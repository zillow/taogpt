from __future__ import annotations
import typing as _t
from _collections import defaultdict as _defaultdict
import math as _math
import json as _json
from abc import abstractmethod

import taogpt
import taogpt.llm_model
from . import StepABC, Backtrack, Pause, Executor, Config, GeneratedFile
from .parsing import *
from .constants import *
import taogpt.utils as _utils
from .utils import safe_subn
from taogpt.prompts import PromptDb


def add_files_to_prompts(executor, prompts, role=ROLE_ORCHESTRATOR) -> dict[str, GeneratedFile]:
    file_contents = ''
    files = GeneratedFile.collect_files(executor.chain)
    for path, file in files.items():
        file_contents += f"### FILE: {path}\n\n{file.markdown_snippet}\n\n"
    if file_contents != '':
        prompts.append((role, f'Current files we have so far:\n\n{file_contents}'))
    return files


class Step(StepABC):

    def __init__(self, *, description: str, role: str, step_name: str|None, **_):
        super().__init__(description=description, role=role, step_name=step_name)
        self._part_of: StepByStepPlan|None = None
        self._created_by: Step|None = None

    @property
    def step_title(self) -> str:
        return ''

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
            content += f"# {self.step_title}\n" if len(self.step_title) > 0 else ""
            tag = self.step_name_tag(step_index)
            content += f"{tag}\n\n"
        content += self.description
        content += extra_content
        return [(self.role, content)]

    def step_name_tag(self, step_index):
        step_name = _utils.str_or_blank(self.step_name)
        if step_name == '':  # no name, use numeric index
            step_name = f"step {step_index}"
        tag = f"[at step#{step_index}: {step_name}]"
        return tag

    def retryable(self, config: Config):
        return False

    def eval(self, executor: Executor) -> Step | None:
        returned = self.eval_only(executor)
        return returned

    def eval_only(self, executor: Executor) -> Step | None:
        return None

    def validate(self, executor: Executor):
        pass

class RedoFinalCheck(RuntimeError):
    """
    This error is used internally to signal the repair mechanism to discard all previous criticisms and perform the
    final check again.
    """

    def __init__(self, step: Step):
        super().__init__(f"Step {step.step_name} requests redo the final check")



class FixableStep(Step):

    def retryable(self, config):
        return self.n_tries < config.max_repairs

    @property
    @abstractmethod
    def n_tries(self) -> int:
        pass

    @abstractmethod
    def record_criticisms(self, criticisms: list[str]):
        pass

    @property
    @abstractmethod
    def criticisms(self) -> list[str]:
        pass

    def format_critic_text(self):
        all_criticisms = [f'* {c}' if not c.startswith('* ') else c for c in self.criticisms]
        return "\n".join(all_criticisms)

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
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._criticisms: list[str] = list()

    def record_criticisms(self, additional_criticisms: list[str]):
        self._criticisms.extend(additional_criticisms)

    @property
    def criticisms(self) -> list[str]:
        return self._criticisms


