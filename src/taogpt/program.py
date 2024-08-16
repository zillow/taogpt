from __future__ import annotations

import math as _math
import typing as _t
from _collections import defaultdict as _defaultdict
from abc import abstractmethod, ABCMeta
from difflib import unified_diff as _unified_diff

import taogpt
import taogpt.llm_model
import taogpt.utils as _utils
from taogpt.prompts import PromptDb
from . import StepABC, Backtrack, Executor, Config, GeneratedFile, Pause
from .exceptions import *
from .parsing import *
from .parsing import parse_issue_report
from .utils import safe_subn
import dataclasses


@dataclasses.dataclass
class IssueSeverityCount:
    fatals: int
    errors: int
    warnings: int
    affected: int

    @property
    def severe_issues(self) -> int:
        return self.fatals + self.errors


def count_issue_severities(issues: list[str]) -> IssueSeverityCount:
    return IssueSeverityCount(
        fatals=sum(int(issue.startswith('fatal:')) for issue in issues),
        errors=sum(int(issue.startswith('error:')) for issue in issues),
        warnings=sum(int(issue.startswith('warnings:')) for issue in issues),
        affected=sum(int(issue.startswith('affected:')) for issue in issues),
    )


def supported_ops(config: Config) -> str:
    ops = [MY_THOUGHT, HERE_IS_MY_STEP_BY_STEP_PLAN]
    if config.ask_questions:
        ops.append(WILL_ASK_QUESTIONS)
    if config.ask_genie:
        ops.append(WILL_ASK_GENIE)
    if config.file_support:
        ops.append(WRITE_FILE)
    return ','.join([f"`{op}:`" for op in ops])


class Step(StepABC):

    def __init__(self, *, description: str, role: str, step_name: str|None, **_):
        super().__init__(description=description, role=role, step_name=step_name)
        self._part_of: StepByStepPlan|None = None
        self._created_by: Step|None = None
        self._criticisms: list[str] = list()
        self._past_criticisms: list[str] = list()

    def record_criticisms(self, additional_criticisms: list[str]):
        self._criticisms.extend(additional_criticisms)

    @property
    def criticisms(self) -> list[str]:
        return self._criticisms

    def clear_criticisms(self):
        for new in self._criticisms:
            already_reported = False
            if 'Time-out encountered during repair' in new or new.startswith('affected:'):
                continue
            for old in self._past_criticisms:
                if _utils.normalized_levenstein_distance(new, old) <= 0.1:
                    already_reported = True
                    break
            if not already_reported:
                self._past_criticisms.append(new)
        self._criticisms.clear()

    @property
    def past_criticisms(self) -> list[str]:
        return self._past_criticisms

    def format_critic_text(self):
        all_criticisms = [f'* {c}' if not c.startswith('* ') else c for c in self.criticisms]
        return "\n".join(all_criticisms)

    @property
    def step_title(self) -> str:
        return ''

    @property
    def step_header(self):
        title = self.step_title.strip()
        return f"{title}:" if len(title) > 0 else ''

    @property
    def part_of(self) -> StepByStepPlan|None:
        return self._part_of

    @part_of.setter
    def part_of(self, plan: StepByStepPlan):
        if not _utils.safe_is_instance(plan, StepByStepPlan):
            return
        self._part_of = plan
        if plan is not None:
            plan.append_realized_steps(self)

    @property
    def created_by(self) ->Step:
        return self._created_by

    @created_by.setter
    def created_by(self, by: Step):
        self._created_by = by

    def __repr__(self) -> str:
        short_repr = self.step_name
        if short_repr is None or len(short_repr) == 0:
            short_repr = self.__repr_local__()
        return f"{self.__class__.__name__}({short_repr})"

    def __repr_local__(self) -> str:
        d = safe_subn(self.description)
        return f"description={d}"

    @property
    def extras(self) -> str:
        return ''

    def show_in_thread(self, step_index: int, with_header=True, with_extras=False) -> list[tuple[str, str]]:
        extra_content = self.extras if with_extras else ''
        if _utils.str_or_blank(self.description) == '' and _utils.str_or_blank(extra_content) == '':
            return []
        content = ''
        if with_header:
            content += f"{self.step_header}\n" if len(self.step_header) > 0 else ""
            tag = self.step_name_tag(step_index)
            content += f"{tag}\n\n"
        content += self.description
        content += extra_content
        return [(self.role, content)]

    def step_name_tag(self, step_index) -> str:
        step_name = _utils.str_or_blank(self.step_name)
        if step_name == '':  # no name, use numeric index
            step_name = f"step {step_index}"
        tag = f"[at step#{step_index}: {step_name}]"
        return tag

    def retryable(self, config: Config):
        return False

    def reset_retry_count(self):
        pass

    def eval(self, executor: Executor) -> Step | None:
        returned = self.eval_only(executor)
        return returned

    def eval_only(self, executor: Executor) -> Step | None:
        return None

    def validate(self, executor: Executor):
        pass


class Idle(Step):

    def __init__(self, **_):
        super().__init__(description='', role=ROLE_ORCHESTRATOR, step_name='waiting for task', **_)

    @property
    def visible_in_summarization(self) -> bool:
        return False


class FixableStep(Step):

    def retryable(self, config):
        return self.n_tries < config.max_repairs

    @property
    @abstractmethod
    def n_tries(self) -> int:
        pass

    @abstractmethod
    def repair(self, executor: Executor):
        pass

    def log_repair(self, executor):
        critic_text = self.format_critic_text()
        executor.logger.log(f'---\n<div style="color: white; background-color: gray">\n')
        executor.logger.log(f"# REPAIRING {self.step_name}/{executor.step_id(self)}#{self.n_tries}:\n")
        executor.logger.log(f"</div>\n")
        return critic_text


class TaoReplyStep(Step):

    def __init__(self, *, description: str, role: str, step_name: str|None, **kwargs):
        try:
            next_step, description = parse_next_step_spec(description, required=False)
        except ParseError:
            next_step = None
            pass
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._next_step = next_step
        self._process_next_step()

    def _process_next_step(self):
        pass

    def validate(self, executor: Executor):
        super().validate(executor)
        self.validate_next_step(executor)

    def validate_next_step(self, executor: Executor):
        validate_next_step_spec(executor, self._next_step, nullify_next_step_if_not_in_gp=True)


