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

    def __init__(self, *, previous: StepABC|None, description: str, role: str, **_):
        super().__init__(previous=previous, description=description, role=role)

    @classmethod
    def create(cls, prev_step: StepABC, step_def: str, role: str, config: Config) -> _t.Self:
        _ = Config
        return cls(previous=prev_step, description=step_def, role=role)

    @property
    def step_title(self) -> str:
        return ''

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
            step_name = _utils.str_or_blank(self.step_name)
            if step_name == '': # no name, use numeric index
                step_name = f"step {step_index}"
            content += f"[at step#{step_index}: {step_name}]\n\n"
        content += self.description
        content += extra_content
        return [(self.role, content)]

    def retryable(self, config: Config):
        return False

    def eval(self, executor: Executor) -> Step | None:
        returned = self.eval_only(executor)
        return returned

    def eval_only(self, executor) -> Step | None:
        return None


class FixableStep(Step):

    @abstractmethod
    def retryable(self, config):
        pass

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


class AnalysisStep(Step):

    def __init__(self, *, previous: StepABC|None, description: str, role: str):
        super().__init__(previous=previous, description=description, role=role)
        self._analyzed = False

    @property
    def step_title(self) -> str:
        return 'Problem Analysis'

    def eval_only(self, executor) -> Step | None:
        if self._analyzed:
            return None
        prompt_db: PromptDb  = executor.prompts
        if self.description is None or len(_utils.str_or_blank(self.description)) == 0:
            self.description = prompt_db.tao_ask_init_analysis
        system_prompt = prompt_db.tao_intro
        prompts: list[tuple[str, str]] = executor.show_conversation_thread(with_header=False)
        llm = executor.sage_llm if executor.config.use_sage_llm_for_initial_expansion else executor.llm
        desc = llm.ask(
            system_prompt, prompts,
            reason='analyze',
            temperature=0.0,
            step_id=f"{executor.step_id(self)}")
        self.description = at_step_re.sub('', desc).strip()
        self.role = ROLE_TAO
        self._analyzed = True
        return None