class DirectAnswerStep(TaoReplyStep, FixableStep):
    TYPE_SPEC = MY_THOUGHT

    @property
    def step_title(self) -> str:
        return DirectAnswerStep.TYPE_SPEC

    def __init__(self, *, description: str, role: str, step_name: str, is_final_step=False, **kwargs):
        description = at_step_re.sub('', description, count=1).strip()
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self.is_final_step = is_final_step
        self._n_tries = 1 # already evaluated once since the description is the result
        self._previous_contents: list[tuple[str, dict]] = []
        self._files: dict[str, taogpt.GeneratedFile] = dict()
        self.next_step: NextStepDesc|None = None
        self.build(description)

    def build(self, description: str, next_step: NextStepDesc=None):
        self.description = re.sub(rf"#+\s+{NEXT_I_WANT_TO_WORK_AT}", f"### {NEXT_I_WANT_TO_WORK_AT}:",
                                  description, 1)
        sections: dict[str, str] = parse_sections(self.description)
        extracted_contents = gather_file_contents(sections, pop_file_sections=True)
        self._files = {
            file_path: taogpt.GeneratedFile(content_type, content, snippet, desc)
            for file_path, (content_type, content, snippet, desc) in extracted_contents.items()
        }
        next_step_section = sections.pop(NEXT_I_WANT_TO_WORK_AT, None)
        if next_step_section is not None:
            self.next_step = parse_next_step_spec(next_step_section)
        else:
            self.next_step = next_step
        if self.is_final_step:
            self.next_step.next_step_desc = "all done"
            self.next_step.target_plan_id = None
        reconstructed = [f"# {heading}\n{content}" for heading, content in sections.items()]
        self.description = '\n\n'.join(reconstructed)
        self.description = re.sub(rf"# {FREE_TEXT}\n+", "", self.description, flags=re.IGNORECASE)

    def validate(self, executor: Executor):
        super().validate(executor)
        validate_next_step_spec(executor, self.next_step, nullify_next_step_if_not_in_gp=True)

    @property
    def n_tries(self) -> int:
        return self._n_tries

    def repair(self, executor: Executor):
        self._previous_contents.append((self.description, self._files.copy()))
        critic_text = self.log_repair(executor)

        prompt_db: PromptDb  = executor.prompts
        prompts = executor.show_conversation_thread(with_header=True, with_extras=True, stop_at=self)
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.snippet_notes_for_files))
        step_id = executor.step_id(self)
        instr = prompt_db.tao_fix_issues.format(step_id=step_id, step=self.step_name, critic_text=critic_text)
        prompts.append((ROLE_ORCHESTRATOR, instr))

        to_be_sent = prompts.copy()
        n_retries = 0
        response: str | None = None
        while n_retries < executor.config.max_retries:
            try:
                response = executor.llm.ask(
                    executor.prompts.tao_intro,
                    to_be_sent,
                    temperature=0.0 if n_retries == 0.0 else executor.config.alternative_temperature,
                    reason=f"fix",
                    step_id=f"{len(self._criticisms)}#{n_retries}")
                response = _utils.str_or_blank(response)
                if not response.startswith(f"# {DirectAnswerStep.TYPE_SPEC}"):
                    response = f"# {DirectAnswerStep.TYPE_SPEC}\n\n" + response
                dummy = parse_to_step(response, executor.config, working_on=self.step_name,
                                      limit_to={DirectAnswerStep})
                dummy.validate(executor)
                self.build(f"{dummy.description}\n\n{dummy.extras}", next_step=self.next_step)
                break
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
        self._criticisms.clear()
        self._n_tries += 1

    def eval_only(self, executor: Executor) -> Step | None:
        if self.next_step is not None:
            return proceed_next(self, executor, self.next_step)
        return None

    @property
    def collected_files(self) -> dict[str, GeneratedFile]:
        return self._files

    @property
    def extras(self) -> str:
        file_contents = ''
        for path, file in self.collected_files.items():
            file_contents += f"\n### FILE: {path}\n\n{file.markdown_snippet}\n\n"
        return file_contents


class FinalizeFileStep(DirectAnswerStep):
    TYPE_SPEC = "CONSOLIDATE_FILE"

    def __init__(self, *, description: str, role: str, file_name: str, keep_content_even_if_same=False, **kwargs):
        super().__init__(description=description, role=role, step_name=f"finalizing file {file_name}", **kwargs)
        self._file_name = file_name
        self.keep_content_even_if_same = keep_content_even_if_same
        self._evaluated = False

    @property
    def step_title(self) -> str:
        return FinalizeFileStep.TYPE_SPEC

    def retryable(self, config: Config):
        return True # always retryable

    def eval_only(self, executor) -> Step | None:
        if self._evaluated:
            return None
        prompt_db = executor.prompts
        system_prompt = prompt_db.tao_intro
        except_me = self if len(self.criticisms) == 0 else None
        prompts = executor.show_conversation_thread(with_header=True, with_extras=True,
                                                    except_step=except_me, stop_at=self)
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.snippet_notes_for_files))
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.tao_ensure_updated_file_integrity.format(
            file_name=self._file_name)))
        if len(self.criticisms) > 0:
            critic_text = self.format_critic_text()
            step_id = executor.step_id(self)
            instr = prompt_db.tao_fix_issues.format(step_id=step_id, step=self.step_name, critic_text=critic_text)
            prompts.append((ROLE_ORCHESTRATOR, instr))

        last_version = GeneratedFile.collect_files(executor.chain, self)[self._file_name]
        n_retries = 0
        response: str|None = None
        to_be_sent = prompts.copy()
        while n_retries < executor.config.max_retries:
            try:
                response = executor.llm.ask(
                    system_prompt, to_be_sent,
                    reason=self.TYPE_SPEC,
                    step_id=f"{executor.step_id(self)}#{n_retries}",
                    temperature=0.0 if n_retries == 0 else executor.config.alternative_temperature,
                    log_request=n_retries == 0)
                self.build(response)
                if len(self.collected_files) != 1 or self._file_name not in self.collected_files:
                    raise ParseError(f"You should respond (only) with the complete content of file {self._file_name}")
                if self.keep_content_even_if_same:
                    pass
                elif self.collected_files[self._file_name].content == last_version.content and \
                    self.collected_files[self._file_name].content_type == last_version.content_type:
                    self.collected_files.clear()
                    self.description = f"The last version of file `{self._file_name}` looks good. No change."
                else:
                    self.description = f"The file `{self._file_name}` has been reconciled with prior edits."
                self._evaluated = True
                self.next_step = None # shouldn't happen
                return None
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            prompt_db.orchestrator_parse_error)
        return None

    def repair(self, executor: Executor):
        self._previous_contents.append((self.description, self._files))
        self.log_repair(executor)
        self._evaluated = False
        self.eval_only(executor)
        self.criticisms.clear()
        self._n_tries += 1