class DirectAnswerStep(TaoReplyStep, FixableStep):
    TYPE_SPEC = MY_THOUGHT

    @property
    def step_title(self) -> str:
        return DirectAnswerStep.TYPE_SPEC

    def __init__(self, *, description: str, role: str, step_name: str, is_final_step=False, **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self.is_final_step = is_final_step
        self._n_tries = 1 # already evaluated once since the description is the result
        self._previous_contents: list[str] = []
        if self.is_final_step:
            self._next_step = NextStepDesc(None, None, True, "all done", None)

    @property
    def n_tries(self) -> int:
        return self._n_tries

    @property
    def next_step(self) -> NextStepDesc|None:
        return self._next_step

    def reset_retry_count(self):
        self._n_tries = 0

    def repair(self, executor: Executor):
        self._previous_contents.append(self.description)
        critic_text = self.log_repair(executor)

        config = executor.config
        prompt_db: PromptDb  = executor.prompts
        prompts = executor.show_conversation_thread(with_header=True, with_extras=True, stop_at=self)
        step_id = executor.step_id(self)
        instr = prompt_db.tao_fix_issues.format(step_id=step_id, step=self.step_name, critic_text=critic_text)
        prompts.append((ROLE_ORCHESTRATOR, instr))

        to_be_sent = prompts.copy()
        n_retries = 0
        response: str | None = None
        while n_retries < config.max_retries:
            try:
                response = executor.llm.ask(
                    executor.prompts.tao_intro,
                    to_be_sent,
                    temperature=config.get_temperature(len(self._criticisms) + n_retries),
                    reason=f"fix",
                    step_id=f"{executor.step_id(self)}/{len(self._criticisms)}#{n_retries}")
                response = _utils.str_or_blank(response)
                if response.strip().lower().startswith("no change"):
                    break
                dummy = parse_to_step(response, working_on=self.step_name,
                                      supported_headers=supported_ops(config),
                                      default_header=self.TYPE_SPEC)
                if not _utils.safe_is_instance(dummy, DirectAnswerStep):
                    raise ParseError("Only same action type (direct answer) is allowed during repair or fix.")
                dummy.validate(executor)
                self.description = dummy.description
                break
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
        self._n_tries += int(count_issue_severities(self.criticisms).severe_issues > 0)
        self.clear_criticisms()

    def eval_only(self, executor: Executor) -> Step | None:
        if self.next_step is not None:
            return proceed_next(self, executor, self.next_step, difficulty=self.next_step.difficulty)
        return None


class WriteFileStep(DirectAnswerStep):
    TYPE_SPEC = WRITE_FILE

    @property
    def step_title(self) -> str:
        return WriteFileStep.TYPE_SPEC

    @property
    def step_header(self):
        return f"{self.step_title}: {self.file_path}"

    def __init__(self, *, description: str, role: str, step_name: str, is_final_step=False, **kwargs):
        lines = description.strip().split('\n')
        if len(lines) == 0:
            raise ParseError("No file name and content in Markdown fenced block")
        path = normalize_path(lines[0])
        description = '\n'.join(lines[1:]).strip()
        if _utils.str_or_blank(step_name) == '':
            step_name = f'write/update file `{path}`'
        super().__init__(description=description, role=role, step_name=step_name, is_final_step=is_final_step, **kwargs)
        self._file_path = path

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def collected_files(self) -> dict[str, GeneratedFile]:
        content_type, content, _, desc = gather_file_contents(self.description)
        return {
            self.file_path: GeneratedFile(content_type, content, desc)
        }


class ConsolidateFileStep(WriteFileStep):
    TYPE_SPEC = "CONSOLIDATE_FILE"

    def __init__(self, *, role: str, file_name: str,
                 between: list[Step]=None,
                 keep_content_even_if_same=False, **kwargs):
        super().__init__(description=f"{normalize_path(file_name)}\n", role=role,
                         step_name=f"consolidate file {file_name}", **kwargs)
        self.keep_content_even_if_same = keep_content_even_if_same
        self._evaluated = False
        self.between_steps = between

    @property
    def step_title(self) -> str:
        return ConsolidateFileStep.TYPE_SPEC

    @property
    def evaluated(self) -> bool:
        return self._evaluated

    @evaluated.setter
    def evaluated(self, evaluated: bool):
        self._evaluated = evaluated

    @property
    def collected_files(self) -> dict[str, GeneratedFile]:
        file = gather_file_contents(self.description, expect_one=False)
        if file is None:
            return dict()
        content_type, content, _, desc = file
        return {self.file_path: GeneratedFile(content_type, content, desc)}

    def eval_only(self, executor) -> Step | None:
        if self.evaluated:
            return None
        prompt_db = executor.prompts

        if self.between_steps is None:
            self.between_steps = _t.cast(list[Step], executor.chain)
        self.between_steps = [step for step in self.between_steps if step.visible_in_chain and step is not self]
        critic_text = ''
        if len(self.criticisms) > 0:
            critic_text = self.format_critic_text()

        all_versions: list[GeneratedFile] = collect_all_versions(self.between_steps, self._file_path)
        if len(all_versions) <= 1: # should not happen due to caller filtering
            if self.keep_content_even_if_same:
                self.description = f"The last version of file `{self._file_path}` looks good. No change."
            self._evaluated = True
            return None
        last_version = all_versions[-1]

        # file_sizes = [len(version.content) for version in all_versions]
        # if max(file_sizes) > 1024 or sum(file_sizes) > 2048: # maybe too hard
        g_file = rolling_diff_file_consolidate(
            executor, self._file_path, chain=self.between_steps, critic_text=critic_text)
        desc = _utils.str_or_blank(g_file.description)
        if len(desc) > 0:
            desc = f"This file is for: {desc}\n"
        self.description = f"""Consolidated file `{self.file_path}`.
{desc}
{g_file.markdown_snippet}
"""
        self.finish_consolidation(last_version)
        return None

        # between = ''
        # if len(self.between_steps) > 0:
        #     from_step = self.between_steps[0].step_name_tag(executor.step_id(self.between_steps[0]))
        #     to_step = self.between_steps[-1].step_name_tag(executor.step_id(self.between_steps[-1]))
        #     between = "between steps {from_step} to {to_step}".format(from_step=from_step, to_step=to_step)
        # system_prompt = prompt_db.tao_intro
        # except_me = self if len(self.criticisms) == 0 else None
        # prompts = executor.show_conversation_thread(with_header=True, with_extras=True,
        #                                             except_step=except_me, stop_at=self)
        # prompts.append((ROLE_ORCHESTRATOR, prompt_db.tao_ensure_updated_file_integrity.format(
        #     file_name=self._file_path, between=between)))
        # if len(critic_text) > 0:
        #     step_id = executor.step_id(self)
        #     instr = prompt_db.tao_fix_issues.format(step_id=step_id, step=self.step_name, critic_text=critic_text)
        #     prompts.append((ROLE_ORCHESTRATOR, instr))
        # n_retries = 0
        # response: str|None = None
        # to_be_sent = prompts.copy()
        # while n_retries < executor.config.max_retries:
        #     try:
        #         self.description = executor.llm.ask(
        #             system_prompt, to_be_sent,
        #             reason=self.TYPE_SPEC,
        #             step_id=f"{executor.step_id(self)}#{n_retries}",
        #             temperature=executor.config.get_temperature(n_retries))
        #         if len(self.collected_files) != 1 or self._file_path not in self.collected_files:
        #             raise ParseError(f"You should respond (only) with the complete content of file {self._file_path}")
        #         self.finish_consolidation(last_version)
        #         return None
        #     except ThisMaybeTooHardError as ex:
        #         executor.logger.log_error(str(ex))
        #         self.collected_files[self._file_path] = rolling_diff_file_consolidate(
        #             executor, self._file_path, chain=self.between_steps, critic_text=critic_text)
        #         self.finish_consolidation(last_version)
        #         return None
        #     except ParseError as ex:
        #         n_retries += 1
        #         executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
        #                                     prompt_db.orchestrator_parse_error)
        # return None

    def finish_consolidation(self, last_version):
        if self.keep_content_even_if_same:
            pass
        elif self.collected_files[self._file_path].content == last_version.content and \
                self.collected_files[self._file_path].content_type == last_version.content_type:
            self.description = f"The last version of file `{self._file_path}` looks good. No change."
        self.evaluated = True

    def repair(self, executor: Executor):
        self._previous_contents.append(self.description)
        self.log_repair(executor)
        self.evaluated = False
        self.eval_only(executor)
        self._n_tries += int(count_issue_severities(self.criticisms).severe_issues > 0)
        self.clear_criticisms()


class ReportErrorStep(TaoReplyStep):
    TYPE_SPEC = REPORT_ERROR

    @property
    def step_title(self) -> str:
        return ReportErrorStep.TYPE_SPEC

    def __init__(self, *, description: str, role: str, step_name:str=None, **kwargs):
        super().__init__(description=description, role=role, step_name=None, **kwargs)
        _ = step_name
        self.issues: dict[str, _t.Tuple[str, list[tuple[int, str]] | None]] = dict()

    def validate(self, executor: Executor):
        super().validate(executor)
        self.issues = format_error_reports([self.description], executor.step_id(self), executor)

    def _process_next_step(self):
        super()._process_next_step()
        self._next_step = None

    def eval_only(self, executor):
        if len(self.issues) > 0:
            culprits, n_errors = identify_culprits(executor, self.issues)
            if len(culprits) > 0:
                try:
                    repair_or_backtrack(executor, culprits)
                except RedoFinalCheck as failure:
                    raise Backtrack("Repair attempt failed", self)
                # No Backtrack raised, we have fixed all errors, pop itself
                previous = executor.previous_step(self)
                assert previous is not None and _utils.safe_is_instance(previous, ExpandableStep)
                assert executor.chain[-1] is self
                executor.chain.pop(-1)
                _t.cast(ExpandableStep, previous).choices.remove(self)
                return previous
        raise Backtrack(f"Problem or step is unsolvable. I gave up.", self)


class StepByStepPlan(TaoReplyStep):
    TYPE_SPEC = HERE_IS_MY_STEP_BY_STEP_PLAN

    @property
    def step_title(self) -> str:
        return StepByStepPlan.TYPE_SPEC

    def __repr_local__(self) -> str:
        desc = ';'.join([_utils.safe_subn(step.description, 10) for step in self._steps.values()])
        return f"[{desc}]"

    def __init__(self, *, description: str, role: str, step_name: str|None, **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._realized_steps: list[Step] = list()
        self._next_step_i = 1 # 1-base
        self._free_text = self.description
        self._has_branching, self._has_loop = False, False
        self._steps: dict[int, StepDescriptor] = dict()

    def _process_next_step(self):
        super()._process_next_step()
        self._next_step = None # always go to the first step in the plan

    @property
    def steps(self) -> dict[int, StepDescriptor]:
        return self._steps

    def validate(self, executor: Executor):
        super().validate(executor)
        step_id = executor.step_id(self)
        n_retries = 0
        prompts = [
            (ROLE_TAO, self.description),
            (ROLE_ORCHESTRATOR, executor.prompts.tao_step_by_step_format)
        ]
        prompts_to_be_sent = prompts.copy()

        response: str = ''
        while n_retries < executor.config.max_retries:
            try:
                response = executor.sage_llm.ask(
                    None,
                    prompts_to_be_sent,
                    reason="format-plan",
                    step_id=f"{step_id}#{n_retries}",
                    temperature=executor.config.get_temperature(n_retries))
                self.parse_and_set_step_plan(response)
                break
            except ParseError as e:
                n_retries += 1
                executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
        self.check_duplicated_plan(executor)

    def check_duplicated_plan(self, executor):
        ancestor_plans = executor.select_steps(StepByStepPlan, except_step=self, stop_at=self)
        for ancestor in ancestor_plans:
            ancestor = _t.cast(StepByStepPlan, ancestor)
            if len(self.steps) != len(ancestor.steps):
                continue
            if self.steps == ancestor.steps:
                step_id = executor.step_id(self) or len(executor.chain)
                msg = ("The last response repeats the same plan as the previous step {plan}. Reply with a different "
                       "answer unique to the upcoming step {this_step}.".format(
                    plan=ancestor.step_name_tag(executor.step_id(ancestor)),
                    this_step=self.step_name_tag(step_id)))
                raise ParseError(msg)

    def parse_and_set_step_plan(self, json_payload):
        _, blocks = check_and_fix_fenced_blocks(json_payload, collapse_blocks=True)
        json_key, json_block = None, None
        for key, (_, content_type, _, block_content) in blocks.items():
            if content_type == 'json':
                if json_key is None:
                    json_block = block_content
                else:
                    raise ParseError(f"Expect only one JSON block, but found multiple. Please merge into one")
        if json_block is None:
            raise ParseError(f"Expecting step-by-step plan in a JSON fenced block, found none.")
        parsed_plan = parse_step_by_step_plan(json_block)
        steps, self._has_branching, self._has_loop = parsed_plan
        self._steps = {i + 1: step for i, step in enumerate(step for step in steps.values())}

    def advance_to_next_step(self, trial=False) -> tuple[int, str, int]|None:
        if (self._next_step_i == 1 or self.sequential) and 0 < self._next_step_i <= len(self._steps): # 1-based
            i = self._next_step_i
            if not trial:
                if self.sequential:
                    self._next_step_i += 1
                else:
                    self._next_step_i= -1 # signal
            return i, self._steps[i].description, self._steps[i].difficulty
        return None

    @property
    def sequential(self) -> bool:
        return not (self._has_branching or self._has_loop)

    def eval_only(self, executor) -> Step | None:
        # when evaluating this node, we are always at the first step
        first_step = self.advance_to_next_step()
        assert first_step is not None
        assert first_step[0] == 1
        return ProceedStep.create_proceed_step(executor, first_step[1], self, first_step[2])

    @property
    def realized_steps(self) -> list[Step]:
        return self._realized_steps

    def append_realized_steps(self, step: Step|None) -> list[Step]:
        if step is not None:
            self._realized_steps.append(step)
        return self._realized_steps

    def find_step(self, step_desc: str, min_distance=0.05) -> tuple[int|None, StepDescriptor|None, float|None]:
        step_desc = _utils.str_or_blank(step_desc)
        for i, spec in self._steps.items():
            distance = _utils.normalized_levenstein_distance(spec.description, step_desc)
            if distance <= min_distance:
                return i, spec, distance
        return None, None, None

    @staticmethod
    def find_step_from_chain(executor: Executor, step_desc: str, min_distance=0.05) -> StepByStepPlan|None:
        matched = list()
        for step in reversed(executor.chain):
            if _utils.safe_is_instance(step, StepByStepPlan):
                step = _t.cast(StepByStepPlan, step)
                i, _, d = step.find_step(step_desc, min_distance)
                if i is not None:
                    matched.append((d, step, i))
        if len(matched) == 0:
            return None
        matched = sorted(matched, key=lambda x: x[0])
        return matched[0][1]

    @staticmethod
    def find_first_step_by_step(executor: Executor) -> StepByStepPlan|None:
        for i in range(len(executor.chain)):
            if _utils.safe_is_instance(executor.chain[i], StepByStepPlan):
                return _t.cast(StepByStepPlan, executor.chain[i])
        return None

    @staticmethod
    def find_last_step_by_step(executor: Executor, before:StepABC|int|None=None) \
            -> tuple[StepByStepPlan|None, int|None]:
        if before is None:
            before = len(executor.chain)-1
        elif _utils.safe_is_instance(before, StepABC):
            before = executor.step_id(before)-1
        if before >= len(executor.chain):
            before = len(executor.chain)-1
        for i in range(before, -1, -1):
            if _utils.safe_is_instance(executor.chain[i], StepByStepPlan):
                return _t.cast(StepByStepPlan, executor.chain[i]), i
        return None, None


def verify(intent: str, executor: Executor, step_id: int|str, votes: int=None, reason='verify') \
        -> dict[str, tuple[str, list[tuple[int, str]]|None]]:
    config = executor.config
    votes = (votes or config.verification_votes)
    system_prompt = executor.prompts.sage_intro

    # issue: (level, [step desc])
    verify_prompt = executor.prompts.sage_check_answer.format(intent=intent)
    prompts = executor.show_conversation_thread(with_extras=True)
    prompts.append((ROLE_ORCHESTRATOR, verify_prompt))
    reports = []
    for i in range(votes):
        n_retries = 0
        prompts_to_be_sent = prompts.copy()
        response: str = ''
        while n_retries < config.max_retries:
            try:
                response = executor.sage_llm.ask(
                    system_prompt,
                    prompts_to_be_sent,
                    reason=reason,
                    step_id=f"{step_id}/{i}#{n_retries}",
                    temperature=config.get_temperature(i + n_retries))
                reports.append(response)
                break
            except Exception as e:
                n_retries += 1
                executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
    return format_error_reports(reports, step_id, executor)


def format_error_reports(reports, step_id, executor) -> dict[str, _t.Tuple[str, list[tuple[int, str]] | None]]:
    config = executor.config
    visible_step_ids = {i for i in range(len(executor.chain)) if executor.chain[i].visible_in_chain}
    all_issues: dict[str, tuple[str, list[tuple[int, str]] | None]] = dict()
    if len(reports) > 0:
        all_issues: dict[str, tuple[str, list[tuple[int, str]] | None]] = dict()
        critic_text = "\n\n".join([
            f"**Critic {i + 1}**:\n{report}\n"
            for i, report in enumerate(reports)
        ])
        prompts = []
        prompts.append((ROLE_ORCHESTRATOR, critic_text))
        prompts.append((ROLE_ORCHESTRATOR, executor.prompts.sage_merge_criticisms))
        prompts_to_be_sent = prompts.copy()
        n_retries = 0
        response: str = ''
        while n_retries < config.max_retries:
            try:
                response = executor.sage_llm.ask(
                    None,
                    prompts_to_be_sent,
                    reason='merge_criticisms',
                    step_id=f"{step_id}#{n_retries}",
                    temperature=config.first_try_temperature)
                all_issues, no_culprit_issues = parse_issue_report(response, len(executor.chain))
                for issue in no_culprit_issues:
                    executor.logger.log(f"removing report {issue} due to no more culprit.")
                    del all_issues[issue]
                for severity, blames in all_issues.values():
                    blames = [blame for blame in (blames if blames is not None else [])
                              if blame[0] in visible_step_ids]
                    if len(blames) == 0:
                        continue
                break
            except Exception as e:
                n_retries += 1
                executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
    return all_issues


def identify_culprits(
        executor: Executor,
        issues: dict[str, tuple[str, list[tuple[int, str]]]]=None, # issue: (level, [(step#, step desc)])
) -> tuple[dict[Step, list[str]], int]:
    # (step#, step desc): [issue desc with level]
    blames: dict[tuple[int, str|None], list[str]] = _defaultdict(list)
    for issue, (level, steps) in issues.items():
        if steps is None or _utils.str_or_blank(level) == '':
            continue
        for step_num, step_desc in steps:
            if 0 <= step_num < len(executor.chain) and step_desc != executor.chain[step_num].step_name:
                mapped = executor.chain[step_num].step_name
                executor.logger.log(f"blamed step#{step_num} desc is actually '{mapped}'")
                step_desc = None
            blames[(step_num, step_desc)].append(f"{level}: {issue}")
    # step: [issue desc with level]
    culprits: dict[Step, list[str]] = _defaultdict(list)
    for (step_num, step_desc), issues_of_step in blames.items():
        if step_num < 0 or step_num >= len(executor.chain):
            executor.logger.log(f"WARNING: ignore out-of-range step [step#{step_num}: {step_desc}]")
            continue
        step = _t.cast(Step, executor.chain[step_num])
        severities = count_issue_severities(issues_of_step)
        if _utils.safe_is_instance(step, (FixableStep, TaoReplyStep)):
            _t.cast(FixableStep, step).record_criticisms(issues_of_step)
        if _utils.safe_is_instance(step, SummarizeStep):
            if severities.fatals > 0:
                # no point of backtracking the summary step as it is the final step
                issues_of_step = [issue.replace("fatal:", "error:") for issue in issues_of_step]
                cls = step.__class__.__name__
                executor.logger.log(f"WARNING: change {severities.fatals} fatal issues for {cls} step to errors")
        elif _utils.safe_is_instance(step, (AskQuestionStep,)):
            if severities.severe_issues > 0:
                # these are not fixable currently but should backtrack only if fatal for these types
                issues_of_step = [issue.replace("error:", "warning:") for issue in issues_of_step]
                cls = step.__class__.__name__
                executor.logger.log(f"WARNING: change {severities.severe_issues} errors "
                                    f"for {cls} step to warnings")
        culprits[step].extend(issues_of_step)
    for i, step in enumerate(executor.chain):
        step = _t.cast(Step, step)
        if _utils.safe_is_instance(step, ConsolidateFileStep):
            if step not in culprits:
                culprits[step] = ["affected: Previous steps has been fixed. Consolidate again"]
    total_errors = 0
    for culprits_issues in culprits.values():
        severities = count_issue_severities(culprits_issues)
        total_errors += severities.severe_issues
    return culprits, total_errors


def repair_or_backtrack(executor: Executor, remedies: dict[Step, list[str]]):
    n_errors_fixed = 0
    too_hard_msg = "Likely, it is too hard. Try to rework this with a step-by-step plan."
    for blamed_step in list(remedies.keys()):
        blames = remedies.get(blamed_step)
        if len(blames) == 0:  # shouldn't happen
            continue
        severities = count_issue_severities(blames)
        if severities.fatals == 0 and _utils.safe_is_instance(blamed_step, FixableStep):
            if blamed_step.retryable(executor.config):
                max_time_out_retries = 2
                for tries in range(max_time_out_retries):
                    try:
                        _t.cast(FixableStep, blamed_step).repair(executor)
                        break
                    except ThisMaybeTooHardError as ex:
                        executor.logger.log_error(str(ex))
                        if severities.severe_issues > 0 and tries >= max_time_out_retries-1:
                            del remedies[blamed_step]
                            raise Backtrack(f"Time-out encountered during repair. {too_hard_msg}",
                                            blame=blamed_step)
                        else: # only warning, ignore
                            break
                n_errors_fixed += severities.severe_issues
                del remedies[blamed_step]
            elif severities.errors > 0:
                executor.logger.log(f"Request backtracking due to max-repairs reached.")
                blames.append(f"We have tried repair a few times. {too_hard_msg}")
                message = '\n\n'.join(blames)
                del remedies[blamed_step]
                raise Backtrack(message, blame=blamed_step)
            else:
                del remedies[blamed_step]
        elif severities.severe_issues > 0:
            executor.logger.log(f"Request backtracking due {severities.severe_issues} severe issues.")
            message = '\n\n'.join(blames)
            raise Backtrack(message, blame=blamed_step)
        else: # warning and not fixable
            del remedies[blamed_step]
    return n_errors_fixed


class AskPythonGenieStep(TaoReplyStep, FixableStep):

    TYPE_SPEC = WILL_ASK_GENIE

    @property
    def step_title(self) -> str:
        return AskPythonGenieStep.TYPE_SPEC

    def __init__(self, *, description: str, role: str, step_name: str|None, **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._n_tries = 0
        self._build(self.description)

    def _build(self, description: str):
        self.description = description
        self._evaluated = False
        self._code_snippets = parse_python_snippets(self.description)
        if len(self._code_snippets) == 0:
            raise ParseError("No python code snippet inside markdown fenced block.")
        pitch = "Run the Python snippet underneath"
        if pitch not in self.description:
            self.description = f"{pitch}:\n\n{self.description}"
        self._original_description = self.description

    def eval_only(self, executor) -> Step | None:
        if self._evaluated:
            return None
        if not self.execute_python_snippet(executor):
            self.repair(executor)
        return None

    def execute_python_snippet(self, executor: Executor) -> bool:
        logger = executor.logger
        try:
            results = executor.ask_genie(self._code_snippets, self)
            block_quote = '`' * 11
            result_markdown = '\n\n'.join(f"""{block_quote}\n{r}\n{block_quote}""" for r in results)
            logger.new_message_section(ROLE_GENIE, executor.step_id(self), collapsible=len(result_markdown) > 1000)
            logger.log(result_markdown)
            logger.close_message_section()
            self.description += f"\n\nResults:\n\n{result_markdown}"
            self._evaluated = True
            return True
        except _utils.PythonGenieRuntimeError as e:
            error_text = f"""error: {str(e.error)} when executing this code snippet."""
            logger.new_message_section(ROLE_GENIE, executor.step_id(self))
            logger.log(error_text)
            logger.close_message_section()
            self._evaluated = True
            self.record_criticisms([f"error: {error_text}"])
            return False

    def repair(self, executor: Executor):
        while self.retryable(executor.config):
            if self._repair(executor):
                return
        raise Backtrack("Python code execution error", blame=self)

    def _repair(self, executor: Executor) -> bool:
        critic_text = self.log_repair(executor)
        prompt_db: PromptDb  = executor.prompts
        prompts = executor.show_conversation_thread(with_header=True, with_extras=True, stop_at=self)
        step_id = executor.step_id(self)
        prompts.append((ROLE_ORCHESTRATOR,
                        prompt_db.tao_fix_issues.format(step_id=step_id, step=self.step_name, critic_text=critic_text)))

        to_be_sent = prompts.copy()
        n_retries = 0
        response: str | None = None
        while n_retries < executor.config.max_retries:
            try:
                response = executor.llm.ask(
                    executor.prompts.tao_intro,
                    to_be_sent,
                    temperature=executor.config.get_temperature(self.n_tries + n_retries),
                    reason="repair",
                    step_id=f"{self.n_tries}#{n_retries}")
                response = _utils.str_or_blank(response)
                response = response.replace(f"{self.TYPE_SPEC}:", "").strip()
                self._build(description=response)
                break
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
        self._n_tries += int(count_issue_severities(self.criticisms).severe_issues > 0)
        self.clear_criticisms()
        return self.execute_python_snippet(executor)

    @property
    def n_tries(self) -> int:
        return self._n_tries

    def reset_retry_count(self):
        self._n_tries = 0


class AskQuestionStep(TaoReplyStep):

    TYPE_SPEC = WILL_ASK_QUESTIONS

    @property
    def step_title(self) -> str:
        return AskQuestionStep.TYPE_SPEC if self._answers is None else 'Tao asked and user replied:'

    def __init__(self, *, description: str, role: str, step_name: str|None, **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self.questions = parse_ordered_list(self.description, at_least_one_list=False)
        if len(self.questions) == 0:
            raise ParseError("Must list questions in a ordered bullet list, even if there is only one question.")
        self._answers: list[str]|None = None
        self._need_consolidate = True # always consolidate once

    def _prepend_step_name_header(self, name):
        pass # do not append at step for asking question

    def eval_only(self, executor) -> Step | None:
        if self._need_consolidate:
            prompts: list[tuple[str, str]] = executor.show_conversation_thread()[:-1]
            self.consolidate_questions(executor, prompts)
        if self._answers is None:
            answers: dict[str, str] = executor.ask_questions(self.questions)
            new_text = ''
            for q, a in answers.items():
                q_lines = q.split('\n')
                q_lines = '\n'.join([f"> {line}\n" for line in q_lines])
                new_text += q_lines + '\n'
                new_text += a.strip() + '\n\n'
            self.description = new_text
            self.role = ROLE_USER # because the user answered the questions
            self._prepend_step_name_header(self.step_name)
            self._answers = answers
            previous = executor.previous_step(self)
            if _utils.safe_is_instance(previous, ExpandableStep):
                previous = _t.cast(ExpandableStep, previous)
                assert executor.chain[-1] is self
                executor.chain.pop(-1)
                self.created_by = None # reset this to reflect that it is no long part of the expanded alternative.
                if len(self.questions) > 0:
                    executor.chain.insert(len(executor.chain)-1, self)
                    previous.reset_choices()
                    if _utils.str_or_blank(self.step_name) != '' and not self.step_name.startswith("ask question"):
                        self._step_name = f"ask questions before {self.step_name}"
                return _t.cast(Step, executor.chain[-1])
        return None

    def consolidate_questions(self, executor: taogpt.Executor,
                              conversation_chain: list[tuple[str, str]]) -> str:
        conversation_chain.append((ROLE_TAO, self.description))
        conversation_chain.append((ROLE_ORCHESTRATOR, executor.prompts.tao_summarize_questions))
        llm: taogpt.LLM = executor.llm
        reply = llm.ask(executor.prompts.tao_intro,
                        conversation_chain, reason='consolidate_questions', temperature=0.0)
        self.description = reply
        self._need_consolidate = False
        return reply


def parse_to_step(response: str, working_on: str = None, init_expansion=False,
                  supported_headers: str='', default_header: str=None) -> Step:
    step_type, step_def = parse_step_type_spec(response, working_on=working_on)
    if step_type is None:
        if default_header is not None:
            step_type = default_header
            step_def = response
        else:
            if supported_headers != '':
                supported_headers = ': ' + supported_headers
            raise ReplyHeaderParseError(
                f"Invalid or missing header. Must start with one of the supported header identifiers: "
                f"{supported_headers}")
    if step_type == DirectAnswerStep.TYPE_SPEC:
        step_class = DirectAnswerStep
    elif step_type == AskQuestionStep.TYPE_SPEC:
        step_class = AskQuestionStep
    elif step_type == AskPythonGenieStep.TYPE_SPEC:
        step_class = AskPythonGenieStep
    elif step_type == ReportErrorStep.TYPE_SPEC:
        step_class = ReportErrorStep
    elif step_type == WriteFileStep.TYPE_SPEC:
        step_class = WriteFileStep
    else:
        step_class = StepByStepPlan
    if step_def is None:
        raise ReplyHeaderParseError(f"Unknown action heading '{step_type}'")
    role = ROLE_TAO
    step: TaoReplyStep = step_class(description=step_def, role=role, step_name=working_on,
                                    init_expansion=init_expansion)
    return step


class ExpandableStep(Step):

    def __init__(self, *, description: str, role: str, step_name: str|None,
                 declare_next_step=True, difficulty: int=5, choices: list[Step] = None, first_expansion: int = 1,
                 incremental_expansion: int = 1, max_expansion: int = 4, **kwargs):
        super().__init__(description=description, role=role, step_name=None, **kwargs)
        self.choices = choices if choices is not None else []
        self.first_expansion = first_expansion
        self.incremental_expansion = incremental_expansion
        self.max_expansion = max_expansion
        self.set_visible_in_chain(False)
        self._ptr = 0
        self._step_name_for_expanded = step_name
        self.declare_next_step = declare_next_step
        self._difficulty = difficulty

    def step_name_tag(self, step_index) -> str:
        return ''

    @property
    def step_name_for_expanded(self) -> str:
        return self._step_name_for_expanded

    def reset_choices(self):
        self.choices.clear()
        self._ptr = 0

    @property
    def step_title(self) -> str:
        return "A step-by-step plan"

    def __repr_local__(self) -> str:
        desc = ','.join([step.__class__.__name__ for step in self.choices])
        return f"[{desc}],ptr={self._ptr}"

    @property
    def _expansion_reason(self) -> str:
        return 'expand_choices'

    def insert_choice(self, new_choice: Step, increase_max=True):
        self.choices.append(new_choice)
        self._ptr += 1
        self.max_expansion += 1

    def expand_choices(self, executor: Executor, upto_branches: int):
        prompt_db: PromptDb  = executor.prompts
        config = executor.config
        system_prompt, base_prompts = self.build_prompts(executor)
        llm = executor.sage_llm if executor.is_init_solving_expansion() \
                                   and config.use_sage_llm_for_initial_expansion else executor.llm
        while len(self.choices) < upto_branches:
            prompts = base_prompts.copy()
            if len(self.choices) > 0:
                prior_plans = [
                    (f"[{PRIOR_PROPOSAL}#{i + 1}] {prior.step_header}\n\n{prior.description}\n\n{prior.extras}\n\n"
                     f"{self._collect_criticism(prior)}")
                    for i, prior in enumerate(self.choices)
                ]
                prior_desc = prompt_db.tao_prior_approaches.format(prior='\n\n---\n'.join(prior_plans))
                prompts.append((ROLE_ORCHESTRATOR, prior_desc))
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            plan: str|None = None
            while n_retries < config.max_retries:
                try:
                    temperature = config.get_temperature(len(self.choices) + n_retries)
                    plan = llm.ask(
                        system_prompt, prompts_to_be_sent,
                        reason=self._expansion_reason,
                        step_id=f"{executor.step_id(self)}/{len(self.choices)}#{n_retries}",
                        temperature=temperature)
                    choice = self.parse_reply(plan, executor)
                    if executor.is_init_solving_expansion() and _utils.safe_is_instance(choice, DirectAnswerStep):
                        _t.cast(DirectAnswerStep, choice).is_final_step = True
                    self.choices.append(choice)
                    break
                except Exception as e:
                    n_retries += 1
                    executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent,
                                                plan, prompt_db.orchestrator_parse_error)

    def _collect_criticism(self, choice: Step) -> str:
        if isinstance(choice, (FixableStep, TaoReplyStep)):
            if len(choice.criticisms) > 0:
                return f"\n---\nCriticisms received for this approach:\n{choice.format_critic_text()}"
        return ''

    def parse_reply(self, plan, executor: Executor) -> Step:
        choice = parse_to_step(plan, working_on=self._step_name_for_expanded,
                               init_expansion=executor.is_init_solving_expansion(),
                               supported_headers=supported_ops(executor.config))
        choice.created_by = self
        choice.part_of = self.part_of
        choice.validate(executor)
        return choice

    def build_prompts(self, executor: Executor) \
            -> _t.Tuple[str, list[_t.Tuple[str, str]]]:
        prompt_db = executor.prompts
        system_prompt = prompt_db.tao_intro
        initial = executor.is_init_solving_expansion()
        base_prompts: list[tuple[str, str]] = executor.show_conversation_thread(with_extras=True)

        config = executor.config
        step_by_step = self.part_of
        if step_by_step is not None:
            plan_id = executor.step_id(step_by_step)
            current_plan = step_by_step.step_name_tag(plan_id)
        elif initial:
            current_plan = '[step#0: task statement]'
        else:
            current_plan = '[not sure which plan, go figure out]'
        if not initial:
            tokens, budget = executor.total_tokens, config.max_tokens
            work_prompt = prompt_db.tao_proceed_to_step.format(plan=current_plan, step=self._step_name_for_expanded)
            frac = tokens / budget
            if frac >= 0.8:
                work_prompt += f"\n\n You've spent {frac:0.0%} of your LLM token budget; be mindful of cost."
            base_prompts.append((ROLE_ORCHESTRATOR, work_prompt))

        base_prompts.append((ROLE_ORCHESTRATOR, prompt_db.tao_template))
        # base_prompts.append((ROLE_ORCHESTRATOR, prompt_db.snippet_next_step.format(step=current_plan)))
        question_asked = len(executor.select_steps(AskQuestionStep, stop_at=self)) > 0
        hint = None
        if initial:
            if not question_asked and config.ask_questions:
                hint = prompt_db.tao_encourage_question
            else:
                hint = "Assess the difficulty of the task and decide which action to take."
        if hint is None:
            if self._ptr == 0 and self._difficulty <= 3: # only advice on first expansion
                    hint = f"This step looks easy! I think you may want to avoid `{HERE_IS_MY_STEP_BY_STEP_PLAN}` approach."
            elif self._difficulty >= 7:
                hint = f"This step looks hard! I think you may want to try `{HERE_IS_MY_STEP_BY_STEP_PLAN}`."
        if hint is not None:
            base_prompts.append((ROLE_ORCHESTRATOR, hint))
        return system_prompt, base_prompts

    def rank_choices(self, executor: Executor, n_existing_choices: int = 0):
        config = executor.config
        question_indices = [i for i in range(n_existing_choices, len(self.choices))
                            if _utils.safe_is_instance(self.choices[i], AskQuestionStep)]
        if len(question_indices) > 1:
            indices = list(range(n_existing_choices, len(self.choices)))
            merged_question_index = self.consolidate_questions(self.choices, indices)
            if merged_question_index >= 0:
                self.choices = [self.choices[i] for i in indices]
                executor.logger.log_debug(f"\n**Questions consolidated, final indices**: {indices}\n\n")
                _t.cast(AskQuestionStep, self.choices[merged_question_index])\
                    .consolidate_questions(executor, executor.show_conversation_thread(stop_at=self))
            if len(self.choices) - n_existing_choices <= 1:
                return # nothing left to rank, skip ranking
        prompt_db: PromptDb  = executor.prompts
        system_prompt = prompt_db.sage_intro

        prompts = executor.show_conversation_thread(except_step=self, stop_at=self)

        work_prompt = f"[at step#{executor.step_id(self)}: {self.step_name}]\n\n"
        work_prompt += prompt_db.sage_rank_choices.format(
            choices='\n\n---\n\n'.join([
                f"[Proposal {i+1}] {plan.step_header}\n\n{plan.description}\n\n{plan.extras}"
                for i, plan in enumerate(self.choices)
            ])
        )

        prompts.append((ROLE_ORCHESTRATOR, work_prompt))
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.sage_rank_instructions))
        rankings_one_based: dict[int, float] = _defaultdict(lambda: 0.0)
        ranking_types = {i+1: plan.step_title for i, plan in enumerate(self.choices)}
        n_success = 0
        response: str|None = None
        while n_success < config.votes:
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            while n_retries < config.max_retries:
                try:
                    response = executor.sage_llm.ask(
                        system_prompt, prompts_to_be_sent,
                        reason='rank_choices',
                        step_id=f"{executor.step_id(self)}/{n_success}#{n_retries}",
                        temperature=config.get_temperature(n_success) + n_retries)
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
        executor.logger.log_debug(f"\n**Sorted indices**: {indices} **scores**:\n{final_score_repr}\n\n")
        if len(indices) == 0:
            raise Backtrack(f"No valid plan found for this step.", executor.previous_step(self))
        if n_existing_choices is not None and n_existing_choices > 0:
            indices = list(range(n_existing_choices)) + indices
        self.choices = [self.choices[i] for i in indices]

    @staticmethod
    def consolidate_questions(choices, indices: list[int]) -> int:
        question_indices = [i for i in indices if _utils.safe_is_instance(choices[i], AskQuestionStep)]
        if len(question_indices) > 1:
            merged_question: AskQuestionStep = choices[question_indices[0]]
            for i in range(len(question_indices) - 1, 0, -1):  # all except first in reversed order
                question_index = question_indices[i]
                merged_question.description += '\n\n---\n\n' + choices[question_index].description
                indices.remove(question_index)
            return question_indices[0]
        return -1

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
                raise ParseError(f"Choice#{dupe} is of type \"{ranking_types[dupe]}\" but "
                                 f"Choice#{original} is of type \"{ranking_types[original]}\". "
                                 f"They cannot be duplicates of each other.")
            else:
                scores[dupe] = -_math.fabs(scores[original])

    def retryable(self, config):
        return len(self.choices) < config.max_search_expansion \
            or self._ptr < len(self.choices) - 1 # consume existing expansions

    def backtrack(self, executor: Executor, backtrack: Backtrack | None):
        self._ptr += 1
        if self._ptr < self.max_expansion:
            return
        # should not happen due to the retryable(), this is just defensive programming
        raise Backtrack("No more alternative", blame=executor.previous_step(self))

    def eval_only(self, executor: Executor) -> Step | None:
        old_length = len(self.choices)
        config = executor.config
        first_expand = executor.is_init_solving_expansion()
        logger = executor.logger
        if self._ptr >= (len(self.choices) - 1) and old_length < self.max_expansion:
            incr = self.first_expansion if old_length == 0 else self.incremental_expansion
            logger.log_debug(f"{executor.step_id(self)}/'{self.step_name}'"
                             f" expanding from {len(self.choices)} by {incr} "
                             f"to: {self._ptr + incr}. max={self.max_expansion}")
            self.expand_choices(executor, upto_branches=self._ptr + incr)
        if len(self.choices) - old_length > 1:
            logger.log_debug(f"{executor.step_id(self)}/'{self.step_name}' ranking choices from {old_length}")
            self.rank_choices(executor, n_existing_choices=old_length)
        if first_expand and config.pause_after_initial_solving_expansion:
            raise Pause("Pause after initial solving expansion", self)
        if len(self.choices) == 0 or self._ptr >= len(self.choices):
            raise Backtrack('No viable options.', blame=executor.previous_step(self))
        return self.choices[self._ptr]


class ProceedStep(ExpandableStep):
    @staticmethod
    def create_proceed_step(executor: Executor, next_step_desc: str, step_by_step: StepByStepPlan, difficulty: int):
        config = executor.config
        next_step = ProceedStep(
            description='',
            role=ROLE_ORCHESTRATOR,
            first_expansion=config.first_expansion,
            max_expansion=config.max_search_expansion,
            declare_next_step=not step_by_step.sequential,
            difficulty=difficulty,
            step_name=next_step_desc)
        next_step.part_of = step_by_step
        next_step.created_by = step_by_step.created_by
        return next_step

    @property
    def step_title(self) -> str:
        return ""

    @property
    def _expansion_reason(self) -> str:
        return "proceed_to_next"

    @property
    def visible_in_summarization(self) -> bool:
        return False


class NextStep(Step):

    @property
    def step_title(self) -> str:
        return ""

    @property
    def visible_in_summarization(self) -> bool:
        return False

    def direct_advance(self, executor) -> Step | None:
        parent_plan, plan_id = StepByStepPlan.find_last_step_by_step(executor, before=self)
        if parent_plan is None:
            return proceed_next(self, executor, NextStepDesc(None, None, True, "all done", None))
        assert parent_plan is not None
        assert plan_id is not None
        next_step = parent_plan.advance_to_next_step()
        if next_step is not None:
            return ProceedStep.create_proceed_step(executor, next_step[1], parent_plan, next_step[2])
        if parent_plan.sequential: # we are done with the parent plan, summarize
            gp, gp_id = StepByStepPlan.find_last_step_by_step(executor, before=parent_plan)
            next_step_name = None
            difficulty = 5
            while gp is not None and gp.sequential:
                next_step = gp.advance_to_next_step(trial=True)
                if next_step is None: # this ancestor is done
                    gp, gp_id = StepByStepPlan.find_last_step_by_step(executor, before=gp)
                    continue
                next_step_name = next_step[1]
                difficulty = next_step[2]
                break
            if gp is None: # reach root
                next_step_name = 'all done'
            if next_step_name is not None:
                next_step_spec = NextStepDesc(
                    target_plan_id=plan_id,
                    target_plan_tag=parent_plan.step_name_tag(plan_id),
                    target_plan_done=True,
                    next_step_desc=next_step_name,
                    plan_of_next_step=gp.step_name_tag(gp_id) if gp is not None else None)
                return proceed_next(self, executor, next_step_spec, difficulty)
            # else we need to ask
        return None

    def eval_only(self, executor) -> Step | None:
        if executor.config.optimized_sequential_next_step:
            next_step = self.direct_advance(executor)
            if next_step is not None:
                return next_step

        prompt_db = executor.prompts
        system_prompt = prompt_db.tao_intro
        prompts = executor.show_conversation_thread(with_header=True, with_extras=True)
        last_step = _t.cast(Step, executor.chain[-2])
        last_step_tag = last_step.step_name_tag(executor.step_id(last_step))
        parent_plan, plan_id = StepByStepPlan.find_last_step_by_step(executor, before=self)
        if parent_plan is None:
            parent_plan = executor.select_steps(PresentTaskStep)[-1]
            plan_id = executor.step_id(parent_plan)
        parent_tag = parent_plan.step_name_tag(plan_id)
        snippet_next_step = prompt_db.snippet_next_step.format(step=parent_tag)
        tao_next_step = prompt_db.tao_next_step.format(
            last_step=last_step_tag,
            at_plan=parent_tag,
            snippet_next_step=snippet_next_step,
            snippet_report_errors=prompt_db.snippet_report_errors)
        prompts.append((ROLE_ORCHESTRATOR, tao_next_step))
        n_retries = 0
        response: str|None = None
        to_be_sent = prompts.copy()
        while n_retries < executor.config.max_retries:
            try:
                response = executor.llm.ask(
                    system_prompt, to_be_sent,
                    reason='next_step',
                    step_id=f"{executor.step_id(self)}#{n_retries}",
                    temperature=executor.config.get_temperature(n_retries))
                proceed_step = self.parse_reply(response, executor)
                self.set_visible_in_chain(False)
                return proceed_step
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            prompt_db.orchestrator_parse_error)
        return None # unreachable

    def parse_reply(self, plan: str, executor: Executor) -> Step:
        decision, details = parse_next_step_reply(plan)
        assert decision is not None
        assert details is not None
        if decision == NEXT_I_WANT_TO_WORK_AT:
            next_step_spec = _t.cast(NextStepDesc, details)
            validate_next_step_spec(executor, next_step_spec, no_spec_ok=False)
            return proceed_next(self, executor, next_step_spec, difficulty=next_step_spec.difficulty)
        else:
            step = parse_to_step(_t.cast(str, details), working_on=None,
                                 supported_headers=supported_ops(executor.config),
                                 default_header=REPORT_ERROR)
            if not _utils.safe_is_instance(step, ReportErrorStep):
                raise ParseError(f"Expecting either next step declaration or error report with `{REPORT_ERROR}:`")
            step.validate(executor)
            return step


