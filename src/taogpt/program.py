from __future__ import annotations
import dataclasses as _dc
import time
import typing as _t
from _collections import defaultdict
import math as _math

import taogpt
import taogpt.llm_model
from . import StepABC, Invocation, Backtrack, Pause
from .parsing import *
from .constants import *
import taogpt.utils as _utils
from .utils import log_debug, safe_subn
from taogpt.prompts import PromptDb


def retry_on_parse_error(e, error_report_prompt, response, original_prompts, prompts_to_be_sent, my_invocation):
    if isinstance(e, ParseError) and len(prompts_to_be_sent) <= len(original_prompts):
        prompts_to_be_sent.append((ROLE_TAO, response))
        message = error_report_prompt.format(error=str(e))
        prompts_to_be_sent.append((ROLE_ORCHESTRATOR, message))
        my_invocation.executor.logger.log(f"\n***RETRY***\n{message}")


@_dc.dataclass(repr=False)
class Step(StepABC):
    previous: Step | None
    description: str
    role: str

    @property
    def step_title(self) -> str:
        return ''

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__repr_local__()})"

    def __repr_local__(self) -> str:
        d = safe_subn(self.description)
        prev = self.previous.step_id if self.previous is not None else None
        return f"step_id={self.step_id},prev={prev},role={self.role},description={d}"

    @property
    def step_id(self) -> int:
        return self._step_local_id

    @property
    def description_with_header(self) -> str:
        """
        Always emit the `# ` prefix. Caller can remove the `#` heading indicator if need to.
        :return:
        """
        return f"{self.step_title}\n\n{self.description}" if len(self.step_title) > 0 else self.description

    def show_in_thread(self, my_invocation: Invocation, with_header=True) -> [(str, str)]:
        content = self.description_with_header if with_header else self.description
        return [(self.role, content)]

    def rank_choices(self, choices: [Step]) -> _t.List[Step]:
        return choices

    def retryable(self, invocation: Invocation):
        return False

    def eval(self, my_invocation: Invocation) -> Step | None:
        cls = self.__class__.__name__
        sid = self.step_id if self.step_id is not None else 'root'
        sig = f"{sid}@{id(self)}@{cls}"
        assert id(self) == id(my_invocation.step)
        returned = self.eval_only(my_invocation)
        return returned

    def backtrack(self, my_invocation: Invocation, backtrack: Backtrack|None):
        pass

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        return None

    def __post_init__(self):
        self._step_local_id = self.previous.step_id + 1 if self.previous is not None else 0


@_dc.dataclass(repr=False)
class UserReplyStep(Step):

    @property
    def step_title(self) -> str:
        return 'Here are the answers'

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p},reply={_utils.safe_subn(self.description)}..."

    def retryable(self, invocation: Invocation):
        return False # maybe we can ask the user again but Tao will do so by generating new questions.


@_dc.dataclass(repr=False)
class PythonGenieReplyStep(Step):

    @property
    def step_title(self) -> str:
        return 'The Python Genie Replies'

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p},reply={_utils.safe_subn(self.description)}..."

    def retryable(self, invocation: Invocation):
        return False # maybe we can ask the user again but Tao will do so by generating new questions.


@_dc.dataclass(repr=False)
class AnalysisStep(Step):

    @property
    def step_title(self) -> str:
        return 'Problem Analysis'

    def __post_init__(self):
        super().__post_init__()
        self._analyzed = False

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        if self._analyzed:
            return None
        prompt_db: PromptDb  = my_invocation.executor.prompts
        if self.description is None or len(_utils.str_or_blank(self.description)) == 0:
            self.description = prompt_db.orchestrator_ask_init_analysis
        system_prompt = prompt_db.system_step_expansion
        prompts: _t.List[(str, str)] = my_invocation.executor.show_conversation_thread()
        n_retries = 0
        while n_retries < MAX_RETRIES:
            try:
                desc = my_invocation.executor.llm.ask(system_prompt, prompts,
                                                      reason='request_analysis',
                                                      temperature=0.0,
                                                      step_id=f"{self.step_id}/{n_retries}",
                                                      log_request=n_retries == 0)
                self.description = desc
                self.role = ROLE_TAO
                self._analyzed = True
                return None
            except Exception as e:
                n_retries += 1
                if n_retries >= MAX_RETRIES:
                    raise e


