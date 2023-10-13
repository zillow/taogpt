from __future__ import annotations
import dataclasses as _dc
import time
import typing as _t
from _collections import defaultdict
import math as _math
import json as _json

import taogpt
import taogpt.llm_model
from . import StepABC, Backtrack, Pause, Executor, Config
from .parsing import *
from .constants import *
import taogpt.utils as _utils
from .utils import safe_subn
from taogpt.prompts import PromptDb


@_dc.dataclass(repr=False)
class Step(StepABC):

    def __post_init__(self):
        self._step_name: str|None = None

    @property
    def step_title(self) -> str:
        return ''

    def set_step_name(self, name: str|None, forced=False):
        name = _utils.str_or_blank(name)
        if name == '':
            return
        if self._step_name is None or forced:
            self._step_name = name
            self._prepend_step_name_header(name)
        else:
            raise RuntimeError(f"step name has already been set to {self._step_name}")

    def _prepend_step_name_header(self, name):
        if not self.description.strip().startswith("[at step"):
            self.description = f"[at step: {name}]\n\n{self.description}"

    @property
    def step_name(self) -> str|None:
        return self._step_name

    def __repr__(self) -> str:
        prev = self.previous.step_id if self.previous is not None else None
        return f"{self.__class__.__name__}(step_id={self.step_id},prev={prev};{self.__repr_local__()})"

    def __repr_local__(self) -> str:
        d = safe_subn(self.description)
        return f"description={d}"

    @property
    def step_id(self) -> int:
        return self.previous.step_id + 1 if self.previous is not None else 0

    @property
    def description_with_header(self) -> str:
        """
        Always emit the `# ` prefix. Caller can remove the `#` heading indicator if need to.
        :return:
        """
        return f"# {self.step_title}\n\n{self.description}" if len(self.step_title) > 0 else self.description

    def show_in_thread(self, with_header=True) -> [(str, str)]:
        content = self.description_with_header if with_header else self.description
        return [(self.role, content)]

    def retryable(self, config: Config):
        return False

    def eval(self, executor: Executor) -> Step | None:
        returned = self.eval_only(executor)
        return returned

    def backtrack(self, prompt_db: PromptDb, backtrack: Backtrack | None):
        pass

    def eval_only(self, executor) -> Step | None:
        return None


@_dc.dataclass(repr=False)
class PythonGenieReplyStep(Step):

    @property
    def step_title(self) -> str:
        return 'The Python Genie Replies'