def validate_next_step_spec(executor: Executor, next_step_spec: NextStepDesc,
                            current_plan: StepByStepPlan=None, no_spec_ok=True, nullify_next_step_if_not_in_gp=True):
    if next_step_spec is None:
        if not no_spec_ok:
            raise ParseError(f"No next step specification.")
        return
    current_plan_id: int|None
    if current_plan is None:
        current_plan, current_plan_id = StepByStepPlan.find_last_step_by_step(executor)
    else:
        current_plan_id = executor.step_id(current_plan)

    if (current_plan is not None
            and next_step_spec.target_plan_id is not None
            and next_step_spec.target_plan_id != current_plan_id):
        raise ParseError(f"Need to know if `done with {current_plan.step_name_tag(current_plan_id)}` is true or false "
                         f"but got key `{next_step_spec.target_plan_tag}`.")

    if next_step_spec.target_plan_id is not None and next_step_spec.target_plan_done and next_step_spec.next_step_desc:
        first_step_by_step = -1
        for i in range(len(executor.chain)):
            if _utils.safe_is_instance(executor.chain[i], StepByStepPlan):
                first_step_by_step = i
                break
        if first_step_by_step == next_step_spec.target_plan_id and not next_step_spec.is_final_step:
            raise ParseError(f"You claim the root plan {next_step_spec.target_plan_tag} is done but still want to "
                             f"work at a next step. That is contradictory.")

    if next_step_spec.next_step_desc is not None and current_plan_id is not None:
        _, grandparent_plan_id = StepByStepPlan.find_last_step_by_step(executor, before=current_plan_id)
        actual_plan_step = StepByStepPlan.find_step_from_chain(executor, next_step_spec.next_step_desc)
        actual_plan_id = executor.step_id(actual_plan_step) if actual_plan_step is not None else None
        if actual_plan_id is not None and actual_plan_id != grandparent_plan_id and nullify_next_step_if_not_in_gp:
            # next step belongs to a higher level plan, LLM may be mistaken, will ask again later
            next_step_spec.next_step_desc = None
        elif actual_plan_id is None:
            executor.logger.log(f"Next step {next_step_spec.next_step_desc} is unplanned")
        # else the next step is listed in the GP