class TaoReplyStep(Step):

    def __init__(self, *, previous: StepABC|None, description: str, role: str, **_):
        super().__init__(previous=previous, description=description, role=role)
        self._criticisms: list[str] = list()
        sections = parse_sections(self.description)
        self.description = sections[FREE_TEXT]

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

    def __init__(self, *, previous: StepABC|None, description: str, role: str, is_final_step=False):
        description = at_step_re.sub('', description).strip()
        super().__init__(previous=previous, description=description, role=role)
        self.is_final_step = is_final_step
        self._n_tries = 1 # already evaluated once since the description is the result
        self._previous_contents: list[tuple[str, dict]] = []
        self._fixed_file_contents = False
        self.build(description)

    def build(self, description: str, next_step: str=None):
        self.description = re.sub(rf"#+\s+{NEXT_I_WANT_TO_WORK_AT}", f"### {NEXT_I_WANT_TO_WORK_AT}:",
                                  description, 1)
        sections: dict[str, str] = parse_sections(self.description)
        extracted_contents = gather_file_contents(sections, pop_file_sections=True)
        self._files: dict[str, taogpt.GeneratedFile] = {
            file_path: taogpt.GeneratedFile(content_type, content, snippet, desc)
            for file_path, (content_type, content, snippet, desc) in extracted_contents.items()
        }
        self.next_step = sections.pop(NEXT_I_WANT_TO_WORK_AT, next_step)
        if self.next_step is not None:
            self.next_step = parse_next_step_name(_utils.single_space(strip_quotes_re.sub('', self.next_step)))
        self.is_final_step = self.is_final_step or is_final_answer(self.next_step)
        reconstructed = [f"# {heading}\n{content}" for heading, content in sections.items()]
        self.description = '\n\n'.join(reconstructed)
        self.description = re.sub(rf"# {FREE_TEXT}\n+", "", self.description, flags=re.IGNORECASE)

    def retryable(self, config: Config):
        return self.n_tries < config.max_retries

    @property
    def n_tries(self) -> int:
        return self._n_tries

    def repair(self, executor: Executor):
        self._previous_contents.append((self.description, self._files))
        critic_text = self.log_repair(executor)

        prompt_db: PromptDb  = executor.prompts
        prompts = executor.show_conversation_thread(with_header=True, with_extras=True, stop_at=self)
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.snippet_notes_for_files))
        instr = prompt_db.tao_fix_issues.format(critic_text=critic_text)
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
                if not response.startswith(f"# {self.TYPE_SPEC}"):
                    response = f"# {self.TYPE_SPEC}\n\n" + response
                dummy = parse_to_step(_t.cast(Step, self.previous), response, executor.config, working_on=self.step_name,
                                      limit_to={self.__class__})
                self.build(f"{dummy.description}\n\n{dummy.extras}", next_step=self.next_step)
                self._fixed_file_contents = False
                self.fix_overridden_files(executor)
                break
            except ParseError as ex:
                n_retries += 1
                executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                            executor.prompts.orchestrator_parse_error)
        self._criticisms.clear()
        self.set_step_name(self.step_name)
        self._n_tries += 1

    def eval_only(self, executor) -> Step | None:
        self.fix_overridden_files(executor)
        if not _utils.is_blank(self.next_step) and not self.is_final_step:
            prompt_db: PromptDb  = executor.prompts
            work_prompt = prompt_db.tao_proceed_to_step.format(step=self.next_step)
            next_step = ProceedStep(previous=self, description=work_prompt, role=ROLE_ORCHESTRATOR)
            next_step.set_step_name(self.next_step)
            return next_step
        return None

    def fix_overridden_files(self, executor) -> int:
        if self._fixed_file_contents:
            return 0
        previous_files = GeneratedFile.collect_files(executor.chain, stop_at_step=self)
        ok_files = set()
        diff_files = dict()
        for file_name, updated_file in self._files.items():
            original = previous_files.get(file_name, None)
            if (original is not None
                    and _utils.normalized_levenstein_distance(original.content, updated_file.content) > 0.1):
                diff_files[file_name] = original
            else:
                ok_files.add(file_name)
        if len(diff_files) > 0:
            self._previous_contents.append((self.description, self._files))

            purposes = '\n'.join(f"* {purpose}" for purpose in ([self.step_name] + self.criticisms))
            for file_name, updated_files in self._files.items():
                if file_name in ok_files:
                    continue
                original_file = diff_files.get(file_name, None)
                updated_file= self._files[file_name]
                if original_file is not None:
                    instr = executor.prompts.tao_ensure_updated_file_integrity.format(
                        file_name=file_name, purposes=purposes,
                        original_content=original_file.markdown_snippet, updated_content=updated_file.markdown_snippet)
                else:
                    instr = executor.prompts.tao_ensure_file_completeness.format(
                        file_name=file_name, purposes=purposes, content=updated_file.markdown_snippet)
                prompts = [(ROLE_ORCHESTRATOR, instr)]

                to_be_sent = prompts.copy()
                n_retries = 0
                response: str | None = None
                while n_retries < executor.config.max_retries:
                    try:
                        response = executor.llm.ask(
                            executor.prompts.tao_intro,
                            to_be_sent,
                            temperature=0.0 if n_retries == 0.0 else executor.config.alternative_temperature,
                            reason=f"ensure_full_content",
                            step_id=f"{file_name}#{n_retries}")
                        response = _utils.str_or_blank(response)
                        content_type, content, snippet = extract_fenced_content(response)
                        if content is None:
                            raise ParseError("There seems to be no Markdown fenced block. Make sure file content in "
                                             "fenced block.")
                        if content_type != updated_file.content_type:
                            raise ParseError(f"The Markdown content type is changed "
                                             f"from `{original_file.content_type}` to `{content_type}`")
                        updated_file.content = content
                        # todo: support nested fenced markdown block
                        updated_file.markdown_snippet = f"```{content_type}\n{content}\n```"
                        break
                    except ParseError as ex:
                        n_retries += 1
                        executor.handle_parse_error(ex, n_retries, prompts, to_be_sent, response,
                                                    executor.prompts.orchestrator_parse_error)
            self._fixed_file_contents = True

        return len(diff_files)

    @property
    def collected_files(self) -> dict[str, GeneratedFile]:
        return self._files

    @property
    def extras(self) -> str:
        file_contents = ''
        for path, file in self.collected_files.items():
            file_contents += f"\n### FILE: {path}\n\n{file.markdown_snippet}\n\n"
        return file_contents


