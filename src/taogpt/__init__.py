from __future__ import annotations

import abc as _abc
import dataclasses as _dc
import typing as _t
from threading import local

from taogpt.prompts import PromptDb
from taogpt.logging import MarkdownLogger


class LLM:

    def __init__(self):
        self.collapsed_contents: {str: str} = dict()

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
        self.collapsed_contents.clear()

    def deduplicate_for_logging(self, message, role: str):
        for key, collapsible in self.collapsed_contents.items():
            if collapsible == message:
                return f"[..{key}:{len(message)}..]"
        for i in range(1, 1000):
            key = f"{role}/{i}"
            if key not in self.collapsed_contents:
                self.collapsed_contents[key] = message
                break
        return message

    def merge_collapsed_contents(self, collapse_contents: _t.Dict[str, str]):
        # preferring supplied content name over generated content name
        supplied = {content: key for key, content in collapse_contents.items()}
        evict_keys = set()
        for existing_key, content in self.collapsed_contents.items():
            if content in supplied and existing_key != supplied[content]:
                evict_keys.add(existing_key)
        for key in evict_keys:
            self.collapsed_contents.pop(key)
        self.collapsed_contents.update(collapse_contents)

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
    use_sage_llm_for_initial_expansion: bool = True

    # user interactions
    ask_user_questions_in_one_prompt: bool = False
    ask_user_before_execute_codes: bool = True
    pause_after_initial_solving_expansion: bool = True
    pause_after_final_answer_rejected: bool = False


class Executor(_abc.ABC):

    def __init__(self, input_fn: _t.Callable[[str], str]=None, **kwargs):
        self._pending_pause: _t.Optional[str] = None
        self._input_fn = local()
        if input_fn is not None:
            self._input_fn.callback = input_fn

    def reset(self):
        self._pending_pause = None

    def set_input_fn(self, input_fn: _t.Callable[[str], str]):
        self._input_fn.callback = input_fn

    @property
    def input_fn(self) -> _t.Callable[[str], str]:
        return self._input_fn.callback

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
    def chain(self) -> [StepABC]:
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

    def ask_questions(self, questions: [str]) -> {str: str}:
        raise NotImplementedError('No user agent feature in the base')

    def ask_genie(self, codes: [str], step: StepABC) -> [str]:
        raise NotImplementedError('No ask genie agent feature in the base')

    @property
    @_abc.abstractmethod
    def current_step_name(self) -> str:
        pass

    def handle_parse_error(self,
                           e: Exception,
                           n_retries: int,
                           prompts: [(str, str)],
                           prompts_to_be_sent: [(str, str)],
                           response: str,
                           retry_prompt: str):
        raise e # base just re-throw without retry

    @property
    def pending_pause(self) -> _t.Optional[str]:
        return self._pending_pause

    def request_pause(self, reason: str):
        self._pending_pause = reason

@_dc.dataclass(repr=False)
class StepABC(_abc.ABC):
    previous: _t.Optional[StepABC]
    description: str
    role: str

    @property
    @_abc.abstractmethod
    def step_id(self) -> int:
        pass

    @property
    def collected_files(self) -> _t.Dict[str, GeneratedFile]:
        return dict()

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

@_dc.dataclass
class GeneratedFile:
    content_type: str
    content: str
    markdown_snippet: str
    description: str

    @staticmethod
    def collect_files(chain: _t.List[StepABC]) -> _t.Dict[str, GeneratedFile]:
        files = dict()
        for step in chain:
            for path, file in step.collected_files.items():
                files[path] = file # override previous ones
        return files