def validate_step_id(step_id: int, executor: Executor, key=''):
    if key != '':
        key = f"{key} "
    if step_id < 0 or step_id >= len(executor.chain):
        raise ParseError(f"{key} step number/id must be between 0 and {len(executor.chain)-1}")


def reset_fix_counts(executor: Executor):
    for step in executor.chain:
        _t.cast(Step, step).reset_retry_count()


class SummarizeStepABC(DirectAnswerStep, metaclass=ABCMeta):

    def __init__(self, *, step_name: str, role=ROLE_TAO, n_verifications=3, **kwargs):
        super().__init__(description='', role=role, step_name=step_name, is_final_step=False, **kwargs)
        self._n_verifications = n_verifications
        self._evaluated = False
        self._pending_culprits: dict[Step, list[str]]|None = None
        self._pending_error_count: int = 0

    def _process_next_step(self):
        super()._process_next_step()
        self._next_step = None

    @abstractmethod
    def merge_consolidated_files(self, executor):
        pass

    @abstractmethod
    def merge_steps(self, executor):
        pass

    @abstractmethod
    def get_instruction(self, executor):
        pass

    @abstractmethod
    def get_summarize_steps(self, executor):
        pass

    @abstractmethod
    def get_verification_votes(self, config):
        pass

    def eval_only(self, executor) -> Step | None:
        if self._evaluated:
            return None
        if not executor.config.summarize:
            self._evaluated = True
            return None
        reset_fix_counts(executor)
        instr = self.get_instruction(executor)
        involved_steps = self.get_summarize_steps(executor)
        prompt_db = executor.prompts
        prompts = executor.show_conversation_thread(with_extras=True, stop_at=involved_steps[-1])
        prompts.append((ROLE_ORCHESTRATOR, instr))

        n_retries = 0
        response: str|None = None
        to_be_sent = prompts.copy()
        while n_retries < executor.config.max_retries:
            try:
                self.description = executor.llm.ask(
                    prompt_db.tao_intro, to_be_sent,
                    reason=self.__class__.__name__,
                    step_id=f"{executor.step_id(involved_steps[0])}#{n_retries}",
                    temperature=0.0)
                self.validate(executor)
                for step in involved_steps:
                    tag = step.step_name_tag(executor.step_id(step)).strip()
                    if len(tag) > 0:
                        self.description = self.description.replace(tag, "-")
                break
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            prompt_db.orchestrator_parse_error)
        self.merge_steps(executor)
        self.merge_consolidated_files(executor)
        self.clear_criticisms()
        self._evaluated = True
        return None

    def verify_and_fix(self, intent: str, executor: Executor) -> _t.Self|None:
        if self._n_verifications <= 0:
            reset_fix_counts(executor)
            return None
        votes = self.get_verification_votes(executor.config)
        if self._pending_culprits is None:
            # concern: (issue, [step desc])
            all_issues = verify(intent, executor, executor.step_id(self), votes=votes)
            if len(all_issues) == 0:
                self._pending_error_count = 0
                self._n_verifications = 0 # no need for further check
                reset_fix_counts(executor)
                return None
            self._pending_culprits, self._pending_error_count = identify_culprits(executor, all_issues)
        while self._pending_culprits is not None and len(self._pending_culprits) > 0:
            executor.check_token_usages()
            try:
                repair_or_backtrack(executor, self._pending_culprits)
            except RedoFinalCheck as e:
                executor.logger.log(str(e))
                self._pending_culprits, self._pending_error_count = None, 0
                all_issues = verify(intent, executor, executor.step_id(self), votes=votes)
                if len(all_issues) == 0:
                    self._n_verifications = 0 # no need for further check
                    self._evaluated = False
                    break
                self._pending_culprits, self._pending_error_count = identify_culprits(executor, all_issues)
        self._pending_culprits = None
        if self._pending_error_count > 0:
            self._pending_error_count = 0
            self._n_verifications -= 1
            return self # need to check final answer again
        self._pending_error_count = 0
        self._n_verifications = 0 # no need for further check
        self._evaluated = False
        return None