class GiveUpStep(TaoReplyStep):
    TYPE_SPEC = REPORT_ERROR

    @property
    def step_title(self) -> str:
        return GiveUpStep.TYPE_SPEC

    def __init__(self, *, description: str, role: str, **kwargs):
        # issue: (level, [step desc])
        issues, _ = parse_issue_report(description, None)
        report_lines = []
        for issue, (level, steps) in issues.items():
            if steps is None or _utils.str_or_blank(level) == '':
                continue
            report_lines.extend([f"* {level}: {issue} at [step#{step_num}: {step_desc}]"
                                    for step_num, step_desc in steps])
        super().__init__(description='\n'.join(report_lines), role=role, step_name=None, **kwargs)
        self.issues = issues

    def eval_only(self, executor):
        if len(self.issues) > 0:
            culprits, n_errors = identify_culprits(executor, self.issues)
            if len(culprits) > 0:
                repair_or_backtrack(executor, culprits)
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

    def __init__(self, *, description: str, role: str, step_name: str|None, init_expansion=False, **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._realized_steps: list[Step] = list()
        free_text, blocks = check_and_fix_fenced_blocks(self.description, collapse_blocks=True)
        json_block = None
        for key, (block_content, content_type, _) in blocks.items():
            free_text = free_text.replace(key, '')
            if content_type == 'json':
                if json_block is None:
                    json_block = block_content
                else:
                    raise ParseError(f"Expect only one JSON block, but found multiple. Please merge into one")
        if json_block is None:
            raise ParseError(f"Expecting step-by-step plan in a JSON fenced block, found none.")
        self._steps = parse_step_by_step_plan(json_block)
        # erase sub_steps
        def stringyfy(steps) -> str:
            return "\n".join([f"{i}. {_utils.single_space(strip_quotes_re.sub('', step.description))}"
                              for i, step in steps.items()])
        step_desc = stringyfy(self._steps).strip()

        self.first_step = f"{self._steps[1].description}" # 1-base
        sections: dict[str, str] = parse_sections(free_text, section_level='#')
        sections.pop(NEXT_I_WANT_TO_WORK_AT, None) # just ignore
        self.first_step = f"{self._steps[1].description}" # 1-base

        free_text = _utils.str_or_blank(sections.pop(FREE_TEXT))
        free_text = "\n\n".join([free_text] + [f"## {heading}\n{content}" for heading, content in sections.items()])
        free_text = _utils.str_or_blank(free_text)
        if free_text != '':
            free_text += '\n\n'
        self._free_text = free_text
        self.description = f"""{self._free_text}{step_desc}\n"""

    @property
    def steps(self) -> dict[int, StepDescriptor]:
        return self._steps

    def eval_only(self, executor) -> Step | None:
        # when evaluating this node, we are always at the first step
        return ProceedStep.create_proceed_step(executor, self.first_step, self)

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

class SummarizeStep(TaoReplyStep, FixableStep):
    TYPE_SPEC = SUMMARIZE_FINAL_ANSWER

    def __init__(self, *, description: str, role: str = ROLE_TAO, **kwargs):
        super().__init__(description=description, role=role, step_name=SUMMARIZE_FINAL_ANSWER, **kwargs)
        self._n_tries = 0
        self._evaluated = _utils.str_or_blank(self.description) != ''
        self._pending_culprits: dict[Step, list[str]]|None = None
        self._pending_error_count = 0

    @property
    def step_title(self) -> str:
        return ""

    @property
    def n_tries(self) -> int:
        return self._n_tries

    def repair(self, executor: Executor):
        self.log_repair(executor)
        self._evaluated = False
        self.eval_only(executor)

    def eval_only(self, executor: Executor) -> Step | None:
        if self._evaluated:
            return None
        system_prompt = executor.prompts.tao_intro
        prompts = executor.show_conversation_thread(with_extras=True,
                                                    except_step=self if len(self.description) == 0 else None,
                                                    stop_at=self)
        prompts.append((ROLE_ORCHESTRATOR, executor.prompts.tao_summarize))
        if len(self.criticisms) > 0:
            critic_text = self.format_critic_text()
            step_id = executor.step_id(self)
            prompts.append((ROLE_ORCHESTRATOR,
                            executor.prompts.tao_fix_issues.format(
                                step_id=step_id, step=self.step_name, critic_text=critic_text)))
        self.description = executor.llm.ask(
            system_prompt, prompts,
            reason='summarize',
            step_id=f"{executor.step_id(self)}",
            temperature=0.0,
            log_request=True)
        self._evaluated = True
        self._criticisms.clear()
        self._n_tries += 1
        return None

    def eval(self, executor: Executor) -> Step | None:
        self.eval_only(executor)

        if not executor.config.check_final:
            return None

        if self._pending_culprits is None:
            # concern: (issue, [step desc])
            all_issues = self.check_final_answer(executor)
            if len(all_issues) == 0:
                return None
            self._pending_culprits, self._pending_error_count = identify_culprits(executor, all_issues)
        while self._pending_culprits is not None and len(self._pending_culprits) > 0:
            if self not in self._pending_culprits: # we will always summarize again
                self._n_tries -= 1
                self._pending_culprits[self].append('')
            executor.check_token_usages()
            try:
                repair_or_backtrack(executor, self._pending_culprits)
            except RedoFinalCheck as e:
                executor.logger.log(str(e))
                self._pending_culprits, self._pending_error_count = None, 0
                all_issues = self.check_final_answer(executor)
                if len(all_issues) == 0:
                    break
                self._pending_culprits, self._pending_error_count = identify_culprits(executor, all_issues)
        self._pending_culprits = None
        if self._pending_error_count > 0:
            self._pending_error_count = 0
            return self # need to check final answer again
        self._pending_error_count = 0
        for consolidate_step in consolidate_updated_files(executor.chain):
            executor.enqueue(consolidate_step)
        return None

    def check_final_answer(self,
                           executor: Executor,
                           votes: int=None,
                           reason='check_final_answer') \
            -> dict[str, tuple[str, list[tuple[int, str]]|None]]:
        config = executor.config
        votes = (votes or config.verification_votes)
        system_prompt = executor.prompts.sage_intro
        step_by_step_ids = {i for i in range(len(executor.chain))
                            if _utils.safe_is_instance(executor.chain[i], StepByStepPlan)}
        invisible_step_ids = {i for i in range(len(executor.chain)) if not executor.chain[i].visible_in_chain}

        # issue: (level, [step desc])
        all_issues: dict[str, _t.Tuple[str, list[tuple[int, str]]|None]] = dict()
        issues_by_critic: list[dict] = []
        for i in range(votes):
            prompts = executor.show_conversation_thread(with_extras=True)
            prompts.append((ROLE_ORCHESTRATOR, executor.prompts.sage_final_check))
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            response: str = ''
            while n_retries < config.max_retries:
                try:
                    response = executor.sage_llm.ask(
                        system_prompt,
                        prompts_to_be_sent,
                        reason=reason,
                        step_id=f"{executor.step_id(self)}/{i}#{n_retries}",
                        temperature=0.0)
                    issues, full_json = parse_verification_response(response)
                    matched_step_by_steps: set[int] = set()
                    matched_invisible_steps: set[int] = set()
                    for severity, blames in issues.values():
                        if severity in ('error', 'fatal') and blames is not None:
                            matched_step_by_steps.update(blame[0] for blame in blames if blame[0] in step_by_step_ids)
                        matched_invisible_steps.update(
                            blame[0] for blame in blames
                            if blame[0] in invisible_step_ids or blame[0] < 0 or blame[0] >= len(executor.chain))
                    notes = ''
                    if len(matched_step_by_steps) > 0:
                        if len(matched_step_by_steps) > 1:
                            step_list = ', '.join(f"step#{i}" for i in matched_step_by_steps)
                            step_list = f"{step_list} are step-by-step plans"
                        else:
                            step_list = f"step#{next(iter(matched_step_by_steps))} is a step-by-step plan"
                        notes += f"Double-check: {step_list}. Errors in them are often caused by one of sub-steps. "
                    if len(matched_invisible_steps) > 0:
                        if len(matched_invisible_steps) > 1:
                            step_list = ', '.join(f"{i}" for i in matched_invisible_steps)
                            step_list = f"Step IDs {step_list} do not exist"
                        else:
                            step_list = f"Step ID {next(iter(matched_step_by_steps))} does not exist"
                        notes += f"Double-check: {step_list}. Step IDs are only found in `at step#<ID>`. "
                    if notes != '':
                        prompts.append((ROLE_ORCHESTRATOR, notes))
                        prompts_to_be_sent.append((ROLE_ORCHESTRATOR, notes))
                        step_by_step_ids.clear()
                        continue
                    issues_by_critic.append(full_json)
                    if len(issues) > 0:
                        all_issues.update(issues)
                    break
                except Exception as e:
                    n_retries += 1
                    executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                                executor.prompts.orchestrator_parse_error)
        if len(issues_by_critic) > 0 and votes > 1:
            critic_text = "\n\n".join([
                f"Critic {i+1}:\n```json\n{_json.dumps(report, indent=2)}\n```"
                for i, report in enumerate(issues_by_critic)
            ])
            system_prompt = executor.prompts.sage_intro
            prompts = executor.show_conversation_thread(with_extras=True)
            prompts.append((ROLE_ORCHESTRATOR, executor.prompts.sage_final_check))
            prompts.append((ROLE_ORCHESTRATOR, critic_text))
            prompts.append((ROLE_ORCHESTRATOR, executor.prompts.sage_merge_criticisms))
            prompts_to_be_sent = prompts.copy()
            n_retries = 0
            response: str = ''
            while n_retries < config.max_retries:
                try:
                    response = executor.sage_llm.ask(
                        system_prompt,
                        prompts_to_be_sent,
                        reason='merge_criticisms',
                        step_id=f"{executor.step_id(self)}#{n_retries}",
                        temperature=config.first_try_temperature)
                    all_issues, no_culprit_issues = parse_issue_report(response, len(executor.chain))
                    for issue in no_culprit_issues:
                        executor.logger.log(f"removing report {issue} due to no more culprit.")
                        del all_issues[issue]
                    break
                except Exception as e:
                    n_retries += 1
                    executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                                executor.prompts.orchestrator_parse_error)
        return all_issues


