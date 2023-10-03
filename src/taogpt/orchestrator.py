from __future__ import annotations
import dataclasses as _dc
import typing as _t
import math as _math
import datetime as _datetime
from frozenlist import FrozenList as _FrozenList

from . import Config, Executor, UnsolvableError, MarkdownLogger
from .llm_model import *
from .program import *
import taogpt.utils as _utils


class Orchestrator(Executor):

    def __init__(self, *,
                 config: Config,
                 llm: LLM,
                 prompts: PromptDb,
                 markdown_logger: _utils.MarkdownLogger,
                 sage_llm: LLM | None = None):
        self._config = type(config)(**_dc.asdict(config))
        self._llm = llm
        self._prompts = prompts
        self._markdown_logger = markdown_logger
        self._sage_llm = sage_llm

        self._chain: [Invocation] = []
        self._frozen_chain: _FrozenList | None = None
        if self.config.max_tokens_for_sage_llm is None:
            if self._sage_llm is not None and id(self._llm) != id(self._sage_llm):
                self.config.max_tokens_for_sage_llm = self.config.max_tokens // 3
            else:
                self.config.max_tokens_for_sage_llm = self.config.max_tokens
        else:
            self.config.max_tokens_for_sage_llm = self.config.max_tokens_for_sage_llm

    def __repr__(self) -> str:
        llm_repr = repr(self.llm)
        sage_llm_repr = repr(self.sage_llm)
        n = len(self._chain)
        return f"{self.__class__.__name__}(LLMs={llm_repr}/{sage_llm_repr},invocations={n})"

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
    def chain(self) -> _t.List[Invocation]:
        return self._chain

    def start(self, task: str | Step, analyze_first=False):
        today = _datetime.date.today().strftime('%Y/%m/%d')
        self.logger.log(f"Date: {today}, Model: {self.llm.model_id}")
        if isinstance(task, str):
            root_step = PresentTaskStep(None, task, role=ROLE_USER)
        elif isinstance(task, PresentTaskStep):
            root_step = task
        else:
            raise ValueError(f"Expecting string description of task "
                             f"or a PresentTaskStep object, got {type(task)}")
        self.reset()
        self._chain.append(Invocation(root_step, _executor=self))
        if analyze_first:
            init_analysis_step = AnalysisStep(root_step, '', ROLE_ORCHESTRATOR)
            self._chain.append(Invocation(init_analysis_step, _executor=self))
        self._execute_with_backtracking()

    def resume(self, additional_tokens: int=None, additional_tokens_for_smarter_llm: int=None):
        if additional_tokens is not None:
            self.config.max_tokens += additional_tokens
            print(f"extend token allowance by {additional_tokens} to {self.config.max_tokens}")
        if additional_tokens_for_smarter_llm is not None:
            self.config.max_tokens_for_sage_llm += additional_tokens_for_smarter_llm
            print(f"extend token allowance for smarter LLM by {additional_tokens_for_smarter_llm} "
                  f"to {self.config.max_tokens_for_sage_llm}")
        self._execute_with_backtracking()

    def _execute_with_backtracking(self):
        try:
            while len(self._chain) > 0:
                try:
                    self._loop()
                    self._frozen_chain = _FrozenList(self._chain)
                    break
                except Backtrack as backtrack:
                    self.backtrack(backtrack)
        except UnsolvableError as e:
            prev: Invocation|None = self._chain[-1] if len(self._chain) > 0 else None
            final_inv = Invocation(
                FinalAnswerStep(prev.step if prev is not None else None, str(e), ROLE_TAO),
                _executor=self
            )
            self._chain.append(final_inv)

    def backtrack_to(self, step_number: int):
        if step_number < 0 or step_number >= len(self._chain):
            raise ValueError(f"step number must be in [0, {len(self._chain)-1}]")
        self.backtrack(Backtrack("Manual backtrack", self._chain[step_number]))
        self._execute_with_backtracking()

    def backtrack(self, backtrack: Backtrack):
        self._frozen_chain = _FrozenList(self._chain)
        while len(self._chain) > 0:
            last: Invocation = self._chain.pop(-1)
            if id(last) == id(backtrack.blame): # found the culprit
                self._halt_on_initial_steps(last)
                break

        last: Invocation|None = None
        while len(self._chain) > 0:
            last: Invocation = self._chain.pop(-1)
            last_step: Step = last.step
            self._halt_on_initial_steps(last)
            retryable = last_step.retryable(last)
            if retryable:
                last_step.backtrack(last, backtrack)
                self._chain.append(last)
                cls = last_step.__class__.__name__
                desc = _utils.safe_subn(last_step.description)
                self.logger.log(f'---\n<div style="color: white; background-color: black">\n')
                self.logger.log(f"# BACKTRACK to {cls}:{desc}@{last_step.step_id}\n")
                self.logger.log(f"</div>\n")
                break
        if len(self._chain) == 0: # empty, nothing to backtrack
            raise UnsolvableError('Fail to solve! No more viable options')

    def _halt_on_initial_steps(self, last: Invocation):
        if isinstance(last.step, (PresentTaskStep, AnalysisStep)):
            self._chain.append(last)
            raise UnsolvableError('Tao cannot solve the problem.')

    def _loop(self):
        while True:
            invocation = self._chain[-1]
            new_step = invocation.step.eval(invocation)
            invocation.execution_count += 1
            while new_step is not None:
                new_invocation = Invocation(new_step, _executor=self)
                self._chain.append(new_invocation) # note: we don't necessary eval the new resulting step
                if isinstance(new_step, DirectAnswerStep) and new_step.is_final_step:
                    self.summarize_final_answer()
                    return
                self.check_token_usages()
                new_step = new_step.eval(new_invocation)
            new_step = self.next_step()
            if new_step is None:
                self.summarize_final_answer()
                return
            new_invocation = Invocation(new_step, _executor=self)
            self._chain.append(new_invocation)
            if isinstance(new_step, FinalAnswerStep):
                return
            self.check_token_usages()

    def check_token_usages(self):
        if 0 < self.config.max_tokens <= self.llm.total_tokens:
            raise RuntimeError(f"Regular LLM consumed {self.llm.total_tokens} tokens, "
                               f"exceeded allowance of {self.config.max_tokens}")
        if id(self.llm) != id(self.sage_llm) and 0 < self.config.max_tokens_for_sage_llm <= self.sage_llm.total_tokens:
            raise RuntimeError(f"Smarter LLM consumed {self.sage_llm.total_tokens} tokens, "
                               f"exceeded allowance of {self.config.max_tokens_for_sage_llm}")

    def show_conversation_thread(self, with_extras=False, selector: _t.Callable[[int, Invocation], bool]|None=None) \
            -> [(str, str)]:
        conversation: [(str, str)] = []
        for i, invocation in enumerate(self._chain):
            if selector is None or selector(i, invocation):
                conversation.extend(invocation.step.show_in_thread(invocation, with_extras=with_extras))
        return conversation

    def next_step(self) -> Step:
        system_prompt = self.prompts.system_step_expansion
        start_sovling = self.need_search_expansion_at_next_step()
        step = self._chain[-1].step
        if start_sovling:
            work_prompt = self.prompts.orchestrator_proceed
        else:
            prompts = self.show_conversation_thread()
            direct_answer = self.prompts.tao_template_direct_step_answer
            work_prompt = self.prompts.tao_templates.format(examples='', direct_answer_template=direct_answer)
            prompts.append((ROLE_ORCHESTRATOR, work_prompt))
            prompts.append((ROLE_ORCHESTRATOR, self.prompts.orchestrator_next_step))
            decision, (answer, plan) = self.vote(system_prompt,
                                       prompts,
                                       lambda reply: parse_next_step_reply(reply),
                                       reason='next_step',
                                       step_id=f"{step.step_id}",
                                       collapse_contents={'next_step': work_prompt})
            assert decision is not None
            assert answer is not None
            if decision == NEXT_I_WANT_TO_WORK_AT:
                work_prompt = self.prompts.orchestrator_proceed_to_step.format(step=answer)
                return ProceedStep(
                    step,
                    work_prompt,
                    role=ROLE_ORCHESTRATOR,
                    initial_expansion=self.config.initial_expansion,
                    max_expansion=self.config.max_search_expansion,
                    first_problem_solving_step=start_sovling,
                    choices=[parse_to_step(step, plan)]
                )
            else:
                return parse_to_step(step, answer)
        work_next_step = ProceedStep(step, work_prompt, role=ROLE_ORCHESTRATOR,
                                     initial_expansion=self.config.initial_expansion,
                                     max_expansion=self.config.max_search_expansion,
                                     first_problem_solving_step=start_sovling)
        return work_next_step

    def need_search_expansion_at_next_step(self):
        for i, invocation in enumerate(self.chain):
            if isinstance(invocation.step, ExpandableStep) \
                    and i < len(self.chain) - 1 and not isinstance(self.chain[i + 1].step, AskQuestionStep):
                return False
        return True

    def summarize_final_answer(self) -> FinalAnswerStep:
        if self.config.check_final:
            self.check_final_solution(self._chain[-1])

        is_direct_answer_only = False
        if isinstance(self._chain[-1].step, DirectAnswerStep):
            for i in range(len(self._chain) - 2, -1, -1):
                if isinstance(self._chain[i].step, PresentTaskStep):
                    is_direct_answer_only = True
                    break
                elif isinstance(self._chain[i].step, (DirectAnswerStep, PythonGenieReplyStep, StepByStepPlan)):
                    break
            last_step = self._chain[-1].step
            if is_direct_answer_only:
                final_answer_step = FinalAnswerStep(last_step.previous, last_step.description, ROLE_TAO)
                self._chain[-1].step = final_answer_step
                return final_answer_step

        system_prompt = self.prompts.sage
        prompts = self.show_conversation_thread()
        summarize_prompt = self.prompts.orchestrator_summarize
        prompts.append((ROLE_ORCHESTRATOR, summarize_prompt))
        n_retries= 0
        ex: Exception|None = None
        while n_retries < MAX_RETRIES:
            try:
                response = self.llm.ask(system_prompt, prompts,
                                        reason='summarize',
                                        step_id=f"summarize/{n_retries}",
                                        temperature=0.0,
                                        collapse_contents=dict(),
                                        log_request=n_retries == 0)
                final_answer_step = FinalAnswerStep(self._chain[-1].step, response, ROLE_TAO)
                new_invocation = Invocation(final_answer_step, _executor=self)
                self._chain.append(new_invocation)
                return final_answer_step
            except Backtrack as e:
                raise e
            except Exception as e:
                ex = e
                n_retries += 1
        raise ex

    def check_final_solution(self, invocation: Invocation):
        system_prompt = self.prompts.sage
        prompts = self.show_conversation_thread()
        sage_prompt = self.prompts.sage_final_check
        prompts.append((ROLE_SAGE, sage_prompt))
        self.check_execution_state(system_prompt, prompts, invocation, parse_final_response,
                                   reason='check_final_solution')

    def check_execution_state(self,
                              system_prompt: str,
                              prompts: [(str, str)],
                              invocation: Invocation,
                              response_parser: _t.Callable[[str], (bool, str)],
                              max_voting_factor=MAX_VOTING_FACTOR,
                              reason='check_state',
                              collapse_contents: {str:str}=None):
        all_criticism: [str] = []
        min_yes_needed = int(max_voting_factor * CONTINUE_VOTE_QUORUM)
        max_no_allowed = int(_math.ceil(max_voting_factor * (1 - CONTINUE_VOTE_QUORUM)))
        n_success, n_true = 0, 0
        for i in range(max_voting_factor):
            n_retries = 0
            prompts_to_be_sent = prompts.copy()
            response: str = ''
            while n_retries < MAX_RETRIES:
                try:
                    response = self.sage_llm.ask(
                        system_prompt,
                        prompts_to_be_sent,
                        reason=reason,
                        step_id=f"{invocation.step.step_id}/{i}",
                        temperature=0.0 if n_success == 0 else 0.1,
                        collapse_contents=collapse_contents,
                        log_request=i == 0)
                    result, text = response_parser(response)
                    n_success += 1
                    if result:
                        n_true += 1
                    elif text is not None and len(text.strip()) > 0:
                        all_criticism.append(text.strip())
                    if n_true >= min_yes_needed:
                        break
                    if (n_success - n_true) >= max_no_allowed:
                        break
                except Exception as e:
                    n_retries += 1
                    self._handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                             self.prompts.orchestrator_parse_error)
        if len(all_criticism) > 0:
            self.record_criticisms(all_criticism)
        if n_success == 0:
            raise RuntimeError('Sage failed to perform execution state check')
        if (n_true / n_success) < CONTINUE_VOTE_QUORUM:
            fail_votes = 1. - (n_true / n_success)
            raise Backtrack(f'We are on a dead path with {fail_votes * 100:.1f}% of votes', blame=invocation)

    def record_criticisms(self, criticisms: [str]):
        for invocation in self._chain:
            if isinstance(invocation.step, ExpandableStep):
                invocation.step.record_criticism(criticisms)

    def ask_user(self, questions: [str], input_fn=input) -> str:
        # for now just use the console input
        return ask_questions(input_fn, questions, self.config.ask_user_questions_in_one_prompt)

    def ask_genie(self, codes: [str]) -> [str]:
        prompt = "Tao asks to execute the following codes:" \
            if self.config.ask_user_before_execute_codes else None
        return [_utils.exec_code_and_collect_outputs(prompt, snippet.strip()) for snippet in codes]

    def find_last_criticisms(self, invocation: Invocation) -> {int: {str}}:
        criticism: {int: {str}} = dict()
        for i in range(len(self._chain)):
            step = self._chain[i].step
            if isinstance(step, ExpandableStep):
                if len(step.collected_criticisms) > 0:
                    criticism = step.collected_criticisms
                if id(self._chain[i]) == id(invocation):
                    break
        return criticism

    def reset(self):
        self.llm.reset()
        self._chain = []
        self._frozen_chain = _FrozenList()

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
            while n_retries < MAX_RETRIES:
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
                    self._handle_parse_error(e, n_retries, prompts, prompts_to_be_sent, response,
                                             prompt_db.orchestrator_parse_error)
        choices = sorted([item for item in rankings.items() if item[1][0] >= min_threshold],
                         key=lambda item: item[1][0], reverse=True)
        if len(choices) == 0:
            raise Backtrack('No candidate passes min. threshold.', blame=self._chain[-1])
        result = choices[0]
        return result[0], result[1][1]

    def _handle_parse_error(self, e: Exception, n_retries, prompts, prompts_to_be_sent, response: str, retry_req: str):
        if isinstance(e, ParseError) and len(prompts_to_be_sent) <= len(prompts):
            prompts_to_be_sent.append((ROLE_TAO, response))
            message = retry_req.format(error=str(e))
            prompts_to_be_sent.append((ROLE_ORCHESTRATOR, message))
            self.logger.log(f"\n***RETRY***\n{message}")
        if n_retries >= MAX_RETRIES:
            raise e

def ask_questions(input_fn, questions: [str], one_prompt: bool):
    if one_prompt:
        user_prompt = "Tao wants to ask:\n"
        user_prompt += "\n".join([f"{i+1}. {questions[i]}" for i in range(len(questions))])
        user_prompt += '\n(Reply "cancel" to cancel.)'
        reply = input_fn(user_prompt).strip()
        if reply.lower() == 'cancel':
            raise KeyboardInterrupt("User cancelled")
        return reply
    reply = ""
    for i in range(len(questions)):
        reply_text = questions[i]
        if reply_text.strip() == 'cancel':
            raise KeyboardInterrupt("User cancelled request.")
        user_prompt = f'{questions[i]} (Reply "cancel" to cancel.)'
        reply_lines = input_fn(user_prompt).split('\n')
        bullet = f"{i + 1}. "
        indent = ' ' * len(bullet)
        reply_text = f"{bullet}{reply_lines[0]}"
        for i in range(1, len(reply_lines)):
            if reply_lines[i].strip().lower() == 'cancel':
                raise KeyboardInterrupt("User cancelled")
            reply_text += '\n' + indent + reply_lines[i].strip()
        reply += reply_text + '\n'
    return reply