class SummarizePartialStep(SummarizeStepABC):

    def __init__(self, *, step_name: str, shadowing: list[Step], role=ROLE_TAO, **kwargs):
        super().__init__(step_name=step_name, role=role, n_verifications=3, **kwargs)
        self._shadowing: list[Step]= shadowing

    def eval(self, executor: Executor) -> Step | None:
        if self._n_verifications > 0:
            visible_steps = [step for step in self._shadowing if step.visible_in_chain]
            from_step_tag = visible_steps[0].step_name_tag(executor.step_id(visible_steps[0]))
            to_step_tag = visible_steps[-1].step_name_tag(executor.step_id(self._shadowing[-1]))
            result = self.verify_and_fix("Is everything correct between {from_step_tag} and {to_step_tag}?".format(
                from_step_tag=from_step_tag, to_step_tag=to_step_tag), executor)
            if result is not None:
                return result
        self._n_verifications = 0
        return self.eval_only(executor)

    def merge_steps(self, executor):
        self.created_by = self._shadowing[0].created_by
        self.part_of = self._shadowing[0].part_of
        executor.remove_steps(from_step=self._shadowing[0], to_step=self._shadowing[-1])
        for step in self._shadowing:
            if _utils.safe_is_instance(step, WriteFileStep):
                executor.chain.insert(len(executor.chain)-1, step)

    def merge_consolidated_files(self, executor):
        pass

    def get_instruction(self, executor: Executor):
        from_step_tag = self._shadowing[0].step_name_tag(executor.step_id(self._shadowing[0]))
        to_step_tag = self._shadowing[-1].step_name_tag(executor.step_id(self._shadowing[-1]))
        return executor.prompts.tao_summarize_partial.format(from_step=from_step_tag, to_step=to_step_tag)

    def get_summarize_steps(self, executor: Executor):
        return self._shadowing

    def get_verification_votes(self, config: Config):
        return 1