def parse_issue_report(response, step_number_cutoff: int=None) \
        -> tuple[dict[str, _t.Tuple[str, list[tuple[int, str]]|None]], set[str]]:
    all_issues, _ = parse_verification_response(response)
    no_culprit_issues = set()
    for issue, (level, steps) in all_issues.items():
        if level in ('error', 'fatal'):
            if steps is None or len(steps) == 0:
                raise ParseError(f'Error "{issue}" has missing culprit. '
                                 f'Please add the "blame" attribute to assign the culprit step.')
            for si, (step_num, step_desc) in enumerate(steps):
                if step_num < 0 or step_number_cutoff is not None and step_num >= step_number_cutoff:
                    raise ParseError(f"Unknown step ID: step#{step_num}")
        if len(steps) == 0:
            no_culprit_issues.add(issue)
    return all_issues, no_culprit_issues


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
    for i, step in enumerate(executor.chain):
        step = _t.cast(Step, step)
        for (step_num, step_desc), issues_of_step in blames.items():
            if (step_num == i or step_desc is not None and
                    _utils.normalized_levenstein_distance(step.step_name, step_desc) <.05):
                if _utils.safe_is_instance(step, (FixableStep, TaoReplyStep)):
                    _t.cast(FixableStep, step).record_criticisms(issues_of_step)
                if _utils.safe_is_instance(step, SummarizeStep):
                    n_fatals = sum(issue.startswith("fatal:") for issue in issues_of_step)
                    if n_fatals > 0:
                        # no point of backtracking the summary step as it is the final step
                        issues_of_step = [issue.replace("fatal:", "error:") for issue in issues_of_step]
                        cls = step.__class__.__name__
                        executor.logger.log(f"WARNING: change {n_fatals} fatal issues for {cls} step to errors")
                elif _utils.safe_is_instance(step, (AskQuestionStep,)):
                    n_errors = sum(issue.startswith("error:") for issue in issues_of_step)
                    if n_errors > 0:
                        # these are not fixable currently but should backtrack only if fatal for these types
                        issues_of_step = [issue.replace("error:", "warning:") for issue in issues_of_step]
                        cls = step.__class__.__name__
                        executor.logger.log(f"WARNING: change {n_errors} errors for {cls} step to warnings")
                culprits[step].extend(issues_of_step)
                continue
    for i, step in enumerate(executor.chain):
        step = _t.cast(Step, step)
        if _utils.safe_is_instance(step, FinalizeFileStep):
            if step not in culprits:
                culprits[step] = ["affected: Previous steps has been fixed. Consolidate again"]
    total_errors = 0
    for culprits_issues in culprits.values():
        n_errors, n_fatals = count_errors_in_issues(culprits_issues)
        total_errors += n_errors + n_fatals
    return culprits, total_errors


