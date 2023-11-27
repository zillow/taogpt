from __future__ import annotations
import dataclasses as _dc
import typing as _t
import datetime as _datetime
import json as _json

import taogpt.md_logging
from . import UnsolvableError, MarkdownLogger, TokenUsageError
from .llm_model import *
from .program import *
import taogpt.utils as _utils


class Orchestrator(Executor):

    def __init__(self, *,
                 config: Config,
                 llm: LLM,
                 prompts: PromptDb,
                 markdown_logger: taogpt.logging.MarkdownLogger,
                 sage_llm: LLM | None = None,
                 **kwargs):
        super().__init__(**kwargs)
        self._config = Config(**_dc.asdict(config))
        self._llm = llm
        self._prompts = prompts
        self._markdown_logger = markdown_logger
        self._sage_llm = sage_llm

        self._chain: _t.List[Step] = []
        self._create_python_scope()
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
        n = len(self._chain)
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
    def logger(self) -> MarkdownLogger:
        return self._markdown_logger

    @property
    def chain(self) -> _t.List[Step]:
        return self._chain

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
            root_step = PresentTaskStep(previous=None, description=task, role=ROLE_USER)
        elif _utils.safe_is_instance(task, PresentTaskStep):
            root_step = task
        else:
            raise ValueError(f"Expecting string description of task "
                             f"or a PresentTaskStep object, got {type(task)}")
        self.reset()
        self._chain.append(root_step)
        if self.config.analyze_first:
            init_analysis_step = AnalysisStep(previous=root_step, description='', role=ROLE_ORCHESTRATOR)
            self._chain.append(init_analysis_step)
        self._execute_with_backtracking()

    def log_configs(self, logger: MarkdownLogger=None):
        if logger is None:
            logger = self.logger
        today = _datetime.date.today().strftime('%Y/%m/%d')
        logger.log(f"Date: {today}", role='debug')
        logger.log(f"**Configurations for {self.__class__.__name__}**", role='debug')
        llm_repr = repr(self.llm)
        sage_llm_repr = repr(self.sage_llm)
        logger.log(f"LLM: {llm_repr}")
        logger.log(f"Sage LLM: {sage_llm_repr}")
        logger.log(f"""```json
{_json.dumps(_dc.asdict(self.config), indent=2)}
```
        """, role='debug')

    def resume(self, additional_tokens: int=None,
               unblock_initial_expansion: bool=False,
               additional_sage_tokens: int=None):
        if additional_tokens is not None:
            self.config.max_tokens += additional_tokens
            self.logger.log(f"**resume**: extend token allowance by {additional_tokens} to {self.config.max_tokens}")
        if additional_sage_tokens is not None:
            self.config.max_tokens_for_sage_llm += additional_sage_tokens
            self.logger.log(f"**resume**: extend token allowance for sage "
                            f"LLM by {additional_sage_tokens} to {self.config.max_tokens_for_sage_llm}")
        if unblock_initial_expansion:
            self.config.pause_after_initial_solving_expansion = False
        self._execute_with_backtracking()

    def _execute_with_backtracking(self):
        try:
            while len(self._chain) > 0:
                try:
                    self._loop()
                    break
                except Backtrack as backtrack:
                    while True:
                        try:
                            self.backtrack(backtrack)
                            break
                        except Backtrack as b2:
                            backtrack = b2
        except UnsolvableError as e:
            prev: Step|None = self._chain[-1] if len(self._chain) > 0 else None
            self._chain.append(FinalAnswerStep(previous=prev, description=str(e), role=ROLE_TAO))

    def backtrack_to(self, step_number: int):
        if step_number < 0 or step_number >= len(self._chain):
            raise ValueError(f"step number must be in [0, {len(self._chain)-1}]")
        self.backtrack(Backtrack("Manual backtrack", self._chain[step_number]))
        self._execute_with_backtracking()

    def backtrack(self, backtrack: Backtrack):
        while len(self._chain) > 0:
            last_step = self._chain.pop(-1)
            if last_step is backtrack.blame: # found the culprit
                self._halt_on_initial_steps(last_step)
                break

        while len(self._chain) > 0:
            last_step = self._chain.pop(-1)
            self._halt_on_initial_steps(last_step)
            retryable = last_step.retryable(self.config)
            if retryable:
                last_step.backtrack(self, backtrack)
                self._chain.append(last_step)
                cls = last_step.__class__.__name__
                desc = _utils.safe_subn(
                    last_step.step_name if last_step.step_name is not None else last_step.description)
                self.logger.log(f'---\n<div style="color: white; background-color: black">\n')
                self.logger.log(f"# BACKTRACK to {desc}@{cls}/{last_step.step_id}\n")
                self.logger.log(f"Why: {str(backtrack)}\n")
                self.logger.log(f"</div>\n")
                break
        if len(self._chain) == 0: # empty, nothing to backtrack
            raise UnsolvableError('Fail to solve! No more viable options')

    def _halt_on_initial_steps(self, last: StepABC):
        if _utils.safe_is_instance(last, (PresentTaskStep, AnalysisStep)):
            self._chain.append(_utils.cast(last, Step))
            raise UnsolvableError('Tao cannot solve the problem.')

    def _loop(self):
        while len(self.chain) > 0:
            if self.pending_pause is not None:
                reason = self.pending_pause
                self.request_pause(None)
                raise Pause(reason, self.chain[-1])
            self.check_token_usages()
            last_step = self._chain[-1]
            if _utils.safe_is_instance(last_step, DirectAnswerStep) \
                    and _utils.cast(last_step, DirectAnswerStep).is_final_step:
                self.summarize_final_answer()
                continue
            new_step = last_step.eval(self)
            if _utils.safe_is_instance(last_step, FinalAnswerStep): # and successfully eval/checked
                return
            if new_step is not None:
                self._chain.append(new_step)
            else:
                self.next_step()

    def check_token_usages(self):
        if 0 < self.config.max_tokens <= self.llm.total_tokens:
            raise TokenUsageError(f"Regular LLM consumed {self.llm.total_tokens} tokens, "
                                  f"exceeded allowance of {self.config.max_tokens}", self.chain[-1])
        if self.llm is not self.sage_llm and 0 < self.config.max_tokens_for_sage_llm <= self.sage_llm.total_tokens:
            raise TokenUsageError(f"Smarter LLM consumed {self.sage_llm.total_tokens} tokens, "
                                  f"exceeded allowance of {self.config.max_tokens_for_sage_llm}", self.chain[-1])

    def show_conversation_thread(self, with_header=True, with_extras=False,
                                 selector: _t.Callable[[int, StepABC], bool] | None=None) \
            -> [(str, str)]:
        conversation: [(str, str)] = []
        for i, step in enumerate(self._chain):
            if not step.visible_in_chain and i < len(self._chain) - 1:
                continue # skip the expandable step except the last one
            if selector is None or selector(i, step):
                conversation.extend(step.show_in_thread(with_header=with_header, with_extras=with_extras))
        return conversation

    def next_step(self):
        start_solving = self.is_first_solving_expansion()
        step = self._chain[-1]
        if start_solving:
            work_prompt = self.prompts.orchestrator_proceed
            first_expansion = self.config.initial_expansion if start_solving else self.config.first_expansion
            work_next_step = ProceedStep(previous=step, description=work_prompt, role=ROLE_ORCHESTRATOR,
                                         first_expansion=first_expansion,
                                         max_expansion=self.config.max_search_expansion)
            work_next_step.set_step_name("start working on the problem")
            self._chain.append(work_next_step)
        else:
            ask_next_step = NextStep(previous=step, description='', role=ROLE_ORCHESTRATOR,
                                     first_expansion=1,
                                     max_expansion=self.config.max_search_expansion)
            ask_next_step.set_step_name(self.current_step_name)
            self._chain.append(ask_next_step)

    def is_first_solving_expansion(self):
        for i, step in enumerate(self.chain):
            if _utils.safe_is_instance(step, ExpandableStep) \
                    and i < len(self.chain) - 1 and not _utils.safe_is_instance(self.chain[i + 1], AskQuestionStep):
                return False
        return True

    def summarize_final_answer(self):
        last_step = self.chain[-1]
        if _utils.safe_is_instance(last_step, FinalAnswerStep):
            return

        is_direct_answer_only = False
        if _utils.safe_is_instance(last_step, DirectAnswerStep):
            for i in range(len(self._chain) - 2, -1, -1):
                if _utils.safe_is_instance(self._chain[i], PresentTaskStep):
                    is_direct_answer_only = True
                    break
                elif _utils.safe_is_instance(self._chain[i], (DirectAnswerStep, PythonGenieReplyStep, StepByStepPlan)):
                    break
            if is_direct_answer_only: # replace
                final_answer_step = FinalAnswerStep(previous=self._chain[-2],
                                                    description=last_step.description,
                                                    role=ROLE_TAO)
                self._chain[-1] = final_answer_step
                return

        summarize_step = SummarizeStep(previous=self.chain[-1],
                                       description='',
                                       role=ROLE_ORCHESTRATOR,
                                       first_expansion=1,
                                       max_expansion=self.config.max_search_expansion)
        summarize_step.set_step_name(self.current_step_name)
        self._chain.append(summarize_step)

    def record_criticisms(self, criticisms: [str]):
        for step in reversed(self._chain):
            if _utils.safe_is_instance(step, ExpandableStep):
                step: ExpandableStep
                step.record_criticism(criticisms)

    def ask_questions(self, questions: [str]) -> {str: str}:
        # for now just use the console input
        return ask_questions(self.input_fn, questions, self.config.ask_user_questions_in_one_prompt)

    def ask_genie(self, codes: [str], step: StepABC) -> [str]:
        self._verify_python_scope()
        prompt = "Tao asks to execute the following codes:" \
            if self.config.ask_user_before_execute_codes else None
        snippet: str|None = None
        try:
            return [_utils.exec_code_and_collect_outputs(prompt, snippet.strip(), global_scope=self._python_scope)
                    for snippet in codes]
        except Exception as e:
            self.record_criticisms([f"""Python Genie reported error: {str(e)} when running this code snippet:
```python
{snippet}
```
"""])
            raise Backtrack("Python execution error", blame=step)

    def reset(self):
        super().reset()
        self.llm.reset()
        self._chain = []
        self._create_python_scope()

    def _create_python_scope(self):
        self._python_scope = {'_taogpt_orchestrator_python_scope_sig': time.time()}

    def _verify_python_scope(self):
        assert self._python_scope is not None
        assert _utils.safe_is_instance(self._python_scope['_taogpt_orchestrator_python_scope_sig'], float)

    def vote(self, system_prompt: str, prompts: [(str, str)], parser: _t.Callable[[str], _t.Any],
             reason: str=None, step_id:str=None, min_threshold=0.0, majority=1,
             collapse_contents: {str: str}=None) -> (_t.Any, int|float):
        assert majority == 1 # todo: can't handle multiple votes yet
        prompt_db: PromptDb = self.prompts
        min_threshold = min_threshold * majority
        rankings = dict()
        i = 0
        while i < majority:
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            response: str = ''
            while n_retries < self.config.max_retries:
                try:
                    response = self.llm.ask(system_prompt,
                                            prompts_to_be_sent,
                                            reason=reason,
                                            step_id=f"{step_id}",
                                            temperature=0.0 if i == 0 else 0.1,
                                            log_request=i == 0, collapse_contents=collapse_contents)
                    result, data = parser(response)
                    existing = rankings.get(result, (0, data))
                    existing = existing[0] + 1, data # todo this can't handle multiple votes yet
                    rankings[result] = existing
                    i += 1
                    break
                except Exception as e:
                    n_retries += 1
                    self.handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                            prompt_db.orchestrator_parse_error)
        choices = sorted([item for item in rankings.items() if item[1][0] >= min_threshold],
                         key=lambda item: item[1][0], reverse=True)
        if len(choices) == 0:
            raise Backtrack('No candidate passes min. threshold.', blame=self._chain[-1])
        result = choices[0]
        return result[0], result[1][1]

    def handle_parse_error(self,
                           e: Exception,
                           n_retries: int,
                           prompts: [(str, str)],
                           prompts_to_be_sent: [(str, str)],
                           response: str,
                           retry_prompt: str):
        if n_retries >= self.config.max_retries:
            raise e
        if _utils.safe_is_instance(e, ParseError) and len(prompts_to_be_sent) <= len(prompts):
            prompts_to_be_sent.append((ROLE_TAO, response))
            message = retry_prompt.format(error=str(e))
            prompts_to_be_sent.append((ROLE_ORCHESTRATOR, message))
            self.logger.log(f"\n***RETRY***\n{message}")

def ask_questions(input_fn, questions: [str], one_prompt: bool) -> {str: str}:
    if one_prompt:
        user_prompt = "Tao wants to ask:\n"
        user_prompt += "\n".join([f"{i+1}. {questions[i]}" for i in range(len(questions))])
        user_prompt += '\n(Reply format: "1. answer to question 1; 2. ...". Reply "cancel" to cancel.)'
        ui_prompt = user_prompt
        while True:
            reply = input_fn(ui_prompt).strip()
            if reply.lower() == 'cancel':
                raise KeyboardInterrupt("User cancelled")
            answers = [re.sub(r"\d+\.\s*", '', s) for s in re.split(r";\s+\d+\.\s+", reply)]
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