class GiveUpStep(TaoReplyStep):
    TYPE_SPEC = REPORT_ERROR

    @property
    def step_title(self) -> str:
        return GiveUpStep.TYPE_SPEC

    def __init__(self, *, previous: StepABC|None, description: str, role: str):
        # issue: (level, [step desc])
        issues, _ = parse_issue_report(description, None)
        report_lines = []
        for issue, (level, steps) in issues.items():
            if steps is None or _utils.str_or_blank(level) == '':
                continue
            report_lines.extend([f"* {level}: {issue} at [step#{step_num}: {step_desc}]"
                                    for step_num, step_desc in steps])
        super().__init__(previous=previous, description='\n'.join(report_lines), role=role)
        self.issues = issues

    def eval_only(self, executor):
        if len(self.issues) > 0:
            culprits = identify_culprits(executor, self.issues)
            if len(culprits) > 0:
                repair_or_backtrack(executor, culprits)
                # No Backtrack raised, we have fixed all errors, pop itself
                assert _utils.safe_is_instance(self.previous, ExpandableStep)
                assert executor.chain[-1] is self
                executor.chain.pop(-1)
                _t.cast(ExpandableStep, self.previous).choices.remove(self)
                return self.previous
        raise Backtrack(f"Problem or step is unsolvable. I gave up.", self)


class StepByStepPlan(TaoReplyStep):
    TYPE_SPEC = HERE_IS_MY_STEP_BY_STEP_PLAN

    @classmethod
    def create(cls, prev_step: StepABC, step_def: str, role: str, config: Config) -> _t.Self:
        return cls(previous=prev_step, description=step_def, role=role)

    @property
    def step_title(self) -> str:
        return StepByStepPlan.TYPE_SPEC

    def __repr_local__(self) -> str:
        desc = ';'.join([_utils.safe_subn(step.description, 10) for step in self._steps.values()])
        return f"[{desc}]"

    def __init__(self, *, previous: StepABC|None, description: str, role: str):
        super().__init__(previous=previous, description=description, role=role)
        self._steps = parse_step_by_step_plan(self.description)
        self._update_file_step: StepDescriptor|None = None
        self.first_step = f"{self._steps[1].description}" # 1-base
        # erase sub_steps
        def stringyfy(steps) -> str:
            return "\n".join([f"{i}. {_utils.single_space(strip_quotes_re.sub('', step.description))}"
                              for i, step in steps.items()])
        step_desc = stringyfy(self._steps).strip()
        self.description = f"""\n{step_desc}\n"""
        previous_plan: StepByStepPlan|None = None
        while previous is not None:
            if isinstance(previous, StepByStepPlan):
                previous_plan = previous
                break
            previous = previous.previous
        if previous_plan is not None:
            previous_plan_steps = stringyfy(previous_plan._steps).strip().lower()
            distance = _utils.normalized_levenstein_distance(previous_plan_steps, step_desc.lower())
            if distance < 0.2:
                raise ParseError(f"This step-by-step plan looks like repetition of the plan "
                                 f"for step {previous.step_name}. Come up with a real plan for this step.")

    @property
    def steps(self) -> dict[int, StepDescriptor]:
        return self._steps

    def set_step_name(self, name: str | None, forced=False):
        super().set_step_name(name, forced)
        self.description = self.description.replace("UNKNOWN_STEP", name)
        if self._update_file_step is not None:
            self._update_file_step.description = self._update_file_step.description.replace("UNKNOWN_STEP", name)


    def eval_only(self, executor) -> Step | None:
        # when evaluating this node, we are always at the first step
        prompt_db: PromptDb  = executor.prompts
        work_prompt = prompt_db.tao_proceed_to_step.format(step=self.first_step)
        # note: we insert the update file step at the end, this cannot be update file step.
        next = ProceedStep(previous=self, description=work_prompt, role=ROLE_ORCHESTRATOR)
        next.set_step_name(self.first_step)
        return next