def repair_or_backtrack(executor: Executor, remedies: dict[Step, list[str]]):
    n_errors_fixed = 0
    for blamed_step in list(remedies.keys()):
        blames = remedies.get(blamed_step)
        if len(blames) == 0:  # shouldn't happen
            continue
        n_errors, n_fatals = count_errors_in_issues(blames)
        if n_fatals == 0 and _utils.safe_is_instance(blamed_step, FixableStep):
            if blamed_step.retryable(executor.config):
                _t.cast(FixableStep, blamed_step).repair(executor)
                n_errors_fixed += n_errors + n_fatals
                del remedies[blamed_step]
            elif n_errors > 0:
                raise Backtrack(blames[0], blame=blamed_step)
            else:
                del remedies[blamed_step]
        elif n_fatals > 0 or n_errors > 0:
            raise Backtrack(blames[0], blame=blamed_step)
        else: # warning and not fixable
            del remedies[blamed_step]
    return n_errors_fixed


def count_errors_in_issues(blames: _t.Sequence[str]|None):
    if blames is None:
        return 0, 0
    n_fatals = sum(b.startswith('fatal') for b in blames)
    n_errors = sum(b.startswith('error') or b.startswith('affected') for b in blames)
    return n_errors, n_fatals


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
        pitch = "Python Genie, Python Genie, run the Python snippet underneath"
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
            result_markdown = '\n\n'.join(f"""```text\n{r}\n```""" for r in results)
            logger.new_message_section(ROLE_GENIE, executor.step_id(self))
            logger.log(result_markdown)
            logger.close_message_section()
            self.description += f"\n\nResults:\n\n{result_markdown}"
            self._evaluated = True
            self._n_tries += 1
            return True
        except _utils.PythonGenieRuntimeError as e:
            error_text = f"""error: {str(e.error)} when executing this code snippet."""
            logger.new_message_section(ROLE_GENIE, executor.step_id(self))
            logger.log(error_text)
            logger.close_message_section()
            self._evaluated = True
            self._n_tries += 1
            self.record_criticisms([error_text])
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
                    temperature=0.0 if n_retries == 0.0 else executor.config.alternative_temperature,
                    reason="repair",
                    step_id=f"{self.n_tries}#{n_retries}")
                response = _utils.str_or_blank(response)
                response = response.replace(f"# {self.TYPE_SPEC}", "").strip()
                self._build(description=response)
                break
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
        self._criticisms.clear()
        return self.execute_python_snippet(executor)

    @property
    def n_tries(self) -> int:
        return self._n_tries


