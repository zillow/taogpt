from __future__ import annotations
import dataclasses as _dc
import typing as _t
import math as _math
from frozenlist import FrozenList as _FrozenList

from .runtime_env import *
from .tao_model import *
from .program import *
import taogpt.utils as _utils


@_dc.dataclass
class Orchestrator(Executor):
    llm: LLM = _utils.Frozen()
    prompts: PromptSet = _utils.Frozen()
    markdown_logger: _utils.MarkdownLogger = _utils.Frozen()
    max_tokens: int = 100000

    def __post_init__(self):
        self._chain: [Invocation] = []
        self._frozen_chain: _FrozenList | None = None

    @property
    def logger(self) -> MarkdownLogger:
        return self.markdown_logger

    def start(self, task: str | Step, try_intuition=False):
        if isinstance(task, str):
            root_step = InitialStep(None, 0, task, role=ROLE_USER)
        elif isinstance(task, InitialStep):
            root_step = task
        else:
            raise ValueError(f"Expecting string description of task or a Step object, got {type(task)}")
        self.reset()
        self._chain.append(Invocation(root_step, _executor=self))
        if try_intuition:
            init_analysis_step = AskForAnalysisStep(root_step, root_step.step_id+1, '', ROLE_ORCHESTRATOR)
            self._chain.append(Invocation(init_analysis_step, _executor=self))
        self._execute_with_backtracking()

    def resume(self, additional_token_allowance: int|None=None):
        if self.llm.total_tokens >= self.max_tokens:
            additional_token_allowance = (additional_token_allowance or self.max_tokens)
            if self.max_tokens > 0:
                self.max_tokens += additional_token_allowance
            print(f"extend token allowance by {additional_token_allowance} to {self.max_tokens}")
            self._execute_with_backtracking()
    def _execute_with_backtracking(self):
        done = False
        try:
            while not done and len(self._chain) > 0:
                try:
                    done = self._loop()
                    self._frozen_chain = _FrozenList(self._chain)
                except Backtrack as backtrack:
                    self.backtrack(backtrack)
        except UnsolvableError as e:
            prev: Invocation|None = self._chain[-1] if len(self._chain) > 0 else None
            final_inv = Invocation(
                FinalAnswerStep(prev, prev.step.step_id + 1 if prev is not None else 0, str(e), ROLE_ORCHESTRATOR),
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
        if isinstance(last.step, (InitialStep, TaoAnalysisStep)):
            self._chain.append(last)
            raise UnsolvableError('Tao cannot solve the problem.')

    def _loop(self) -> bool:
        done = False
        while not done and len(self._chain) > 0:
            invocation = self._chain[-1]
            new_step = invocation.step.eval(invocation)
            invocation.execution_count += 1
            while new_step is not None:
                new_invocation = Invocation(new_step, _executor=self)
                if isinstance(new_step, TaoReplyStep):
                    new_invocation.scratchpad = new_step.scratchpad
                self._chain.append(new_invocation) # note: we don't necessary eval the new resulting step
                if new_step.need_to_check_dead_end(new_invocation):
                    self.check_dead_end(self._chain[-1])
                new_step = new_step.eval(new_invocation)
            new_step = self.next_step()
            assert new_step is not None and isinstance(new_step, (ProceedStep, FinalAnswerStep))
            new_invocation = Invocation(new_step, _executor=self)
            self._chain.append(new_invocation)
            if isinstance(new_step, FinalAnswerStep):
                self.check_final_solution(self._chain[-1])
                return True
            if self.max_tokens > 0 and self.llm.total_tokens >= self.max_tokens:
                raise RuntimeError(f"Used {self.llm.total_tokens}, exceeded token allowance of {self.max_tokens}")
        return done or len(self._chain) == 0

    def show_conversation_thread(self, with_extras=False, selector: _t.Callable[[int, Invocation], bool]|None=None) \
            -> [(str, str)]:
        conversation: [(str, str)] = []
        for i, invocation in enumerate(self._chain):
            if selector is None or selector(i, invocation):
                conversation.extend(invocation.step.show_in_thread(invocation, with_extras=with_extras))
        return conversation

    def find_scratchpad(self) -> str:
        for i in range(len(self._chain)-1, -1, -1):
            invocation = self._chain[i]
            scratchpad = _utils.str_or_blank(invocation.scratchpad)
            if scratchpad != '':
                return scratchpad
        return ''

    def next_step(self) -> ProceedStep | FinalAnswerStep:
        step = self._chain[-1].step
        system_prompt = self.prompts.system_step_expansion
        prompts = self.show_conversation_thread()
        work_prompt = self.prompts.orchestrator_next_step
        prompts.append((ROLE_ORCHESTRATOR, work_prompt))
        scratchpad = self.find_scratchpad()
        if len(_utils.str_or_blank(scratchpad)) > 0:
            prompts.append((ROLE_ORCHESTRATOR, f"### {SCRATCHPAD_AT_THIS_POINT}\n{scratchpad}\n"))
        decision, next = self.vote(system_prompt, prompts, lambda reply: parse_next_step_reply(reply),
                                   reason='next_step', step_id=step.step_id,
                                   collapse_contents={'next_step': work_prompt})
        if decision == DONE:
            return FinalAnswerStep(step, step.step_id+1, next, role=ROLE_SOLVER)
        work_prompt = self.prompts.orchestrator_proceed.format(
            description=decision,
            scratchpad=self.find_scratchpad()
        )
        work_next_step = ProceedStep(step, step.step_id + 1, work_prompt, role=ROLE_ORCHESTRATOR)
        return work_next_step

    def check_dead_end(self, invocation: Invocation):
        system_prompt = self.prompts.sage
        prompts = self.show_conversation_thread()
        sage_prompt = self.prompts.sage_check_dead_end
        prompts.append((ROLE_SAGE, sage_prompt))
        self.check_execution_state(system_prompt, prompts, invocation, parse_dead_end_check_response,
                                   reason='check_dead_end',
                                   collapse_contents={'check_dead_end': sage_prompt})

    def check_final_solution(self, invocation: Invocation):
        system_prompt = self.prompts.sage

        def select_for_final(i, invc: Invocation):
            step = invc.step
            return isinstance(step, (InitialStep, AskQuestionStep, UserReplyStep, FinalAnswerStep))

        prompts = self.show_conversation_thread(selector=select_for_final)
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
                    response = self.llm.ask(system_prompt, prompts_to_be_sent,
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
                    log_debug(f"===> received dead-end check reply {i}: {result} ({n_true}/{n_success})")
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

    def ask_user(self, questions: str) -> str:
        # for now just use the console input
        print("Tao, the problem tackler, asks you a few questions for clarification. Please reply all questions.")
        print(questions)
        reply = input(f"{questions}\nPlease reply to Tao:")
        if reply.lower().strip() == 'cancel!':
            raise KeyboardInterrupt(reply)
        return reply

    def find_last_criticisms(self, invocation: Invocation) -> {set}:
        criticism: {str} = set()
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
        prompt_db: PromptSet = self.prompts
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
                                             prompt_db.orchestrator_next_step_parse_error)
        choices = sorted([item for item in rankings.items() if item[1][0] >= min_threshold],
                         key=lambda item: item[1][0], reverse=True)
        if len(choices) == 0:
            raise Backtrack('No candidate passes min. threshold.', blame=self._chain[-1])
        result = choices[0]
        return result[0], result[1][1]

    def _handle_parse_error(self, e: Exception, n_retries, prompts, prompts_to_be_sent, response: str, retry_req: str):
        if isinstance(e, ParseError) and len(prompts_to_be_sent) <= len(prompts):
            prompts_to_be_sent.append((ROLE_SOLVER, response))
            message = retry_req.format(error=str(e))
            prompts_to_be_sent.append((ROLE_ORCHESTRATOR, message))
            self.logger.log(f"\n***RETRY***\n{message}")
        if n_retries >= MAX_RETRIES:
            print(f"failed after {n_retries}")
            raise e