class SummarizeStep(TaoReplyStep, FixableStep):
    TYPE_SPEC = SUMMARIZE_FINAL_ANSWER

    def __init__(self, *, previous: StepABC|None, description: str, role: str=ROLE_TAO):
        super().__init__(previous=previous, description=description, role=role)
        self._n_tries = 0
        self._evaluated = _utils.str_or_blank(self.description) != ''
        self._pending_culprits: dict[Step, list[str]]|None = None
        self.set_step_name(None)

    @property
    def step_title(self) -> str:
        return ""

    def set_step_name(self, name: str | None, forced=False):
        super().set_step_name(SUMMARIZE_FINAL_ANSWER)

    def retryable(self, config: Config):
        return self._n_tries < config.max_retries

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
            prompts.append((ROLE_ORCHESTRATOR, executor.prompts.tao_fix_issues.format(critic_text=critic_text)))
        self.description = executor.llm.ask(
            system_prompt, prompts,
            reason='summarize',
            step_id=f"{executor.step_id(self)}",
            temperature=0.0,
            log_request=True)
        self._evaluated = True
        self._pending_culprits = None
        self._criticisms.clear()
        self.set_step_name(SUMMARIZE_FINAL_ANSWER)
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
            self._pending_culprits = identify_culprits(executor, all_issues)

        if self not in self._pending_culprits: # we will always summarize again
            self._n_tries -= 1
            self._pending_culprits[self].append('')
        try:
            total_errors = repair_or_backtrack(executor, self._pending_culprits)
            return self if total_errors > 0 else None
        finally:
            if self._pending_culprits is not None and len(self._pending_culprits) == 0:
                self._pending_culprits = None

    def check_final_answer(self,
                           executor: Executor,
                           votes: int=None,
                           reason='check_final_answer') \
            -> dict[str, tuple[str, list[tuple[int, str]]|None]]:
        config = executor.config
        votes = (votes or config.verification_votes)
        system_prompt = executor.prompts.sage_intro

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
                    raise ParseError(f"Unknown step number: step#{step_num}")
        if len(steps) == 0:
            no_culprit_issues.add(issue)
    return all_issues, no_culprit_issues


def identify_culprits(
        executor: Executor,
        issues: dict[str, tuple[str, list[tuple[int, str]]]]=None, # issue: (level, [(step#, step desc)])
) -> dict[Step, list[str]]:
    # (step#, step desc): [issue desc with level]
    blames: dict[tuple[int, str], list[str]] = _defaultdict(list)
    for issue, (level, steps) in issues.items():
        if steps is None or _utils.str_or_blank(level) == '':
            continue
        for step_num, step_desc in steps:
            blames[(step_num, step_desc)].append(f"{level}: {issue}")
    # step: [issue desc with level]
    culprits: dict[Step, list[str]] = _defaultdict(list)
    for i, step in enumerate(executor.chain):
        for (step_num, step_desc), issues_of_step in blames.items():
            if step_num == i or _utils.normalized_levenstein_distance(step.step_name, step_desc) < 0.05:
                if _utils.safe_is_instance(step, (FixableStep, TaoReplyStep)):
                    step.record_criticisms(issues_of_step)
                if _utils.safe_is_instance(step, SummarizeStep):
                    n_fatals = sum(issue.startswith("fatal:") for issue in issues_of_step)
                    if n_fatals > 0:
                        # no point of backtracking the summary step as it is the final step
                        issues_of_step = [issue.replace("fatal:", "error:") for issue in issues_of_step]
                        cls = step.__class__.__name__
                        executor.logger.log(f"WARNING: change {n_fatals} fatal issues for {cls} step to errors")
                elif _utils.safe_is_instance(step, (PresentTaskStep, AskQuestionStep, AnalysisStep)):
                    n_errors = sum(issue.startswith("error:") for issue in issues_of_step)
                    if n_errors > 0:
                        # these are not fixable currently but should backtrack only if fatal for these types
                        issues_of_step = [issue.replace("error:", "warning:") for issue in issues_of_step]
                        cls = step.__class__.__name__
                        executor.logger.log(f"WARNING: change {n_errors} errors for {cls} step to warnings")
                culprits[step].extend(issues_of_step)
                continue
    return culprits


def repair_or_backtrack(executor, remedies):
    total_errors = 0
    for blamed_step in list(remedies.keys()):
        blames = remedies.get(blamed_step)
        if len(blames) == 0:  # shouldn't happen
            continue
        n_fatals = sum(b.startswith('fatal') for b in blames)
        n_errors = sum(b.startswith('error') or b.startswith('affected') for b in blames)
        total_errors += n_fatals + n_errors
        if n_fatals == 0 and _utils.safe_is_instance(blamed_step, FixableStep):
            if blamed_step.retryable(executor.config):
                _t.cast(FixableStep, blamed_step).repair(executor)
                del remedies[blamed_step]
            elif n_errors > 0:
                del remedies[blamed_step]
                raise Backtrack(blames[0], blame=blamed_step)
        elif n_fatals > 0 or n_errors > 0:
            del remedies[blamed_step]
            raise Backtrack(blames[0], blame=blamed_step)
    return total_errors