class AskQuestionStep(TaoReplyStep):

    TYPE_SPEC = WILL_ASK_QUESTIONS

    @property
    def step_title(self) -> str:
        return AskQuestionStep.TYPE_SPEC if self._answers is None else 'Tao asked and user replied:'

    def __init__(self, *, description: str, role: str, step_name: str|None, **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._answers: list[str]|None = None
        self._need_consolidate = True # always consolidate once

    def _prepend_step_name_header(self, name):
        pass # do not append at step for asking question

    def eval_only(self, executor) -> Step | None:
        if self._need_consolidate:
            prompts: list[tuple[str, str]] = executor.show_conversation_thread()[:-1]
            self.consolidate_questions(executor, prompts)
        if self._answers is None:
            questions = parse_ordered_list(self.description, at_least_one_list=False)
            if len(questions) > 0:
                answers: dict[str, str] = executor.ask_questions(questions)
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
            else:
                self._answers = dict()
            previous = executor.previous_step(self)
            if _utils.safe_is_instance(previous, ExpandableStep):
                previous = _t.cast(ExpandableStep, previous)
                assert executor.chain[-1] is self
                executor.chain.pop(-1)
                if len(questions) > 0:
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


def parse_to_step(response: str, config: Config,
                  working_on: str = None, init_expansion=False, limit_to: set = None) -> Step:
    step_type, step_def = parse_step_type_spec(response)
    if step_type is None:
        raise ParseError(f"Invalid Tao response. Missing header.")
    else:
        if step_type == DirectAnswerStep.TYPE_SPEC:
            step_class = DirectAnswerStep
        elif step_type == AskQuestionStep.TYPE_SPEC:
            step_class = AskQuestionStep
        elif step_type == AskPythonGenieStep.TYPE_SPEC:
            step_class = AskPythonGenieStep
        elif step_type == GiveUpStep.TYPE_SPEC:
            step_class = GiveUpStep
        else:
            step_class = StepByStepPlan
        if step_def is None:
            raise ParseError(f"Unknown action heading '{step_type}'")
    if limit_to is not None and step_class not in limit_to:
        allowed_specs = ', '.join([f"`# {cls.TYPE_SPEC}`" for cls in limit_to])
        raise ParseError(f"Unexpected action `{step_type.TYPE_SPEC}`, only {allowed_specs} are allowed")
    return step_class(description=step_def, role=ROLE_TAO, step_name=working_on, init_expansion=init_expansion)


class ExpandableStep(Step):

    def __init__(self, *, description: str, role: str, step_name: str|None,
                 choices: list[Step] = None, first_expansion: int = 1,
                 incremental_expansion: int = 1, max_expansion: int = 4, **kwargs):
        super().__init__(description=description, role=role, step_name=None, **kwargs)
        self.choices = choices if choices is not None else []
        self.first_expansion = first_expansion
        self.incremental_expansion = incremental_expansion
        self.max_expansion = max_expansion
        self.set_visible_in_chain(False)
        self._ptr = 0
        self._step_name_for_expanded = step_name

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
        system_prompt, base_prompts = self.build_prompts(executor)
        llm = executor.sage_llm if executor.is_init_solving_expansion() \
                                   and executor.config.use_sage_llm_for_initial_expansion else executor.llm
        while len(self.choices) < upto_branches:
            prompts = base_prompts.copy()
            if len(self.choices) > 0:
                prior_plans = [
                    (f"[{PRIOR_PROPOSAL}#{i + 1}] {prior.step_title}\n\n{prior.description}\n\n{prior.extras}\n\n"
                     f"{self._collect_criticism(prior)}")
                    for i, prior in enumerate(self.choices)
                ]
                prior_desc = prompt_db.tao_prior_approaches.format(prior='\n\n---\n'.join(prior_plans))
                prompts.append((ROLE_ORCHESTRATOR, prior_desc))
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            plan: str|None = None
            while n_retries < executor.config.max_retries:
                try:
                    temperature = executor.config.first_try_temperature if len(self.choices) == 0 \
                        else executor.config.alternative_temperature
                    plan = llm.ask(
                        system_prompt, prompts_to_be_sent,
                        reason=self._expansion_reason,
                        step_id=f"{executor.step_id(self)}/{len(self.choices)}#{n_retries}",
                        temperature=temperature,
                        log_request=(len(self.choices) == 0 and n_retries == 0))
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
        if _utils.safe_is_instance(choice, FixableStep):
            choice = _t.cast(FixableStep, choice)
            if len(choice.criticisms) > 0:
                return f"\n---\nCriticisms received for this:\n{choice.format_critic_text()}"
        return ''

    def parse_reply(self, plan, executor: Executor) -> Step:
        choice = parse_to_step(plan, config=executor.config, working_on=self._step_name_for_expanded,
                               init_expansion=executor.is_init_solving_expansion())
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
        n_step_by_step_plans = 0
        if step_by_step is not None:
            plan_id = executor.step_id(step_by_step)
            current_plan = step_by_step.step_name_tag(plan_id)
            for i in range(plan_id, -1, -1):
                if _utils.safe_is_instance(executor.chain[i], StepByStepPlan):
                    n_step_by_step_plans += 1
        else:
            current_plan = '[not sure which plan, go figure out]'
        if not initial:
            tokens, budget = executor.total_tokens, config.max_tokens
            work_prompt = prompt_db.tao_proceed_to_step.format(plan=current_plan, step=self._step_name_for_expanded)
            if n_step_by_step_plans >= 3:
                frac = tokens / budget
                work_prompt += (f"\n\n You've spent {frac:0.0%} of your LLM token budget; be mindful of cost. "
                                f"The step-by-step plan is at {n_step_by_step_plans} levels deep; "
                                f"try to avoid `{HERE_IS_MY_STEP_BY_STEP_PLAN}` actions.")
            base_prompts.append((ROLE_ORCHESTRATOR, work_prompt))

        tao_templates = prompt_db.tao_expand_init_step if initial else prompt_db.tao_expand_any_step
        base_prompts.append((ROLE_ORCHESTRATOR, tao_templates))
        if not initial:
            next_step_instr = prompt_db.snippet_next_step.format(step=current_plan)
            base_prompts.append((ROLE_ORCHESTRATOR, next_step_instr))
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
                f"[Choice {i+1}] {plan.step_title}\n\n{plan.description}\n\n{plan.extras}"
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
                        temperature=config.first_try_temperature if n_success == 0 else config.alternative_temperature,
                        log_request=(n_success == 0 and n_retries == 0))
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
    def create_proceed_step(executor: Executor, next_step_desc: str, step_by_step: StepByStepPlan):
        config = executor.config
        next_step = ProceedStep(
            description='',
            role=ROLE_ORCHESTRATOR,
            first_expansion=config.first_expansion,
            max_expansion=config.max_search_expansion,
            step_name=next_step_desc)
        next_step.part_of = step_by_step
        return next_step

    @property
    def step_title(self) -> str:
        return ""

    @property
    def _expansion_reason(self) -> str:
        return "proceed_to_next"