class SummarizeStep(SummarizeStepABC):
    TYPE_SPEC = SUMMARIZE_FINAL_ANSWER

    def __init__(self, *, role=ROLE_TAO, n_verifications=3, **kwargs):
        super().__init__(step_name=SUMMARIZE_FINAL_ANSWER, role=role, n_verifications=n_verifications, **kwargs)
        self._reset_chain_retry_count = False

    @property
    def step_title(self) -> str:
        return ''

    def eval(self, executor: Executor) -> Step | None:
        if self._n_verifications > 0:
            result = self.verify_and_fix('Is the solution correct?', executor)
            if result is not None:
                return result
        self._n_verifications = 0
        next_step = self.eval_only(executor)
        if next_step is None:
            next_step = Idle()
        return next_step

    def verify_and_fix(self, intent: str, executor: Executor) -> _t.Self | None:
        return super().verify_and_fix(intent, executor)

    def merge_consolidated_files(self, executor):
        consolidate_file_steps = consolidate_updated_files(self.get_summarize_steps(executor))
        for consolidate_file_step in consolidate_file_steps:
            if not consolidate_file_step.evaluated:
                executor.enqueue(consolidate_file_step)

    def merge_steps(self, executor):
        pass

    def get_instruction(self, executor: Executor):
        return executor.prompts.tao_summarize

    def get_summarize_steps(self, executor: Executor):
        my_index = executor.step_id(self)
        return executor.chain[:my_index]

    def get_verification_votes(self, config: Config):
        return config.verification_votes