class AskPythonGenieStep(TaoReplyStep, FixableStep):

    TYPE_SPEC = WILL_ASK_GENIE

    @property
    def step_title(self) -> str:
        return AskPythonGenieStep.TYPE_SPEC

    def __init__(self, *, previous: StepABC|None, description: str, role: str):
        super().__init__(previous=previous, description=description, role=role)
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
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.tao_fix_issues.format(critic_text=critic_text)))

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
        self.set_step_name(self.step_name)
        return self.execute_python_snippet(executor)

    def retryable(self, config):
        return self.n_tries < config.max_retries

    @property
    def n_tries(self) -> int:
        return self._n_tries


class AskQuestionStep(TaoReplyStep):

    TYPE_SPEC = WILL_ASK_QUESTIONS

    @property
    def step_title(self) -> str:
        return AskQuestionStep.TYPE_SPEC if self._answers is None else 'Tao asked and user replied:'

    def __init__(self, *, previous: StepABC|None, description: str, role: str):
        super().__init__(previous=previous, description=description, role=role)
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
            previous = self.previous
            if _utils.safe_is_instance(previous, ExpandableStep):
                previous = _t.cast(ExpandableStep, previous)
                assert executor.chain[-1] is self
                executor.chain.pop(-1)
                if len(questions) > 0:
                    executor.chain.insert(len(executor.chain)-1, self)
                    grandparent = previous.previous
                    self.previous = grandparent
                    previous.previous = self
                    previous.reset_choices()
                    if _utils.str_or_blank(self.step_name) != '' and not self.step_name.startswith("ask question"):
                        self.set_step_name(f"ask questions before {self.step_name}", forced=True)
                return executor.chain[-1]
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


def parse_to_step(prev_step: Step|None, response: str, config: Config,
                  working_on: str = None, limit_to: set=None) -> Step:
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
            raise ParseError(f"Unknown strategy heading '{step_type}'")
    if limit_to is not None and step_class not in limit_to:
        allowed_specs = ', '.join([f"`# {cls.TYPE_SPEC}`" for cls in limit_to])
        raise ParseError(f"Unexpected strategy `{step_type.TYPE_SPEC}`, only {allowed_specs} are allowed")
    step = step_class.create(prev_step, step_def, role=ROLE_TAO, config=config)
    if working_on is not None:
        step.set_step_name(working_on)
    return step


