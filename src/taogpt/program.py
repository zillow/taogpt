from __future__ import annotations
import dataclasses as _dc
import time
import typing as _t
from _collections import defaultdict

import taogpt.tao_model
from .runtime_env import Invocation, Backtrack, StepABC
from .parsing import *
from .constants import *
import taogpt.utils as _utils
from .utils import log_debug, safe_subn
from taogpt.prompts import PromptSet


@_dc.dataclass(repr=False)
class Step(StepABC):
    previous: Step | None
    step_local_id: int
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
        return self.step_local_id

    @property
    def description_with_extras(self):
        return self.description

    def show_in_thread(self, my_invocation: Invocation, with_extras=False) -> [(str, str)]:
        content = self.description_with_extras if with_extras else self.description
        return [(self.role, content)]

    def rank_choices(self, choices: [Step]) -> _t.List[Step]:
        return choices

    def retryable(self, invocation: Invocation):
        return False

    def eval(self, my_invocation: Invocation) -> Step | None:
        cls = self.__class__.__name__
        sid = self.step_id if self.step_id is not None else 'root'
        sig = f"{sid}@{id(self)}@{cls}"
        log_debug(f">>>>>>>>>> EVAL: {sig:>25} {_utils.safe_subn(self.description)}... <<<<<<<<<<<<")
        assert id(self) == id(my_invocation.step)
        returned = self.eval_only(my_invocation)
        return returned

    def backtrack(self, my_invocation: Invocation, backtrack: Backtrack|None):
        pass

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        return None

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return False

    def __post_init__(self):
        pass


@_dc.dataclass(repr=False)
class UserReplyStep(Step):

    @property
    def step_title(self) -> str:
        return 'User replies'

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p},reply={_utils.safe_subn(self.description)}..."

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return False

    def retryable(self, invocation: Invocation):
        return False # maybe we can ask the user again but Tao will do so by generating new questions.


@_dc.dataclass(repr=False)
class AskForAnalysisStep(Step):

    @property
    def step_title(self) -> str:
        return 'ask for analysis'

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        prompt_db: PromptSet  = my_invocation.executor.prompts
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
                return TaoAnalysisStep(self, self.step_id + 1, desc, ROLE_SOLVER)
            except Exception as e:
                n_retries += 1
                if n_retries >= MAX_RETRIES:
                    raise e


@_dc.dataclass(repr=False)
class TaoReplyStep(Step):

    def __post_init__(self):
        sections = parse_sections(self.description)
        self.description = sections[FREE_TEXT]

    @property
    def description_with_extras(self):
        return _utils.str_or_blank(self.description)

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return not _utils.is_blank(self.description)


@_dc.dataclass(repr=False)
class TaoAnalysisStep(TaoReplyStep):
    @property
    def step_title(self) -> str:
        return 'initial analysis'

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p},{safe_subn(self.description)}"

    @property
    def description_with_extras(self):
        return _utils.str_or_blank(self.description)

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        prompt_db: PromptSet  = my_invocation.executor.prompts
        prompts: _t.List[(str, str)] = my_invocation.executor.show_conversation_thread()
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.orchestrator_direct_solve))
        llm: taogpt.tao_model.LLM = my_invocation.executor.llm
        intuition: str | None = None
        n_retries = 0
        while True:
            try:
                intuition = llm.ask('',prompts, reason='intuition', temperature=0.0)
                break
            except Exception as e:
                n_retries += 1
                time.sleep(n_retries)
                if n_retries >= MAX_RETRIES:
                    raise e
        return ProceedStep(self, self.step_id+1, "How do you want to proceed?", ROLE_ORCHESTRATOR,
                           prepared=intuition)

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return False


@_dc.dataclass(repr=False)
class DirectAnswerStep(TaoReplyStep):
    TYPE_SPEC = WILL_ANSWER_DIRECTLY

    @property
    def step_title(self) -> str:
        return DirectAnswerStep.TYPE_SPEC

    def __post_init__(self):
        sections = parse_sections(self.description)
        self.description = sections[FREE_TEXT]
        self.next_step = sections.get(NEXT_I_WANT_TO_WORK_AT, None)


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
        sections = parse_sections(self.description)
        self.description = _utils.str_or_blank(sections[FREE_TEXT])
        if len(self.description) == 0:
            raise ParseError("Must provide explanation why you gave up.")

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return False

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        raise Backtrack(f"Problem or step is unsolvable. I gave up.", my_invocation)


@_dc.dataclass(repr=False)
class PlanStep(TaoReplyStep):
    TYPE_SPEC = HERE_IS_MY_STEP_BY_STEP_PLAN

    @property
    def step_title(self) -> str:
        return PlanStep.TYPE_SPEC

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p}, {safe_subn(self.description)}"


@_dc.dataclass(repr=False)
class FinalAnswerStep(TaoReplyStep):

    @property
    def step_title(self) -> str:
        return "Tao's final answer"


