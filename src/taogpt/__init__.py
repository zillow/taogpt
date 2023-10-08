from __future__ import annotations

import abc as _abc
import dataclasses as _dc
import typing as _t

from taogpt.prompts import PromptDb
from taogpt.utils import MarkdownLogger


class LLM:

    def __init__(self):
        self.collapsed_contents: {str} = set()

    @property
    @_abc.abstractmethod
    def model_id(self) -> str:
        pass

    @property
    def total_tokens(self):
        return 0

    def ask(self, system_prompt: str, conversation: _t.List[_t.Tuple[str, str]], reason=None,
            temperature: float=None, log_request=True, collapse_contents: {str: str}=None,**_) -> str:
        pass

    def reset(self):
        pass

    def deduplicate_for_logging(self, message, collapse_contents):
        content_to_be_logged: str = message
        for key, collapsible in collapse_contents.items():
            if collapsible in content_to_be_logged:
                if collapsible in self.collapsed_contents:
                    content_to_be_logged = content_to_be_logged.replace(
                        collapsible, f"[..{key}:{len(collapsible)}..]")
                self.collapsed_contents.add(collapsible)
                break
        return content_to_be_logged


@_dc.dataclass
class Config:
    initial_expansion: int = 1
    first_expansion: int = 1
    first_try_temperature: float = 0.0
    alternative_temperature: float = 0.7
    max_search_expansion: int = 4
    ask_user_before_execute_codes: bool = True
    max_tokens: int = 10000
    max_tree_branches: int = 4
    check_final: bool = False,
    max_tokens_for_sage_llm: int | None = None
    ask_user_questions_in_one_prompt: bool = False
    pause_after_initial_solving_expansion: bool = False
    max_retries: int = 3
    votes: int = 1


class Executor(_abc.ABC):

    @property
    @_abc.abstractmethod
    def config(self) -> Config:
        pass

    @property
    @_abc.abstractmethod
    def llm(self) -> LLM:
        pass

    @property
    def sage_llm(self) -> LLM:
        """
        Sage LLM is used for ranking and final answer checking. It can be a smarter (and more expensive) LLM. By
        default, it just returns the regular LLM.
        :return: the sage LLM
        """
        return self.llm

    @property
    @_abc.abstractmethod
    def prompts(self) -> PromptDb:
        pass

    @property
    @_abc.abstractmethod
    def logger(self) -> MarkdownLogger:
        pass

    @_abc.abstractmethod
    def show_conversation_thread(self) -> [(str, str)]:
        pass

    def record_criticisms(self, criticisms: [str]):
        pass

    def ask_user(self, questions: [str]) -> str:
        raise NotImplementedError('No user agent feature in the base')

    def ask_genie(self, codes: [str], invocation: Invocation) -> [str]:
        raise NotImplementedError('No ask genie agent feature in the base')

    @_abc.abstractmethod
    def find_last_criticisms(self, invocation: Invocation) -> [str]:
        pass


class StepABC(_abc.ABC):
    @property
    @_abc.abstractmethod
    def step_id(self) -> int:
        pass


@_dc.dataclass(repr=False)
class Invocation:
    step: StepABC
    _executor: Executor | None = None

    def __repr__(self) -> str:
        c = self.__class__.__name__
        step = self.step.step_id
        sc = self.step.__class__.__name__
        return f"{c}(step={sc}#{step})"

    @property
    def executor(self) -> Executor:
        return self._executor


class Backtrack(RuntimeError):
    def __init__(self, reason: str | None, blame: Invocation):
        super().__init__(reason)
        self.blame = blame


class Pause(RuntimeError):
    def __init__(self, reason: str | None, cause: StepABC):
        super().__init__(reason)
        self.cause = cause


class UnsolvableError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