class ExpandableStep(Step):

    def __init__(self, *, previous: StepABC|None, description: str, role: str,
                 choices: list[Step]=None,
                 first_expansion: int=1,
                 incremental_expansion: int=1,
                 max_expansion: int=4):
        super().__init__(previous=previous, description=description, role=role)
        self.choices = choices if choices is not None else []
        self.first_expansion = first_expansion
        self.incremental_expansion = incremental_expansion
        self.max_expansion = max_expansion
        self.set_visible_in_chain(False)
        self._ptr = 0
        for next_step in self.choices:
            next_step.previous = self

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

    def _prepend_step_name_header(self, name):
        pass

    def expand_choices(self, executor: Executor, upto_branches: int):
        prompt_db: PromptDb  = executor.prompts
        system_prompt, base_prompts = self.build_prompts(executor)
        llm = executor.sage_llm if executor.is_first_solving_expansion() \
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
                    if executor.is_first_solving_expansion() and _utils.safe_is_instance(choice, DirectAnswerStep):
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
        choice = parse_to_step(self, plan, config=executor.config, working_on=f"response to {self.step_name}")
        return choice

    def build_prompts(self, executor: Executor) \
            -> _t.Tuple[str, list[_t.Tuple[str, str]]]:
        prompt_db = executor.prompts
        system_prompt = prompt_db.tao_intro
        first = executor.is_first_solving_expansion()
        tao_templates = prompt_db.tao_expand_first_step if first else prompt_db.tao_expand_any_step
        base_prompts: list[tuple[str, str]] = executor.show_conversation_thread(with_extras=True)
        base_prompts.insert(-1, (ROLE_ORCHESTRATOR, tao_templates))
        return system_prompt, base_prompts

    def ask_for_intuition(self, executor: Executor) -> Step|None:
        prompts: list[tuple[str, str]] = executor.show_conversation_thread(
            with_header=False, with_extras=True)
        prompt_db = executor.prompts
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.tao_proceed_intuitively.format(step=self.step_name)))
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.snippet_notes_for_files))
        n_retries = 0
        prompts_to_be_sent = prompts.copy()
        intuition: str|None = None
        while n_retries < executor.config.max_retries:
            try:
                intuition = executor.llm.ask(
                    None, prompts_to_be_sent,
                    reason="intuition",
                    step_id=f"{executor.step_id(self)}#{n_retries}",
                    temperature=executor.config.first_try_temperature).strip()
                if len(intuition) == 0:
                    return None

                if executor.is_first_solving_expansion():
                    intuition = f"""{intuition}

### {NEXT_I_WANT_TO_WORK_AT}:
None. This is the final step.
"""
                match: re.Match = step_type_re.search(intuition)
                response_step_name = f"response to {self.step_name}"
                if match is not None:
                    step = parse_to_step(self, intuition, executor.config, working_on=response_step_name)
                else:
                    step = DirectAnswerStep.create(self, intuition, role=ROLE_TAO, config=executor.config)
                    step.set_step_name(response_step_name)
                return step
            except Exception as e:
                n_retries += 1
                executor.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent,
                                            intuition, prompt_db.orchestrator_parse_error)

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
            raise Backtrack(f"No valid plan found for this step.", self.previous)
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
        raise Backtrack("No more alternative", blame=self.previous)

    def eval_only(self, executor: Executor) -> Step | None:
        old_length = len(self.choices)
        config = executor.config
        first_expand = executor.is_first_solving_expansion()
        if self.should_try_intuition(executor):
            intuition = self.ask_for_intuition(executor)
            self.choices.append(intuition)
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
            logger.log_debug(f"{executor.step_id(self)}/'{self.step_name}' no more options: {self._ptr}/{len(self.choices)}")
            raise Backtrack('No viable options.', blame=self.previous)
        return self.choices[self._ptr]

    def should_try_intuition(self, executor: Executor):
        config = executor.config
        first_expand = executor.is_first_solving_expansion()
        return (len(self.choices) == 0
                and (not first_expand and config.try_intuition
                     or first_expand and config.try_intuition_initial_expansion))


class ProceedStep(ExpandableStep):

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
        prompts.append((ROLE_ORCHESTRATOR, prompt_db.tao_next_step))
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
        decision, (answer, plan) = parse_next_step_reply(plan)
        assert decision is not None
        assert answer is not None
        if decision == NEXT_I_WANT_TO_WORK_AT:
            step_id, step_name = parse_step_name(answer)
            if _utils.is_blank(step_name) or step_name.lower().startswith('none'):
                return SummarizeStep(previous=self, description='', role=ROLE_TAO)
            work_prompt = prompt_db.tao_proceed_to_step.format(step=step_name)
            choices = [parse_to_step(self, plan, config=config, working_on=step_name)] if plan is not None else []
            proceed = ProceedStep(
                previous=self,
                description=work_prompt,
                role=ROLE_ORCHESTRATOR,
                first_expansion=config.first_expansion,
                max_expansion=config.max_search_expansion,
                choices=choices
            )
            proceed.set_step_name(step_name)
            return proceed
        else:
            return parse_to_step(self, answer, config=config, working_on=f"response to {self.step_name}")


class PresentTaskStep(Step):

    @property
    def step_title(self) -> str:
        return ""

    def __init__(self, *, previous: StepABC|None, description: str, role: str):
        super().__init__(previous=previous, description=description, role=role)
        sections: dict[str, str] = parse_sections(self.description)
        extracted_contents = gather_file_contents(sections, pop_file_sections=True)
        self._files: dict[str, taogpt.GeneratedFile] = {
            file_path: taogpt.GeneratedFile(content_type, content, snippet, desc)
            for file_path, (content_type, content, snippet, desc) in extracted_contents.items()
        }
        reconstructed = [f"# {heading}\n{content}" for heading, content in sections.items()]
        self.description = '\n\n'.join(reconstructed)
        self.description = re.sub(rf"# {FREE_TEXT}\n+", "", self.description, flags=re.IGNORECASE)

    @property
    def collected_files(self) -> dict[str, GeneratedFile]:
        return self._files