@_dc.dataclass(repr=False)
class TaoReplyStep(Step):

    def __post_init__(self):
        super().__post_init__()
        sections = parse_sections(self.description)
        self.description = sections[FREE_TEXT]


@_dc.dataclass(repr=False)
class DirectAnswerStep(TaoReplyStep):
    TYPE_SPEC = WILL_ANSWER_DIRECTLY

    is_final_step: bool = False

    @property
    def step_title(self) -> str:
        return DirectAnswerStep.TYPE_SPEC

    def __post_init__(self):
        sections = parse_sections(self.description)
        self.next_step = sections.get(NEXT_I_WANT_TO_WORK_AT, None)
        self.is_final_step = self.is_final_step or is_final_answer(self.next_step)
        super().__post_init__()

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        if not _utils.is_blank(self.next_step) and not self.is_final_step:
            prompt_db: PromptDb  = my_invocation.executor.prompts
            work_prompt = prompt_db.orchestrator_proceed_to_step.format(step=self.next_step)
            return ProceedStep(self, work_prompt, ROLE_ORCHESTRATOR)
        return None


@_dc.dataclass(repr=False)
class GiveUpStep(TaoReplyStep):
    TYPE_SPEC = UNSOLVABLE

    @property
    def step_title(self) -> str:
        return GiveUpStep.TYPE_SPEC

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p}, {safe_subn(self.description)}"

    def __post_init__(self):
        super().__post_init__()
        if len(self.description) == 0:
            raise ParseError("Must provide explanation why you gave up.")
        self.issues = [issue.replace('\n', '').strip() for issue in parse_json_list(self.description)]

    def eval_only(self, my_invocation: Invocation):
        if len(self.issues) > 0:
            my_invocation.executor.record_criticisms(self.issues)
        raise Backtrack(f"Problem or step is unsolvable. I gave up.", my_invocation)


@_dc.dataclass(repr=False)
class StepByStepPlan(TaoReplyStep):
    TYPE_SPEC = HERE_IS_MY_STEP_BY_STEP_PLAN

    @property
    def step_title(self) -> str:
        return StepByStepPlan.TYPE_SPEC

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p}, {safe_subn(self.description)}"

    def __post_init__(self):
        super().__post_init__()
        self._steps = parse_step_by_step_plan(self.description)
        why = f" [{self._steps[0].why}]" if _utils.str_or_blank(self._steps[0].why) == '' else ''
        self.first_step = f"{self._steps[0].description}{why}"

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        # when evaluating this node, we are always at the first step
        prompt_db: PromptDb  = my_invocation.executor.prompts
        work_prompt = prompt_db.orchestrator_proceed_to_step.format(step=self.first_step)
        return ProceedStep(self, work_prompt, ROLE_ORCHESTRATOR)


@_dc.dataclass(repr=False)
class FinalAnswerStep(TaoReplyStep):
    TYPE_SPEC = FINAL_ANSWER

    @property
    def step_title(self) -> str:
        return "Tao's Final Answer"


@_dc.dataclass(repr=False)
class AskPythonGenieStep(TaoReplyStep):

    TYPE_SPEC = WILL_ASK_GENIE

    @property
    def step_title(self) -> str:
        return AskPythonGenieStep.TYPE_SPEC

    def __post_init__(self):
        super().__post_init__()
        self._code_snippets = parse_python_snippets(self.description)
        if len(self._code_snippets) == 0:
            raise ParseError("No python code snippet inside markdown fenced block.")
        pitch = "Python Genie, Python Genie, run the Python snippet underneath"
        if pitch not in self.description:
            self.description = f"{pitch}:\n\n{self.description}"

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        results = my_invocation.executor.ask_genie(self._code_snippets, my_invocation)
        result_markdown = '\n\n'.join(f"""```text\n{r}\n```""" for r in results)
        return PythonGenieReplyStep(self, result_markdown, ROLE_GENIE)