class NextStep(Step):

    @property
    def step_title(self) -> str:
        return ""

    def eval_only(self, executor) -> Step | None:
        prompt_db = executor.prompts
        system_prompt = prompt_db.tao_intro
        prompts = executor.show_conversation_thread(with_header=True, with_extras=True)
        parent_plan, plan_id = StepByStepPlan.find_last_step_by_step(executor, before=self)
        assert parent_plan is not None
        assert plan_id is not None
        snippet_next_step = prompt_db.snippet_next_step.format(step=parent_plan.step_name_tag(plan_id))
        tao_next_step = prompt_db.tao_next_step.format(
            snippet_next_step=snippet_next_step, snippet_report_errors=prompt_db.snippet_report_errors)
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
                    temperature=0.0 if n_retries == 0 else executor.config.alternative_temperature,
                    log_request=n_retries == 0)
                proceed_step = self.parse_reply(response, executor)
                self.set_visible_in_chain(False)
                return proceed_step
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            prompt_db.orchestrator_parse_error)
        return None # unreachable

    def parse_reply(self, plan: str, executor: Executor) -> Step:
        prompt_db, config = executor.prompts, executor.config
        decision, details = parse_next_step_reply(plan)
        assert decision is not None
        assert details is not None
        if decision == NEXT_I_WANT_TO_WORK_AT:
            next_step_spec = _t.cast(NextStepDesc, details)
            validate_next_step_spec(executor, next_step_spec, no_spec_ok=False)
            return proceed_next(self, executor, next_step_spec)
        else:
            step = parse_to_step(_t.cast(str, details), config=config, working_on=None)
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

    if next_step_spec.target_plan_id is not None and next_step_spec.target_plan_id != current_plan_id:
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


