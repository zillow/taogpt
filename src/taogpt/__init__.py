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

    def __repr__(self) -> str:
        return self.model_id


@_dc.dataclass
class Config:
    # hyperparameters
    initial_expansion: int = 1
    first_expansion: int = 1
    first_try_temperature: float = 0.0
    alternative_temperature: float = 0.7
    max_search_expansion: int = 4
    votes: int = 1

    # behavioral
    analyze_first: bool = True
    check_final: bool = True,

    # token usage controls
    max_tokens: int = 10000
    max_tokens_for_sage_llm: int | None = None
    max_retries: int = 3

    # user interactions
    ask_user_questions_in_one_prompt: bool = False
    ask_user_before_execute_codes: bool = True
    pause_after_initial_solving_expansion: bool = False


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
    def show_conversation_thread(self, with_header=True, selector: _t.Callable[[int, StepABC], bool] | None=None) \
            -> [(str, str)]:
        pass

    def record_criticisms(self, criticisms: [str]):
        pass

    def ask_user(self, questions: [str]) -> str:
        raise NotImplementedError('No user agent feature in the base')

    def ask_genie(self, codes: [str], step: StepABC) -> [str]:
        raise NotImplementedError('No ask genie agent feature in the base')

    def handle_parse_error(self,
                           e: Exception,
                           n_retries: int,
                           prompts: [(str, str)],
                           prompts_to_be_sent: [(str, str)],
                           response: str,
                           retry_prompt: str):
        raise e # base just re-throw without retry


@_dc.dataclass(repr=False)
class StepABC(_abc.ABC):
    previous: _t.Optional[StepABC]
    description: str
    role: str

    @property
    @_abc.abstractmethod
    def step_id(self) -> int:
        pass

    # @property
    # @_abc.abstractmethod
    # def description(self) -> str:
    #     pass
    #
    # @description.setter
    # @_abc.abstractmethod
    # def description(self, value: str) -> str:
    #     pass
    #
    @property
    @_abc.abstractmethod
    def description_with_header(self) -> str:
        pass

    @_abc.abstractmethod
    def eval(self, executor: Executor) -> StepABC | None:
        pass


class Backtrack(RuntimeError):
    def __init__(self, reason: str | None, blame: StepABC):
        super().__init__(reason)
        self.blame = blame


class Pause(RuntimeError):
    def __init__(self, reason: str | None, cause: StepABC):
        super().__init__(reason)
        self.cause = cause


class TokenUsageError(Pause):
    pass


class UnsolvableError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