def proceed_next(current_step: Step, executor: Executor, next_step_spec: NextStepDesc, difficulty: int=5) -> Step:
    current_index = executor.step_id(current_step)
    assert current_index == len(executor.chain)-1

    if next_step_spec.is_final_step:
        return _t.cast(Step, executor.summarize_final_answer())
    if next_step_spec.target_plan_id is not None and next_step_spec.target_plan_done:
        finished_plan = _t.cast(Step, executor.chain[next_step_spec.target_plan_id])
        partial = _t.cast(list[Step], executor.chain[next_step_spec.target_plan_id:current_index + 1])
        summarize = SummarizePartialStep(step_name=finished_plan.step_name, shadowing=partial)
        if _utils.safe_is_instance(finished_plan.created_by, ExpandableStep):
            _t.cast(ExpandableStep, finished_plan.created_by).insert_choice(summarize, increase_max=True)
        return summarize

    matched_plan, _ = StepByStepPlan.find_last_step_by_step(executor, before=current_index)
    if matched_plan.sequential and executor.config.optimized_sequential_next_step:
        next_step = matched_plan.advance_to_next_step()
        if next_step is not None:
            return ProceedStep.create_proceed_step(executor, next_step[1], matched_plan, difficulty)
        # unknown or beyond plan
    return ProceedStep.create_proceed_step(executor, next_step_spec.next_step_desc, matched_plan, difficulty)