@_dc.dataclass(repr=False)
class AskQuestionStep(TaoReplyStep):

    TYPE_SPEC = WILL_ASK_QUESTIONS

    @property
    def step_title(self) -> str:
        return AskQuestionStep.TYPE_SPEC

    def __post_init__(self):
        super().__post_init__()
        self._need_consolidate = False

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p},questions={_utils.safe_subn(self.description)[:10]}..."

    @property
    def need_consolidate(self) -> bool:
        return self._need_consolidate

    def need_consolidate_multiple_questions(self, true_or_false: bool):
        self._need_consolidate = true_or_false

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        if self._need_consolidate:
            prompts: _t.List[(str, str)] = my_invocation.executor.show_conversation_thread()[:-1]
            self.description = self.consolidate_questions(
                my_invocation.executor, prompts, self.description)
            self._need_consolidate = False
        questions = parse_ordered_list(self.description)
        reply = my_invocation.executor.ask_user(questions)
        reply = _utils.str_or_blank(reply)
        if reply == '':
            return None
        return UserReplyStep(self, reply, ROLE_USER)

    @staticmethod
    def consolidate_questions(executor: taogpt.Executor,
                              conversation_chain: _t.List[(str, str)],
                              question_text: str) -> str:
        conversation_chain.append((ROLE_TAO, question_text))
        conversation_chain.append((ROLE_ORCHESTRATOR, executor.prompts.orchestrator_summarize_questions))
        llm: taogpt.LLM = executor.llm
        n_retries = 0
        while True:
            try:
                reply = llm.ask(executor.prompts.system_step_expansion,
                                conversation_chain, reason='consolidate_questions', temperature=0.0)
                return reply
            except Exception as e:
                n_retries += 1
                time.sleep(n_retries)
                if n_retries >= MAX_RETRIES:
                    raise e


def parse_to_step(step: Step, response: str) -> Step:
    step_type, step_def = parse_step_type_spec(response)
    if step_type is None:
        raise ParseError(f"Invalid Tao response. Missing header.")
    else:
        if step_type == DirectAnswerStep.TYPE_SPEC:
            step_class = DirectAnswerStep
        elif step_type == FinalAnswerStep.TYPE_SPEC:
            step_class = FinalAnswerStep
        elif step_type == AskQuestionStep.TYPE_SPEC:
            step_class = AskQuestionStep
        elif step_type == AskPythonGenieStep.TYPE_SPEC:
            step_class = AskPythonGenieStep
        elif step_type == GiveUpStep.TYPE_SPEC:
            step_class = GiveUpStep
        else:
            step_class = StepByStepPlan
        if step_def is None:
            raise ParseError(f"Missing details.")
    return step_class(step, description=step_def, role=ROLE_TAO)