class SummarizePartialStep(DirectAnswerStep):

    def __init__(self, *, role: str, step_name: str, shadowing: list[Step],
                 consolidate_file_steps: list[FinalizeFileStep], **kwargs):
        super().__init__(description='', role=role, step_name=step_name, is_final_step=False, **kwargs)
        self._shadowing: list[Step]= shadowing
        self.consolidate_file_steps = consolidate_file_steps
        self._evaluated = False

    def eval_only(self, executor) -> Step | None:
        if self._evaluated:
            return super().eval_only(executor)
        from_step_tag = self._shadowing[0].step_name_tag(executor.step_id(self._shadowing[0]))
        to_step_tag = self._shadowing[-1].step_name_tag(executor.step_id(self._shadowing[-1]))
        prompt_db = executor.prompts
        system_prompt = prompt_db.tao_intro
        prompts = executor.show_conversation_thread(with_extras=True, stop_at=self._shadowing[-1])

        instr = prompt_db.tao_summarize_partial.format(from_step=from_step_tag, to_step=to_step_tag)
        prompts.append((ROLE_ORCHESTRATOR, instr))
        files: set[str] = set()
        for step in self._shadowing:
            files.update(step.collected_files.keys())
        if len(files) > 0:
            prompts.append((ROLE_ORCHESTRATOR, prompt_db.snippet_notes_for_files))

        n_retries = 0
        response: str|None = None
        to_be_sent = prompts.copy()
        while n_retries < executor.config.max_retries:
            try:
                response = executor.llm.ask(
                    system_prompt, to_be_sent,
                    reason='summarize_partial',
                    step_id=f"{executor.step_id(self._shadowing[0])}#{n_retries}",
                    temperature=0.0)
                self.build(response)
                self.next_step = None # nullify just in case, will ask later
                self.validate(executor)
                self.description = self.description.replace(from_step_tag, "-").replace(to_step_tag, "-")
                break
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            prompt_db.orchestrator_parse_error)
        executor.remove_steps(from_step=self._shadowing[0], to_step=self._shadowing[-1])
        if self.consolidate_file_steps is not None:
            for consolidation in self.consolidate_file_steps:
                self.collected_files.update(consolidation.collected_files)
            executor.remove_steps(steps=self.consolidate_file_steps)
        self._evaluated = True
        return super().eval_only(executor)


def proceed_next(current_step: Step, executor: Executor, next_step_spec: NextStepDesc) -> Step:
    if next_step_spec.is_final_step:
        return _t.cast(Step, executor.summarize_final_answer())

    current_index = executor.step_id(current_step)
    assert current_index == len(executor.chain)-1
    if next_step_spec.target_plan_id is not None and next_step_spec.target_plan_done:
        finished_plan = _t.cast(Step, executor.chain[next_step_spec.target_plan_id])
        partial = _t.cast(list[Step], executor.chain[next_step_spec.target_plan_id:current_index + 1])

        consolidate_file_steps = consolidate_updated_files(partial)
        for consolidate_file_step in consolidate_file_steps:
            if not consolidate_file_step._evaluated:
                executor.enqueue(consolidate_file_step)
        summarize = SummarizePartialStep(role=ROLE_TAO, step_name=finished_plan.step_name, shadowing=partial,
                                         consolidate_file_steps=consolidate_file_steps)
        if _utils.safe_is_instance(finished_plan.created_by, ExpandableStep):
            _t.cast(ExpandableStep, finished_plan.created_by).insert_choice(summarize, increase_max=True)
        if next_step_spec.is_final_step:
            executor.enqueue(summarize)
            return _t.cast(Step, executor.summarize_final_answer())
        return summarize

    matched_plan, _ = StepByStepPlan.find_last_step_by_step(executor, before=current_index)
    return ProceedStep.create_proceed_step(executor, next_step_spec.next_step_desc, matched_plan)


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
    files = GeneratedFile.collect_files(steps)
    file_updates = count_file_updates(steps)
    consolidate_file_steps = []
    for file, content in files.items():
        consolidate_file_step = FinalizeFileStep(description='', role=ROLE_TAO, file_name=file,
                                                 keep_content_even_if_same=True)
        consolidate_file_steps.append(consolidate_file_step)
        if file_updates.get(file, 0) == 1:  # only if more than 1 update. 0 shouldn't happen
            consolidate_file_step.collected_files[file] = content
            consolidate_file_step._evaluated = True
    return consolidate_file_steps


class PresentTaskStep(FixableStep):

    def __init__(self, *, description: str, role: str, step_name='task statement', **kwargs):
        super().__init__(description=description, role=role, step_name=step_name, **kwargs)
        self._n_tries = 1 # already evaluated once since the description is the result
        self._criticisms: list[str] = []

    @property
    def step_title(self) -> str:
        return ""

    def retryable(self, config):
        return True # always retryable

    @property
    def n_tries(self) -> int:
        return self._n_tries

    def record_criticisms(self, criticisms: list[str]):
        self._criticisms.extend(criticisms)

    @property
    def criticisms(self) -> list[str]:
        return self._criticisms

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
        self._n_tries += 1
        raise RedoFinalCheck(self)