@_dc.dataclass(repr=False)
class AskQuestionStep(TaoReplyStep):

    TYPE_SPEC = WILL_ASK_QUESTIONS

    @property
    def step_title(self) -> str:
        return AskQuestionStep.TYPE_SPEC

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        return f"{p},questions={_utils.safe_subn(self.description)[:10]}..."

    def __post_init__(self):
        sections = parse_sections(self.description)
        self.description = f"My dear user, I have some questions before I can proceed:\n\n{sections[MY_QUESTIONS]}"

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return False

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        reply = my_invocation.executor.ask_user(self.description)
        reply = _utils.str_or_blank(reply)
        if reply == '':
            return None
        return UserReplyStep(self, self.step_id+1, reply, ROLE_USER)


def parse_to_step(step: Step, response: str) -> Step:
    type_and_def = parse_step_type_spec(response)
    if type_and_def is None:
        raise ParseError(f"Invalid Tao response. Missing header.")
    else:
        step_type, step_def = type_and_def
        if step_type == DirectAnswerStep.TYPE_SPEC:
            step_class = DirectAnswerStep
        elif step_type == AskQuestionStep.TYPE_SPEC:
            step_class = AskQuestionStep
        elif step_type == GiveUpStep.TYPE_SPEC:
            step_class = GiveUpStep
        else:
            step_class = PlanStep
        if step_def is None:
            raise ParseError(f"Missing details.")
    return step_class(step, step_local_id=step.step_local_id + 1, description=step_def, role=ROLE_SOLVER)