@_dc.dataclass(repr=False)
class ExpandableStep(Step):
    choices: _t.List[Step] | None = None
    first_expansion: int = 1
    incremental_expansion: int = 1
    max_expansion: int = 4
    first_problem_solving_step: bool = False

    @property
    def step_title(self) -> str:
        return "A step-by-step plan"

    def __repr_local__(self) -> str:
        return f"{repr(self.choices)},ptr={self._ptr}"

    def __post_init__(self):
        super().__post_init__()
        self._ptr = 0
        self._all_criticisms: {int: {str}} = dict()
        if self.choices is not None:
            for next_step in self.choices:
                next_step.previous = self

    @property
    def collected_criticisms(self):
        return self._all_criticisms

    def record_criticism(self, additional_criticisms: [str]):
        assert self._ptr >= 0
        if not self._ptr in self._all_criticisms:
            self._all_criticisms[self._ptr] = set()
        self._all_criticisms[self._ptr].update(additional_criticisms)

    def _expansion_reason(self) -> str:
        return 'expand_choices'

    def expand_choices(self, my_invocation: Invocation, upto_branches: int):
        executor = my_invocation.executor
        upto_branches = min(upto_branches, executor.config.max_search_expansion)
        prompt_db: PromptDb  = executor.prompts
        system_prompt = prompt_db.system_step_expansion
        direct_answer = prompt_db.tao_template_intuitive_answer if self.first_problem_solving_step \
            else prompt_db.tao_template_direct_step_answer
        tao_templates = prompt_db.tao_templates.format(examples='', direct_answer_template=direct_answer)
        prompts: _t.List[(str, str)] = executor.show_conversation_thread()
        prompts.insert(-1, (ROLE_ORCHESTRATOR, tao_templates))
        if self.choices is None:
            self.choices = []
        if len(self.choices) > 0:
            prior_plans_and_criticisms = self.gather_choices_with_criticisms()
            criticism = prompt_db.orchestrator_critics.format(criticisms='\n\n---\n'.join(prior_plans_and_criticisms))
            prompts.append((ROLE_ORCHESTRATOR, criticism))
        while len(self.choices) < upto_branches:
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            plan: str|None = None
            while n_retries < MAX_RETRIES:
                try:
                    n = len(self.choices)
                    temperature = executor.config.first_try_temperature if len(self.choices) == 0 \
                        else executor.config.alternative_temperature
                    plan = executor.llm.ask(system_prompt, prompts_to_be_sent,
                                            reason=self._expansion_reason(),
                                            step_id=f"{self.step_id}/{n}",
                                            temperature=temperature,
                                            log_request=(len(self.choices) == 0 and n_retries == 0),
                                            collapse_contents={'tao_templates': tao_templates})
                    choice = parse_to_step(self, plan)
                    self.choices.append(choice)
                    log_debug(f"===> received choice {len(self.choices)}: {plan[:30]}...", level=2)
                    break
                except Exception as e:
                    n_retries += 1
                    retry_on_parse_error(e, prompt_db.orchestrator_expand_parse_error,
                                         plan, prompts, prompts_to_be_sent, my_invocation)
                    if n_retries >= MAX_RETRIES:
                        print(f"failed after {n_retries}")
                        raise e

    def gather_choices_with_criticisms(self):
        prior: Step
        prior_plans_and_criticisms = []
        for i, prior in enumerate(self.choices):
            # desc_with_criticism = f"[Prior approach {i + 1}] {prior.description}"
            desc_with_criticism = f""
            if i in self._all_criticisms:
                # desc_with_criticism += "\n\ncriticism:\n"
                desc_with_criticism += '\n'.join([f"* {s.strip()}" for s in self._all_criticisms[i]])
            prior_plans_and_criticisms.append(desc_with_criticism)
        return prior_plans_and_criticisms

    def rank_choices(self, my_invocation: Invocation, n_existing_choices: int=0):
        question_indices = [i for i in range(n_existing_choices, len(self.choices))
                               if isinstance(self.choices[i], AskPythonGenieStep)]
        if len(question_indices) > 0:
            if self.consolidate_questions(self.choices, question_indices):
                indices = list(range(n_existing_choices)) + question_indices
                self.choices = [self.choices[i] for i in indices]
                my_invocation.executor.logger.log(f"\n**Questions consolidated, final indices**: {indices}\n\n")
        prompt_db: PromptDb  = my_invocation.executor.prompts
        system_prompt = prompt_db.sage
        direct_answer = prompt_db.tao_template_intuitive_answer if self.first_problem_solving_step \
            else prompt_db.tao_template_direct_step_answer
        tao_templates = prompt_db.tao_templates.format(examples='', direct_answer_template=direct_answer)
        prompts = my_invocation.executor.show_conversation_thread()

        def _fix_desc_heading(desc: str):
            if desc.strip().startswith('# '):
                return desc.replace('# ', '', 1)
            return desc

        work_prompt = prompt_db.orchestrator_rank_choices.format(
            tao_templates='', # skip template
            approaches='\n\n---\n\n'.join([
                f"# [Approach {i+1}] {_fix_desc_heading(plan.description_with_header)}"
                for i, plan in enumerate(self.choices)
            ])
        )
        prompts.append((ROLE_ORCHESTRATOR, work_prompt))
        rankings_one_based: _t.Dict[int, float] = defaultdict(lambda: 0.0)
        ranking_types = {i+1: plan.step_title for i, plan in enumerate(self.choices)}
        n_success = 0
        response: str|None = None
        while n_success < MAX_VOTING_FACTOR:
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            while n_retries < MAX_RETRIES:
                try:
                    rank_choice_instruction = prompt_db.orchestrator_rank_choices.split('---')[-1].strip()
                    response = my_invocation.executor.sage_llm.ask(
                        system_prompt, prompts_to_be_sent,
                        reason='rank_choices',
                        step_id=f"{self.step_id}/{n_success}",
                        temperature=0.0 if n_success == 0 else 0.1,
                        log_request=(n_success == 0 and n_retries == 0),
                        collapse_contents={'tao_templates': tao_templates, 'rank_choices': rank_choice_instruction})
                    scores, dupes = parse_ranking_response(response, len(self.choices))
                    for plan, score in scores.items():
                        rankings_one_based[plan] += score
                    self.check_duplicates(dupes, scores, ranking_types)
                    n_success += 1
                    break
                except Exception as e:
                    n_retries += 1
                    if n_retries >= MAX_RETRIES:
                        raise e
                    retry_on_parse_error(e, prompt_db.orchestrator_parse_error,
                                         response, prompts, prompts_to_be_sent, my_invocation)
        final_score_repr = '\n'.join([f"{k}. score {v}" for k, v in rankings_one_based.items()])
        indices = self.sort_rankings(rankings_one_based, n_existing_choices)
        my_invocation.executor.logger.log(f"\n**Sorted indices**: {indices} **scores**:\n{final_score_repr}\n\n")
        if len(indices) == 0:
            raise Backtrack(f"No valid plan found for this step.", my_invocation)
        if n_existing_choices is not None and n_existing_choices > 0:
            indices = list(range(n_existing_choices)) + indices
        self.choices = [self.choices[i] for i in indices]

    @staticmethod
    def consolidate_questions(choices, indices) -> bool:
        question_indices = [i for i in indices if isinstance(choices[i], AskQuestionStep)]
        if len(question_indices) > 1:
            merged_question: AskQuestionStep = choices[question_indices[0]]
            for i in range(len(question_indices) - 1, 0, -1):  # all except first in reversed order
                question_index = question_indices[i]
                merged_question.description += '\n\n---\n\n' + choices[question_index].description
                indices.remove(question_index)
            merged_question.need_consolidate_multiple_questions(True)
            return True
        return False

    @staticmethod
    def sort_rankings(rankings_one_based, n_existing_choices):
        # rank only new choices
        rankings = {k - 1: score for k, score in rankings_one_based.items()
                    if score > 0 and (n_existing_choices is None or k - 1 >= n_existing_choices)}
        indices = sorted(rankings.keys(), key=lambda i: rankings[i], reverse=True)
        return indices

    @staticmethod
    def check_duplicates(dupes, scores, ranking_types):
        for dupe, original in dupes.items():
            if ranking_types[dupe] != ranking_types[original]:
                raise ParseError(f"Approach#{dupe} is of type \"{ranking_types[dupe]}\" but "
                                 f"Approach#{original} is of type \"{ranking_types[original]}\". "
                                 f"They cannot be duplicates of each other.")
            else:
                scores[dupe] = -_math.fabs(scores[original])

    def retryable(self, invocation: Invocation):
        assert self.choices is not None
        return len(self.choices) <= invocation.executor.config.max_search_expansion \
            or self._ptr < len(self.choices)

    def backtrack(self, my_invocation: Invocation, backtrack: Backtrack|None):
        if self._ptr < self.max_expansion:
            self._ptr += 1
            return
        # should not happen due to the retryable(), this is just defensive
        raise Backtrack("No more alternative", blame=my_invocation)

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        if self.choices is None or len(self.choices) < self.max_expansion:
            old_length = len(self.choices) if self.choices is not None else 0
            incr = self.first_expansion if self.choices is None else self.incremental_expansion
            self.expand_choices(my_invocation, upto_branches=self._ptr + incr)
            if self.choices is not None and len(self.choices) - old_length > 1:
                self.rank_choices(my_invocation, n_existing_choices=old_length)
            if self.first_problem_solving_step and my_invocation.executor.config.pause_after_initial_solving_expansion:
                raise Pause("Pause after initial solving expansion", self)
        if self.choices is None or len(self.choices) == 0:
            raise Backtrack('No viable options.', blame=my_invocation)
        if self._ptr < len(self.choices):
            return self.choices[self._ptr]
        else:
            raise Backtrack('No more options', blame=my_invocation)


@_dc.dataclass(repr=False)
class ProceedStep(ExpandableStep):

    @property
    def step_title(self) -> str:
        return ""

    def _expansion_reason(self) -> str:
        return "proceed_to_next"


@_dc.dataclass(repr=False)
class PresentTaskStep(Step):

    @property
    def step_title(self) -> str:
        return ""

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        return ProceedStep(self,
                           '',
                           role=ROLE_ORCHESTRATOR,
                           first_expansion=my_invocation.executor.config.first_expansion,
                           max_expansion=my_invocation.executor.config.max_search_expansion,
                           first_problem_solving_step=True)



@_dc.dataclass(repr=False)
class SageReplyStep(Step):

    @property
    def step_title(self) -> str:
        return "Sage Replied"

    def _expansion_reason(self) -> str:
        return "respond_to_criticism"