@_dc.dataclass(repr=False)
class AnalysisStep(Step):

    @property
    def step_title(self) -> str:
        return 'Problem Analysis'

    def __post_init__(self):
        super().__post_init__()
        self._analyzed = False

    def eval_only(self, executor) -> Step | None:
        if self._analyzed:
            return None
        prompt_db: PromptDb  = executor.prompts
        if self.description is None or len(_utils.str_or_blank(self.description)) == 0:
            self.description = prompt_db.orchestrator_ask_init_analysis
        system_prompt = prompt_db.tao_intro
        prompts: _t.List[(str, str)] = executor.show_conversation_thread()
        llm = executor.sage_llm if executor.config.use_sage_llm_for_initial_expansion else executor.llm
        n_retries = 0
        while n_retries < executor.config.max_retries:
            try:
                desc = llm.ask(
                    system_prompt, prompts,
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
                if n_retries >= executor.config.max_retries:
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
        self.description = re.sub(rf"#+\s+{NEXT_I_WANT_TO_WORK_AT}", f"### {NEXT_I_WANT_TO_WORK_AT}:",
                                  self.description, 1)
        sections: _t.Dict[str, str] = parse_sections(self.description)
        self.next_step = sections.pop(NEXT_I_WANT_TO_WORK_AT, None)
        self.is_final_step = self.is_final_step or is_final_answer(self.next_step)
        reconstructed = [f"# {heading}\n{content}" for heading, content in sections.items()]
        self.description = '\n\n'.join(reconstructed)
        self.description = re.sub(rf"# {FREE_TEXT}\n+", "", self.description, flags=re.IGNORECASE)
        self.description = re.sub(r"#+ FILE", "### FILE", self.description, flags=re.IGNORECASE).strip()
        Step.__post_init__(self)

    def eval_only(self, executor) -> Step | None:
        if not _utils.is_blank(self.next_step) and not self.is_final_step:
            prompt_db: PromptDb  = executor.prompts
            prev_step = self.step_name or "start or unknown"
            work_prompt = prompt_db.orchestrator_proceed_to_step.format(prev_step=prev_step, step=self.next_step)
            next = ProceedStep(self, work_prompt, ROLE_ORCHESTRATOR)
            next.set_step_name(self.next_step)
            return next
        return None


@_dc.dataclass(repr=False)
class GiveUpStep(TaoReplyStep):
    TYPE_SPEC = UNSOLVABLE

    @property
    def step_title(self) -> str:
        return GiveUpStep.TYPE_SPEC

    def __post_init__(self):
        super().__post_init__()
        if len(self.description) == 0:
            raise ParseError("Must provide explanation why you gave up.")
        self.issues = [issue.replace('\n', '').strip() for issue in parse_json_list(self.description)]

    def eval_only(self, executor):
        if len(self.issues) > 0:
            executor.record_criticisms(self.issues)
        raise Backtrack(f"Problem or step is unsolvable. I gave up.", self)


@_dc.dataclass(repr=False)
class StepByStepPlan(TaoReplyStep):
    TYPE_SPEC = HERE_IS_MY_STEP_BY_STEP_PLAN

    @property
    def step_title(self) -> str:
        return StepByStepPlan.TYPE_SPEC

    def __repr_local__(self) -> str:
        desc = ';'.join([_utils.safe_subn(step.description, 10) for step in self._steps.values()])
        return f"[{desc}]"

    def __post_init__(self):
        super().__post_init__()
        self._steps = parse_step_by_step_plan(self.description)
        self.first_step = f"{self._steps[0].description}"
        # erase sub_steps
        step_def = {i+1: {'description': step.description} for i, step in self._steps.items()}
        self.description = f"""```json
{_json.dumps(step_def, indent=2)}
```
"""

    def eval_only(self, executor) -> Step | None:
        # when evaluating this node, we are always at the first step
        prompt_db: PromptDb  = executor.prompts
        prev_step = executor.current_step_name
        work_prompt = prompt_db.orchestrator_proceed_to_step.format(prev_step=prev_step, step=self.first_step)
        next = ProceedStep(self, work_prompt, ROLE_ORCHESTRATOR)
        next.set_step_name(self.first_step)
        return next


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

    def eval_only(self, executor) -> Step | None:
        results = executor.ask_genie(self._code_snippets, self)
        result_markdown = '\n\n'.join(f"""```text\n{r}\n```""" for r in results)
        return PythonGenieReplyStep(self, result_markdown, ROLE_GENIE)


@_dc.dataclass(repr=False)
class AskQuestionStep(TaoReplyStep):

    TYPE_SPEC = WILL_ASK_QUESTIONS

    @property
    def step_title(self) -> str:
        return AskQuestionStep.TYPE_SPEC if self._questions is None else 'Tao asked and user replied:'

    def __post_init__(self):
        super().__post_init__()
        self._questions: [str] = None
        self._need_consolidate = False

    @property
    def need_consolidate(self) -> bool:
        return self._need_consolidate

    def need_consolidate_multiple_questions(self, true_or_false: bool):
        self._need_consolidate = true_or_false

    def eval_only(self, executor) -> Step | None:
        if self._need_consolidate:
            prompts: _t.List[(str, str)] = executor.show_conversation_thread()[:-1]
            self.description = self.consolidate_questions(
                executor, prompts, self.description)
            self._need_consolidate = False
        if self._questions is None:
            questions = parse_ordered_list(self.description)
            answers: _t.Dict[str, str] = executor.ask_user(questions)
            new_text = ''
            for q, a in answers.items():
                q_lines = q.split('\n')
                q_lines = '\n'.join([f"> {line}\n" for line in q_lines])
                new_text += q_lines + '\n'
                new_text += a.strip() + '\n\n'
            self.description = new_text
            self.set_step_name(self.step_name, forced=True) # reset the "[at step: ...]" header
            self.role = ROLE_USER
            self._questions = questions
            return None

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
                reply = llm.ask(executor.prompts.tao_intro,
                                conversation_chain, reason='consolidate_questions', temperature=0.0)
                return reply
            except Exception as e:
                n_retries += 1
                time.sleep(n_retries)
                if n_retries >= executor.config.max_retries:
                    raise e


def parse_to_step(prev_step: Step, response: str, working_on: str=None) -> Step:
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
            raise ParseError(f"Unknown strategy heading '{step_type}'")
    step = step_class(prev_step, description=step_def, role=ROLE_TAO)
    if working_on is not None:
        step.set_step_name(working_on)
    return step


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
        desc = ','.join([step.__class__.__name__ for step in self.choices] if self.choices is not None else [])
        return f"[{desc}],ptr={self._ptr}"

    def __post_init__(self):
        super().__post_init__()
        self._ptr = 0
        self.n_expanded = 0
        self._new_criticisms: {int: {str}} = dict()
        if self.choices is not None:
            for next_step in self.choices:
                next_step.previous = self

    @property
    def _expansion_reason(self) -> str:
        return 'expand_choices'

    def _prepend_step_name_header(self, name):
        pass

    def expand_choices(self, executor: Executor, upto_branches: int):
        prompt_db: PromptDb  = executor.prompts
        system_prompt = prompt_db.tao_intro
        direct_answer = prompt_db.tao_template_intuitive_answer if self.first_problem_solving_step \
            else prompt_db.tao_template_direct_step_answer
        tao_templates = prompt_db.tao_templates.format(examples='', direct_answer_template=direct_answer)
        base_prompts: _t.List[(str, str)] = executor.show_conversation_thread()
        base_prompts.insert(-1, (ROLE_ORCHESTRATOR, tao_templates))
        if self.choices is None:
            self.choices = []
        llm = executor.sage_llm if self.first_problem_solving_step \
                                   and executor.config.use_sage_llm_for_initial_expansion else executor.llm
        while self.n_expanded < upto_branches:
            prompts = base_prompts.copy()
            if len(self.choices) > 0:
                prior_plans = [f"[Prior approach#{i + 1}] {prior.description_with_header}"
                               for i, prior in enumerate(self.choices)]
                prior_desc = prompt_db.orchestrator_prior_approaches.format(prior='\n\n---\n'.join(prior_plans))
                prompts.append((ROLE_ORCHESTRATOR, prior_desc))
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            plan: str|None = None
            while n_retries < executor.config.max_retries:
                try:
                    temperature = executor.config.first_try_temperature if self.n_expanded == 0 \
                        else executor.config.alternative_temperature
                    plan = llm.ask(
                        system_prompt, prompts_to_be_sent,
                        reason=self._expansion_reason,
                        step_id=f"{self.step_id}/{self.n_expanded}",
                        temperature=temperature,
                        log_request=(len(self.choices) == 0 and n_retries == 0),
                        collapse_contents={'tao_templates': tao_templates})
                    choice = parse_to_step(self, plan, working_on=self.step_name)
                    self.choices.append(choice)
                    self.n_expanded += 1
                    break
                except Exception as e:
                    n_retries += 1
                    executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent,
                                                plan, prompt_db.orchestrator_expand_parse_error)

    def rank_choices(self, executor: Executor, n_existing_choices: int = 0):
        question_indices = [i for i in range(n_existing_choices, len(self.choices))
                            if _utils.safe_is_instance(self.choices[i], AskPythonGenieStep)]
        if len(question_indices) > 0:
            if self.consolidate_questions(self.choices, question_indices):
                indices = list(range(n_existing_choices)) + question_indices
                self.choices = [self.choices[i] for i in indices]
                executor.logger.log(f"\n**Questions consolidated, final indices**: {indices}\n\n")
        prompt_db: PromptDb  = executor.prompts
        system_prompt = prompt_db.sage_intro
        direct_answer = prompt_db.tao_template_intuitive_answer if self.first_problem_solving_step \
            else prompt_db.tao_template_direct_step_answer
        tao_templates = prompt_db.tao_templates.format(examples='', direct_answer_template=direct_answer)

        def _select_except_self(_: int, step: StepABC) -> bool:
            return step != self

        prompts = executor.show_conversation_thread(selector=_select_except_self)

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
        while n_success < executor.config.votes:
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            while n_retries < executor.config.max_retries:
                try:
                    rank_choice_instruction = prompt_db.orchestrator_rank_choices.split('---')[-1].strip()
                    response = executor.sage_llm.ask(
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
                    executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent,
                                                response, prompt_db.orchestrator_parse_error)
        final_score_repr = '\n'.join([f"{k}. score {v}" for k, v in rankings_one_based.items()])
        indices = self.sort_rankings(rankings_one_based, n_existing_choices)
        executor.logger.log(f"\n**Sorted indices**: {indices} **scores**:\n{final_score_repr}\n\n")
        if len(indices) == 0:
            raise Backtrack(f"No valid plan found for this step.", self)
        if n_existing_choices is not None and n_existing_choices > 0:
            indices = list(range(n_existing_choices)) + indices
        self.choices = [self.choices[i] for i in indices]

    @staticmethod
    def consolidate_questions(choices, indices) -> bool:
        question_indices = [i for i in indices if _utils.safe_is_instance(choices[i], AskQuestionStep)]
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

    def retryable(self, config):
        assert self.choices is not None
        return self.n_expanded <= config.max_search_expansion \
            or self._ptr < len(self.choices) # consume existing expansions

    @property
    def collected_criticisms(self):
        return self._new_criticisms

    def record_criticism(self, additional_criticisms: [str]):
        assert self._ptr >= 0
        if not self._ptr in self._new_criticisms:
            self._new_criticisms[self._ptr] = set()
        self._new_criticisms[self._ptr].update(additional_criticisms)

    def backtrack(self, prompt_db: PromptDb, backtrack: Backtrack | None):
        for i, criticisms in self._new_criticisms.items():
            criticism_list = [f'* {c}' if not c.startswith('* ') else c for c in criticisms]
            note = prompt_db.orchestrator_criticisms.format(criticisms='\n'.join(criticism_list))
            self.choices[i].description += '\n' + note
        self._new_criticisms.clear()
        if self._ptr < self.max_expansion:
            self._ptr += 1
            return
        # should not happen due to the retryable(), this is just defensive
        raise Backtrack("No more alternative", blame=self)

    def eval_only(self, executor: Executor) -> Step | None:
        logger = executor.logger
        old_length = self.n_expanded
        if (self.choices is None or self._ptr >= len(self.choices)) and old_length < self.max_expansion:
            incr = self.first_expansion if old_length == 0 else self.incremental_expansion
            logger.log_debug(f"{self.step_id}/'{self.step_name}' expanding from {self.n_expanded} by {incr} to:"
                    f" {self._ptr + incr}. max={self.max_expansion}")
            self.expand_choices(executor, upto_branches=self._ptr + incr)
            if self.n_expanded - old_length > 1:
                logger.log_debug(f"{self.step_id}/'{self.step_name}' ranking choices from {old_length}")
                self.rank_choices(executor, n_existing_choices=old_length)
            if self.first_problem_solving_step and executor.config.pause_after_initial_solving_expansion:
                raise Pause("Pause after initial solving expansion", self)
        if self.choices is None or len(self.choices) == 0:
            raise Backtrack('No viable options.', blame=self)
        if self._ptr < len(self.choices):
            return self.choices[self._ptr]
        else:
            logger.log_debug(f"{self.step_id}/'{self.step_name}' no more options: {self._ptr}/{len(self.choices)}")
            raise Backtrack('No more options', blame=self)


@_dc.dataclass(repr=False)
class ProceedStep(ExpandableStep):

    @property
    def step_title(self) -> str:
        return ""

    @property
    def _expansion_reason(self) -> str:
        return "proceed_to_next"


@_dc.dataclass(repr=False)
class PresentTaskStep(Step):

    @property
    def step_title(self) -> str:
        return ""

    def eval_only(self, executor) -> Step | None:
        return ProceedStep(self,
                           '',
                           role=ROLE_ORCHESTRATOR,
                           first_expansion=executor.config.first_expansion,
                           max_expansion=executor.config.max_search_expansion,
                           first_problem_solving_step=True)



@_dc.dataclass(repr=False)
class SageReplyStep(Step):

    @property
    def step_title(self) -> str:
        return "Sage Replied"

