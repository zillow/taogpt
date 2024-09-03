from __future__ import annotations
import dataclasses as _dc
import typing as _t
import datetime as _datetime
import json as _json
import re as _re
import inspect as _inspect

import taogpt.md_logging
from . import MarkdownLogger, TokenUsageError
from .exceptions import UnsolvableError
from .llm_model import *
from .program import *
import taogpt.utils as _utils


class Orchestrator(Executor):

    def __init__(self, *,
                 config: Config,
                 llm: LLM,
                 prompts: PromptDb,
                 markdown_logger: taogpt.md_logging.MarkdownLogger,
                 sage_llm: LLM=None,
                 file_merging_llm: LLM=None,
                 **kwargs):
        super().__init__(**kwargs)
        self._config = Config(**_dc.asdict(config))
        self._llm = llm
        self._prompts = prompts
        self._markdown_logger = markdown_logger
        self._sage_llm = sage_llm
        self._merge_file_llm = file_merging_llm

        self._chain: list[Step] = []
        self._waiting: list[Step] = []
        self._reverted_steps: list[Step]|None = None
        self._pending_backtrack: Backtrack|None = None
        self._create_python_scope()
        if self._config.collapse_long_prompts:
            self._llm.merge_collapsed_contents(self._prompts.to_dict())
            if self._sage_llm is not None:
                self._sage_llm.merge_collapsed_contents(self._prompts.to_dict())
        if self.config.max_tokens_for_sage_llm is None:
            if self._sage_llm is not None and self._llm is not self._sage_llm:
                self.config.max_tokens_for_sage_llm = self.config.max_tokens // 3
            else:
                self.config.max_tokens_for_sage_llm = self.config.max_tokens
        else:
            self.config.max_tokens_for_sage_llm = self.config.max_tokens_for_sage_llm

    def __repr__(self) -> str:
        llm_repr = repr(self.llm)
        sage_llm_repr = repr(self.sage_llm)
        n = len(self.chain)
        return f"{self.__class__.__name__}(LLMs={llm_repr}/{sage_llm_repr},chain={n})"

    @property
    def config(self) -> Config:
        return self._config

    @property
    def llm(self) -> LLM:
        return self._llm

    @property
    def prompts(self) -> PromptDb:
        return self._prompts

    @property
    def sage_llm(self) -> LLM:
        return self._sage_llm or self.llm

    @property
    def file_merging_llm(self) -> LLM:
        return self._merge_file_llm or self.llm

    @property
    def logger(self) -> MarkdownLogger:
        return self._markdown_logger

    @property
    def chain(self) -> list[Step]:
        return self._chain

    def remove_steps(self, *, from_step: StepABC=None, to_step: StepABC=None, steps: list[StepABC]=None):
        if from_step is not None:
            from_index, to_index = self.step_id(from_step), None
            new_chain = self._chain[:from_index]
            if to_step is not None:
                to_index = self.step_id(to_step)
                new_chain += self._chain[to_index + 1:]
            self._chain = new_chain
        if steps is not None:
            for step in steps:
                if step in self._chain:
                    self._chain.remove(_t.cast(Step, step))

    @property
    def current_step_name(self) -> str:
        step: Step
        for step in reversed(self.chain):
            step_name = step.step_name
            if _utils.str_or_blank(step_name) != '':
                return step_name
        return ''

    def start(self, task: str | Step):
        self.log_configs()
        if _utils.safe_is_instance(task, str):
            root_step = PresentTaskStep(description=task, role=ROLE_USER)
        elif _utils.safe_is_instance(task, PresentTaskStep):
            root_step = task
        else:
            raise ValueError(f"Expecting string description of task "
                             f"or a PresentTaskStep object, got {type(task)}")
        self.reset()
        self.chain.append(root_step)
        step_id = f"[step#{self.step_id(root_step)}: task statement]"
        work_next_step = ProceedStep(description=self.prompts.tao_proceed_to_step.format(plan="root", step=step_id),
                                     role=ROLE_ORCHESTRATOR,
                                     first_expansion=self.config.initial_expansion,
                                     max_expansion=self.config.max_search_expansion,
                                     declare_next_step=False,
                                     step_name="top-level plan/answer")
        self.chain.append(work_next_step)
        self._execute_with_backtracking()

    def log_configs(self, logger: MarkdownLogger=None):
        if logger is None:
            logger = self.logger
        today = _datetime.date.today().strftime('%Y/%m/%d')
        logger.log(f"Date: {today}", role='debug')
        logger.log(f"**Configurations for {self.__class__.__name__}**", role='debug')
        logger.log(f"LLM: {repr(self.llm)}")
        logger.log(f"Sage LLM: {repr(self.sage_llm)}")
        if self.config.file_support:
            logger.log(f"File consolidation LLM: {repr(self.file_merging_llm)}")
        logger.log(f"""```json
{_json.dumps(_dc.asdict(self.config), indent=2)}
```
        """, role='debug')

    def resume(self, additional_tokens: int=None,
               additional_sage_tokens: int=None):
        if additional_tokens is not None:
            self.config.max_tokens += additional_tokens
            self.llm.max_token_usage = self.config.max_tokens * 2
            self.logger.log(f"**resume**: extend token allowance by {additional_tokens} to {self.config.max_tokens}")
            if self.file_merging_llm is not self.llm:
                self.file_merging_llm.max_token_usage = self.config.max_tokens * 2
                self.logger.log(f"**resume**: extend file mergining token allowance by {additional_tokens} to"
                                f" {self.config.max_tokens}")
        if additional_sage_tokens is not None:
            self.config.max_tokens_for_sage_llm += additional_sage_tokens
            if self._sage_llm is not None:
                self._sage_llm.max_token_usage = self.config.max_tokens_for_sage_llm * 2
            self.logger.log(f"**resume**: extend token allowance for sage "
                            f"LLM by {additional_sage_tokens} to {self.config.max_tokens_for_sage_llm}")
        self.config.pause_after_initial_solving_expansion = False
        self._execute_with_backtracking()

    def _execute_with_backtracking(self):

        def perform_backtracking(backtrack: Backtrack):
            while True:
                try:
                    self.backtrack(backtrack)
                    break
                except Backtrack as b2:
                    backtrack = b2

        try:
            while len(self.chain) > 0:
                try:
                    if self._pending_backtrack is not None:
                        backtrack = self._pending_backtrack
                        self._pending_backtrack = None
                        perform_backtracking(backtrack)
                    self._loop()
                    break
                except Backtrack as backtrack:
                    if self.config.pause_on_backtrack:
                        self._pending_backtrack = backtrack
                        raise Pause(f"Backtracking is requested for {backtrack}", backtrack.blame)
                    perform_backtracking(backtrack)
                except Pause as paused:
                    self.logger.log(f'Pause requested: {paused}\n')
                    raise paused
                except UnsolvableError:
                    raise
                except Exception as e:
                    self.logger.log_error(repr(e))
                    raise e
        except UnsolvableError as e:
            self.logger.log_error(str(e))

    def backtrack_to(self, step_number: int):
        if step_number < 0 or step_number >= len(self.chain):
            raise ValueError(f"step number must be in [0, {len(self.chain)-1}]")
        self.backtrack(Backtrack("Manual backtrack", blame=self.chain[step_number]))
        self._execute_with_backtracking()

    def backtrack(self, backtrack: Backtrack):
        blamed_step = _t.cast(Step, backtrack.blame)
        if _utils.safe_is_instance(blamed_step, TaoReplyStep):
            _t.cast(TaoReplyStep, blamed_step).record_criticisms([str(backtrack)])
        backtrack_to: Step|None = _t.cast(Step, backtrack.blame).created_by
        i = self.step_id(backtrack.blame if backtrack_to is None else backtrack_to)
        if i is None:
            i = len(self.chain) - 1
        while 0 <= i < len(self.chain):
            step = self.chain[i]
            if _utils.safe_is_instance(step, ExpandableStep):
                backtrack_to = step
                break
            i -= 1

        if backtrack_to is None or not _utils.safe_is_instance(backtrack_to, ExpandableStep):
            raise UnsolvableError(f"Sorry, I can't solve this problem or perform this task.")
        choices = _t.cast(ExpandableStep, backtrack_to).choices
        if (len(choices) > 0 and
                _utils.safe_is_instance(choices[-1], TaoReplyStep) and choices[-1] is not blamed_step):
            _t.cast(TaoReplyStep, choices[-1]).record_criticisms([str(backtrack)])

        reverted_steps = []
        while len(self.chain) > 0 and self.chain[-1] is not backtrack_to:
            reverted_steps.append(self.chain.pop(-1))
        self._waiting.clear() # as we backtrack, cancel all waiting steps
        if len(self.chain) == 0:
            raise UnsolvableError('Fail to solve! No more viable options')
        self._reverted_steps = reversed(reverted_steps)
        assert backtrack_to is self.chain[-1] # exactly at the end

        desc = _t.cast(ExpandableStep, backtrack_to).step_name_for_expanded
        self.logger.log(f'---\n<div style="color: white; background-color: black">\n')
        self.logger.log(f"# BACKTRACK to {desc}/{self.step_id(backtrack_to)} for: {str(backtrack)}\n")
        self.logger.log(f"</div>\n")
        _t.cast(ExpandableStep, backtrack_to).backtrack(self, backtrack)

    def _loop(self):
        while len(self.chain) > 0:
            if self.pending_pause is not None:
                reason = self.pending_pause
                self.request_pause(None)
                raise Pause(reason, self.chain[-1])
            last_step = self.chain[-1]
            if _utils.safe_is_instance(last_step, Idle):
                break
            if (_utils.safe_is_instance(last_step, DirectAnswerStep)
                    and _t.cast(DirectAnswerStep, last_step).is_final_step):
                self.summarize_final_answer()
                self._dequeue_waiting_step()
                continue
            self.check_token_usages()
            new_step = last_step.eval(self)
            if _utils.safe_is_instance(last_step, SummarizeStep) and new_step is None: # and successfully eval&checked
                self.logger.log(f"Completed final summarization. Taking care of {len(self._waiting)} clean-up chores")
                remaining = self._dequeue_waiting_step()
                while remaining is not None:
                    remaining.eval(self)
                    remaining = self._dequeue_waiting_step()
                return
            if new_step is not None:
                if new_step is not self.chain[-1]:
                    self._waiting.append(new_step)
            elif len(self._waiting) == 0:
                self.next_step()
            self._dequeue_waiting_step()

    def enqueue(self, step: StepABC):
        self._waiting.append(_t.cast(Step, step))

    def _dequeue_waiting_step(self) -> Step|None:
        if len(self._waiting) > 0:
            next_waiting = self._waiting.pop(0)
            self.chain.append(next_waiting) # dequeue first waiting
            return next_waiting
        return None

    def check_token_usages(self):
        if 0 < self.config.max_tokens <= self.llm.total_tokens:
            raise TokenUsageError(f"Regular LLM consumed {self.llm.total_tokens} tokens, "
                                  f"exceeded allowance of {self.config.max_tokens}", self.chain[-1])
        if self.llm is not self.sage_llm and 0 < self.config.max_tokens_for_sage_llm <= self.sage_llm.total_tokens:
            raise TokenUsageError(f"Smarter LLM consumed {self.sage_llm.total_tokens} tokens, "
                                  f"exceeded allowance of {self.config.max_tokens_for_sage_llm}", self.chain[-1])
        if self.llm is not self.file_merging_llm and 0 < self.config.max_tokens <= self.file_merging_llm.total_tokens:
            raise TokenUsageError(f"File merging LLM consumed {self.file_merging_llm.total_tokens} tokens, "
                                  f"exceeded allowance of {self.config.max_tokens}", self.chain[-1])

    def step_id(self, step) -> int|None:
        assert step is not None
        for i, elem in enumerate(self.chain):
            if elem is step:
                return i
        return None

    def select_steps(self, selector: _t.Callable[[int, StepABC], bool]|_t.Type,
                     except_step: StepABC=None, stop_at: StepABC=None) \
            -> list[StepABC]:
        steps: list[StepABC] = []
        for i, step in enumerate(self.chain):
            if not step.visible_in_chain and i < len(self.chain) - 1:
                continue # skip the expandable step except the last one
            if step is except_step:
                if step is stop_at:
                    break
                continue
            if (_inspect.isclass(selector) and _utils.safe_is_instance(step, selector)
                    or not _inspect.isclass(selector) and callable(selector) and selector(i, step)):
                steps.append(step)
            if step is stop_at:
                break
        return steps

    def show_conversation_thread(self, with_header=True, with_extras=False,
                                 selector: _t.Callable[[int, StepABC], bool] | None=None,
                                 except_step: StepABC=None,
                                 stop_at: StepABC=None) \
            -> list[tuple[str, str]]:
        conversation: list[tuple[str, str]] = []
        for i, step in enumerate(self.chain):
            if not step.visible_in_chain and i < len(self.chain) - 1:
                continue # skip the expandable step except the last one
            if step is except_step:
                if step is stop_at:
                    break
                continue
            if selector is None or selector(i, step):
                conversation.extend(step.show_in_thread(i, with_header=with_header, with_extras=with_extras))
            if step is stop_at:
                break
        return conversation

    def next_step(self):
        ask_next_step = NextStep(description='', role=ROLE_ORCHESTRATOR, step_name=None)
        self._waiting.append(ask_next_step)

    def is_init_solving_expansion(self):
        for i, step in enumerate(self.chain):
            if _utils.safe_is_instance(step, ExpandableStep) \
                    and i < len(self.chain) - 1 and not _utils.safe_is_instance(self.chain[i + 1], AskQuestionStep):
                return False
        return True

    def summarize_final_answer(self):
        last_step = self.chain[-1]
        if _utils.safe_is_instance(last_step, SummarizeStep): # already has the summarize step as the last step
            return None

        is_direct_answer_only = False
        if _utils.safe_is_instance(last_step, DirectAnswerStep):
            for i in range(len(self.chain) - 2, -1, -1):
                if _utils.safe_is_instance(self.chain[i], PresentTaskStep):
                    is_direct_answer_only = True
                    break
                elif _utils.safe_is_instance(self.chain[i], (DirectAnswerStep, AskPythonGenieStep, StepByStepPlan)):
                    break
            if is_direct_answer_only: # replace
                final_answer_step = SummarizeStep(n_verifications=self.config.n_final_checks)
                self._waiting.append(final_answer_step)
                return final_answer_step

        summarize_step = SummarizeStep(n_verifications=self.config.n_final_checks)
        self._waiting.append(summarize_step)
        return None

    def finalize_files(self):
        from taogpt.program import consolidate_updated_files
        consolidate_file_steps, shadowing_steps = consolidate_updated_files(self, self.chain, 'final file consolidation')
        for consolidate_file_step in consolidate_file_steps:
            self.chain.append(consolidate_file_step)
        self.remove_steps(steps=list(shadowing_steps.values()))

    def ask_questions(self, questions: list[str]) -> dict[str, str]:
        # for now just use the console input
        return ask_questions(self.input_fn, questions, self.config.ask_user_questions_in_one_prompt)

    def ask_genie(self, codes: list[str], step: StepABC) -> list[str]:
        self._verify_python_scope()
        prompt = "Tao asks to execute the following codes:" \
            if self.config.ask_user_before_execute_codes else None
        return [_utils.exec_code_and_collect_outputs(prompt, snippet.strip(), global_scope=self._python_scope)
                for snippet in codes]

    def reset(self):
        super().reset()
        self.llm.reset()
        self._chain = []
        self._reverted_steps = None
        self._create_python_scope()

    def _create_python_scope(self):
        import time
        self._python_scope = {'_taogpt_orchestrator_python_scope_sig': time.time()}

    def _verify_python_scope(self):
        assert self._python_scope is not None
        assert _utils.safe_is_instance(self._python_scope['_taogpt_orchestrator_python_scope_sig'], float)

    def handle_parse_error(self,
                           e: Exception,
                           n_retries: int,
                           prompts: list[tuple[str, str]],
                           prompts_to_be_sent: list[tuple[str, str]],
                           response: str,
                           retry_prompt: str):
        if n_retries >= self.config.max_retries:
            raise e
        if _utils.safe_is_instance(e, ParseError):
            prompts_to_be_sent.clear()
            prompts_to_be_sent.extend(prompts)
            prompts_to_be_sent.append((ROLE_TAO, response))
            message = retry_prompt.format(error=str(e))
            prompts_to_be_sent.append((ROLE_ORCHESTRATOR, message))
            self.logger.log(f"\n***RETRY***\n{message}")

def ask_questions(input_fn, questions: list[str], one_prompt: bool) -> dict[str, str]:
    if one_prompt:
        user_prompt = "Tao wants to ask:\n"
        user_prompt += "\n".join([f"{i+1}. {questions[i]}" for i in range(len(questions))])
        user_prompt += '\n(Reply format: "1. answer to question 1; 2. ...". Reply "cancel" to cancel.)'
        ui_prompt = user_prompt
        while True:
            reply = input_fn(ui_prompt).strip()
            if reply.lower() == 'cancel':
                raise KeyboardInterrupt("User cancelled")
            answers = [_re.sub(r"\d+\.\s*", '', s) for s in _re.split(r";\s+\d+\.\s+", reply)]
            if len(answers) != len(questions):
                ui_prompt = f"ERROR: there are {len(questions)} but found {len(answers)} answers.\n{ui_prompt}"
                continue
            return {q: a for q, a in zip(questions, answers)}
    answers = dict()
    for i in range(len(questions)):
        user_prompt = f'{questions[i]}\n(Reply "cancel" to cancel.)'
        reply = input_fn(user_prompt).strip()
        if reply.lower() == 'cancel':
            raise KeyboardInterrupt("User cancelled")
        answers[questions[i]] = reply
    return answers