@_dc.dataclass(repr=False)
class ExpandableStep(Step):
    choices: _t.List[Step] | None = None
    rankings: _t.Dict[int, float] = None
    prepared: str|None=None

    @property
    def step_title(self) -> str:
        return "A step-by-step plan"

    def __repr_local__(self) -> str:
        p = super().__repr_local__()
        choices, rankings = repr(self.choices), repr(self.rankings)
        return f"{p},choices={choices},rankings={rankings}"

    def __post_init__(self):
        super().__post_init__()
        self._all_criticisms: {str} = set()

    @property
    def collected_criticisms(self):
        return self._all_criticisms

    def record_criticism(self, additional_criticisms: [str]):
        self._all_criticisms.update(additional_criticisms)

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return False  # the ranking will also check for dead-end

    def _expansion_reason(self) -> str:
        return 'expand_choices'

    def expand_choices(self, my_invocation: Invocation, branch_factor = MAX_BRANCHING_FACTOR):
        prompt_db: PromptSet  = my_invocation.executor.prompts
        system_prompt = prompt_db.system_step_expansion
        tao_templates = prompt_db.tao_templates.format(examples=prompt_db.tao_templates_examples)
        prompts: _t.List[(str, str)] = my_invocation.executor.show_conversation_thread()
        prompts.insert(-1, (ROLE_ORCHESTRATOR, tao_templates))
        work_prompt = self.get_expansion_prompt(prompt_db)
        if work_prompt is not None:
            work_prompt = prompt_db.orchestrator_proceed2.format(expansion_prompt=work_prompt)
            prompts.append((ROLE_ORCHESTRATOR, work_prompt))
        last_criticisms = my_invocation.executor.find_last_criticisms(my_invocation)
        if len(last_criticisms) > 0:
            criticism = prompt_db.orchestrator_critics.format(criticisms='\n\n---\n'.join(last_criticisms))
            prompts.append((ROLE_ORCHESTRATOR, criticism))
        self.choices = []
        while len(self.choices) < branch_factor:
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            plan: str|None = None
            while n_retries < MAX_RETRIES:
                try:
                    n = len(self.choices)
                    temperature = 0.0 if len(self.choices) == 0 else None
                    plan = my_invocation.executor.llm.ask(system_prompt, prompts_to_be_sent,
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
                    if isinstance(e, ParseError) and len(prompts_to_be_sent) <= len(prompts):
                        prompts_to_be_sent.append((ROLE_SOLVER, plan))
                        message = prompt_db.orchestrator_expand_parse_error.format(error=str(e))
                        prompts_to_be_sent.append((ROLE_ORCHESTRATOR, message))
                        my_invocation.executor.logger.log(f"\n***RETRY***\n{message}")
                    if n_retries >= MAX_RETRIES:
                        print(f"failed after {n_retries}")
                        raise e
        if len(_utils.str_or_blank(self.prepared)) > 0:
            self.prepared = _utils.str_or_blank(self.prepared)
            if UNSOLVABLE not in self.prepared:
                self.prepared = f"# {WILL_ANSWER_DIRECTLY}\n{self.prepared}"
            self.choices.append(parse_to_step(self, self.prepared))

    def get_expansion_prompt(self, _: PromptSet) -> str | None:
        return None

    def rank_choices(self, my_invocation: Invocation):
        prompt_db: PromptSet  = my_invocation.executor.prompts
        system_prompt = prompt_db.sage
        tao_templates = prompt_db.tao_templates.format(examples='')
        prompts = my_invocation.executor.show_conversation_thread()
        last_criticisms = my_invocation.executor.find_last_criticisms(my_invocation)
        if len(last_criticisms) > 0:
            criticism = prompt_db.orchestrator_critics.format(criticisms='\n\n---\n'.join(last_criticisms))
            prompts.append((ROLE_ORCHESTRATOR, criticism))
        work_prompt = prompt_db.orchestrator_eval_strategy_choices.format(
            tao_templates=tao_templates,
            approaches='\n\n---\n\n'.join([
                f"# [Approach {i+1}] {plan.step_title}\n\n{plan.description_with_extras}"
                for i, plan in enumerate(self.choices)
            ])
        )
        prompts.append((ROLE_ORCHESTRATOR, work_prompt))
        rankings = defaultdict(lambda: 0.0)
        n_success = 0
        while n_success < MAX_VOTING_FACTOR:
            n_retries = 0
            try:
                rank_choice_instruction = prompt_db.orchestrator_eval_strategy_choices.split('---')[-1].strip()
                response = my_invocation.executor.llm.ask(
                    system_prompt, prompts,
                    reason='rank_choices',
                                                          step_id=f"{self.step_id}/{n_success}",
                                                          temperature=0.0 if n_success == 0 else 0.1,
                                                          log_request=(n_success == 0 and n_retries == 0),
                                                          collapse_contents={'tao_templates': tao_templates,
                                                                             'rank_choices': rank_choice_instruction})
                scores = parse_ranking_response(response, len(self.choices))
                if isinstance(scores, str):
                    assert scores == 'backtrack'
                    raise Backtrack(f"On the wrong path", my_invocation)
                for plan, score in scores.items():
                    rankings[plan] += score
                n_success += 1
                log_debug(f"===> received ranking {n_success}: {response[:20]}...", level=2)
            except Exception as e:
                n_retries += 1
                if n_retries >= MAX_RETRIES:
                    raise e
                pass
        final_score_repr = '\n'.join([f"{k}. score {v}" for k, v in rankings.items()])
        my_invocation.executor.logger.log(f"\n### Final scores:\n{final_score_repr}\n\n")
        self.rankings = {k-1: v for k, v in rankings.items()}
        if len(self.rankings) == 0:
            raise Backtrack(f"No valid plan found for this step.", my_invocation)
        indices = sorted(self.rankings.keys(), key=lambda i: self.rankings[i], reverse=True)
        _debug_info = {i: self.rankings[i] for i in indices}
        log_debug(f"===> rankings: {_debug_info}", level=2)
        self.choices = [self.choices[i] for i in indices if self.rankings[i] > 0]
        if len(self.choices) == 0:
            raise Backtrack(f"No valid plans found for this step", my_invocation)

    def retryable(self, invocation: Invocation):
        return self.choices is not None and invocation.current_choice < len(self.choices)

    def backtrack(self, my_invocation: Invocation, backtrack: Backtrack|None):
        if my_invocation.current_choice >= len(self.choices): # shouldn't reach here due to the `retryable` check
            raise RuntimeError("No more alternative", my_invocation) # this is just defensive
        my_invocation.current_choice += 1

    def eval_only(self, my_invocation: Invocation) -> Step | None:
        if self.choices is None:
            self.expand_choices(my_invocation)
            self.rank_choices(my_invocation)
            # todo: use dynamic expansion later
            # attempts = 0
            # while attempts < MAX_RETRIES and (self.choices is None or len(self.choices) < MAX_BRANCHING_FACTOR):
            #     self.expand_choices(my_invocation)
            #     self.rank_choices(my_invocation)
            #     attempts += 1
        if self.choices is None or len(self.choices) == 0:
            raise Backtrack('No viable options.', blame=my_invocation)
        if my_invocation.current_choice < len(self.choices):
            return self.choices[my_invocation.current_choice]
        else:
            raise Backtrack('No more options', blame=my_invocation)


@_dc.dataclass(repr=False)
class ProceedStep(ExpandableStep):

    @property
    def step_title(self) -> str:
        return "Tao will proceed"

    def __post_init__(self):
        super().__post_init__()
        sections = parse_sections(self.description)
        self.description = sections[FREE_TEXT]

    def _expansion_reason(self) -> str:
        return "proceed_to_next"

    def need_to_check_dead_end(self, my_invocation: Invocation) -> bool:
        return False


@_dc.dataclass(repr=False)
class InitialStep(Step):

    @property
    def step_title(self) -> str:
        return "task problem"

    def __post_init__(self):
        super().__post_init__()
        sections = parse_sections(self.description)
        self.description = sections[FREE_TEXT]


@_dc.dataclass(repr=False)
class SageReplyStep(Step):

    @property
    def step_title(self) -> str:
        return "Sage replied"

    def __post_init__(self):
        pass

    def _expansion_reason(self) -> str:
        return "respond_to_criticism"