def count_file_updates(chain: list[StepABC], stop_at_step: StepABC=None) -> dict[str, int]:
    files = dict()
    for step in chain:
        if stop_at_step is step:
            break
        for path, file in step.collected_files.items():
            if path in files:
                files[path] += 1
            else:
                files[path] = 1
    return files


def consolidate_updated_files(steps: list[StepABC]):
    steps = _t.cast(list[Step], steps)
    files = GeneratedFile.collect_files(steps)
    file_updates = count_file_updates(steps)
    consolidate_file_steps = []
    for file, content in files.items():
        if file_updates.get(file, 0) > 1:
            consolidate_file_step = ConsolidateFileStep(
                role=ROLE_TAO, file_name=file, keep_content_even_if_same=True, between=steps)
            consolidate_file_steps.append(consolidate_file_step)
    return consolidate_file_steps


class PresentTaskStep(FixableStep):

    def __init__(self, *, description: str, role: str, step_name='task statement', **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._n_tries = 1 # already evaluated once since the description is the result

    @property
    def step_title(self) -> str:
        return ""

    def retryable(self, config):
        return True # always retryable

    @property
    def n_tries(self) -> int:
        return self._n_tries

    def reset_retry_count(self):
        self._n_tries = 0

    def repair(self, executor: Executor):
        errors = [f"{i+1}. Please clarify this concern of your task: {issue}"
                  for i, issue in enumerate(self.criticisms)]
        if len(errors) == 0:
            return
        questions = '\n'.join(errors)
        ask_step = AskQuestionStep(description=questions, role=ROLE_TAO, step_name="clarify issues")
        ask_step.created_by = self
        ask_step._need_consolidate = False
        my_index = executor.step_id(self)
        executor.chain.insert(my_index+1, ask_step)
        ask_step.eval_only(executor)
        self._n_tries += int(count_issue_severities(self.criticisms).severe_issues > 0)
        raise RedoFinalCheck(self.step_name)


def collect_all_versions(chain: list[Step], file: str, with_steps=False) \
        -> list[GeneratedFile|tuple[GeneratedFile, Step]]:
    all_versions = []
    for step in chain:
        files = step.collected_files
        if file in files:
            g_file = files[file]
            all_versions.append((g_file, step) if with_steps else g_file)
    return all_versions


def collect_all_snippets(chain: list[Step], file: str) -> tuple[list[tuple[str, str]], str]:
    markdown_blocks = []
    content_type = ''
    for g_file in collect_all_versions(chain, file):
        markdown_blocks.append((g_file.markdown_snippet, g_file.content))
        content_type = g_file.content_type
    return markdown_blocks, content_type


def rolling_diff_file_consolidate(executor: Executor, file: str,
                                  chain: list[Step]=None, critic_text: str=None) -> GeneratedFile:
    import os

    snippets: list[tuple[GeneratedFile, Step]] = []
    for i, (g_file, step) in enumerate(collect_all_versions(chain, file, with_steps=True)):
        snippets.append((g_file, step))
    if len(snippets) == 1:
        return snippets[0][0]
    merge_file = f'/tmp/taogpt_manual_merge.{os.path.basename(file)}.md'
    content_type = snippets[0][0].content_type

    version_count = 0
    with open(merge_file, 'w') as f:
        while version_count < 2:
            f.write(f"total edits: {len(snippets)}\n\n")
            f.write(f"### update#{version_count} {snippets[version_count][1].step_name}\n")
            f.write(f"{snippets[version_count][1].description}\n\n")
            f.write(snippets[version_count][0].markdown_snippet)
            f.write("\n\n")
            version_count += 1

    failed = False
    actual_merges = 0
    prompt_db = executor.prompts
    while len(snippets) > 1:
        collecting = snippets[:2] # 2 snippets at a time
        snippets = snippets[2:]
        if collecting[0][0].content == collecting[-1][0].content:
            with open(merge_file, 'a') as f:
                f.write("\nThe next edit is identical to the last result. skipping.\n")
            executor.logger.log("The next edit is identical to the last result. skipping.")
            snippets.insert(0, collecting[-1])
            continue
        executor.logger.log(f"Rolling consolidation. starting snippets: {len(snippets)}, "
                            f"text length: {len(collecting[0][0].content)}")
        prompts = []
        original: GeneratedFile
        snippet_text = "\n\n".join(f"**Update#{k+1}: {step.step_name}**\n{step.description}"
                                   for k, (original, step) in enumerate(collecting))
        diffs = _unified_diff(collecting[0][0].content.split('\n'), collecting[1][0].content.split('\n'),
                              fromfile='Update#1', tofile='Update#2', lineterm='')
        diffs = '\n'.join(line for line in diffs if not line.startswith('-'))

        prompts.append((ROLE_ORCHESTRATOR, snippet_text))
        if critic_text is not None and len(critic_text) > 0:
            prompts.append((ROLE_ORCHESTRATOR, f"Prior issues trying this:\n\n{critic_text}"))
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.tao_ensure_updated_file_integrity.format(
            file_name=file, diffs=diffs)))
        for n_try in range(2):
            try:
                response = executor.llm.ask(
                    prompt_db.tao_intro,
                    prompts,
                    reason='rolling_file_consolidate',
                    step_id=f"{file}/{actual_merges}")
                content_type, content, snippet, desc = gather_file_contents(response)
                updated = GeneratedFile(content_type, content, desc)
                snippets.insert(0, (updated, collecting[-1][1]))
                actual_merges += 1
                with open(merge_file, 'a') as f:
                    f.write(f"**diffs**:\n")
                    f.write(f"""
        `````
        {diffs}
        `````
        
        """)
                    f.write(f"### merged:\n")
                    f.write(snippets[0][0].markdown_snippet)
                    f.write("\n\n")
                    if len(snippets) > 1:
                        f.write(f"### update#{version_count} {snippets[1][1].step_name}\n")
                        f.write(snippets[1][1].description)
                        f.write("\n\n")
                        f.write(snippets[1][0].markdown_snippet)
                        f.write("\n\n")
                        version_count += 1
                failed = False
                break
            except ThisMaybeTooHardError as ex:
                executor.logger.log_error(str(ex))
                if n_try > 0:
                    with open(merge_file, 'a') as f:
                        for edit, step in snippets: # ensured all versions written
                            f.write(f"### update#{version_count} {step.step_name}\n")
                            f.write(f"{step.description}\n\n")
                            f.write(edit.markdown_snippet)
                            f.write("\n\n")
                            version_count += 1
                failed = True
        if failed:
            break

    if (actual_merges == 0 or not executor.config.review_file_merges) and not failed and len(snippets) > 0:
        return snippets[-1][0]
    with open(merge_file, 'a') as f:
        f.write(f"**NOTE:**: Merge all into one markdown fenced block and nothing else.\n")
    question = f"Please edit `{merge_file}` to merge manually. Reply 'OK' when done or 'cancel' to stop."
    user_answer = executor.ask_questions([question])[question].lower().strip()
    if user_answer == 'ok':
        with open(merge_file, 'r') as f:
            response = f.read().strip()
            lines = response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:-1]
            response = "\n".join(lines)
            return GeneratedFile(content_type, response, '')
    else:
        raise KeyboardInterrupt(f"User gave unexpected answer: {user_answer}")
