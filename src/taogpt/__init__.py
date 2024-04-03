from __future__ import annotations

import abc as _abc
import dataclasses as _dc
import typing as _t
import re as _re
from threading import local

from taogpt.prompts import PromptDb
from taogpt.md_logging import MarkdownLogger
from taogpt import utils as _utils


class LLM:
    collapsed_contents: dict[str, str] = dict()

    @property
    @_abc.abstractmethod
    def model_id(self) -> str:
        pass

    @property
    def total_tokens(self):
        return 0

    def ask(self, system_prompt: str|None, conversation: list[_t.Tuple[str, str]], reason=None,
            temperature: float=None, log_request=True, **_) -> str:
        pass

    def reset(self):
        self.collapsed_contents.clear()

    @_abc.abstractmethod
    def count_tokens(self, text: str) -> int:
        pass

    @staticmethod
    def deduplicate_for_logging(message, role: str):
        content = _utils.str_or_blank(message)
        return LLM.collapsed_contents.get(content.lower(), content)

    def merge_collapsed_contents(self, collapse_contents: _t.Dict[str, str]):
        for key, content in collapse_contents.items():
            content = _utils.str_or_blank(content).lower()
            tokens = self.count_tokens(content)
            if len(content) > 0 and tokens > 32:
                LLM.collapsed_contents[content] = f"[..{key}:{tokens}..]"

    def __repr__(self) -> str:
        return self.model_id


@_dc.dataclass
class Config:
    # hyperparameters
    initial_expansion: int = 3
    first_expansion: int = 1
    first_try_temperature: float = 0.0
    alternative_temperature: float = 0.7
    max_search_expansion: int = 4
    try_intuition: bool = True
    try_intuition_first_expansion: bool = True
    votes: int = 1

    # behavioral
    analyze_first: bool = True
    check_final: bool = True

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
    file_generation_support: bool = False
    # logging
    collapse_long_prompts: bool = True


class Executor(_abc.ABC):

    def __init__(self, input_fn: _t.Callable[[str], str]=None, **kwargs):
        self._pending_pause: str|None = None
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
    def show_conversation_thread(self, with_header=True, with_extras=False,
                                 selector: _t.Callable[[int, StepABC], bool] | None=None, except_step:StepABC=None) \
            -> list[tuple[str, str]]:
        pass

    @_abc.abstractmethod
    def is_first_solving_expansion(self) -> bool:
        pass

    def ask_questions(self, questions: list[str]) -> dict[str, str]:
        raise NotImplementedError('No user agent feature in the base')

    def ask_genie(self, codes: list[str], step: StepABC) -> list[str]:
        raise NotImplementedError('No ask genie agent feature in the base')

    @property
    @_abc.abstractmethod
    def current_step_name(self) -> str:
        pass

    def handle_parse_error(self,
                           e: Exception,
                           n_retries: int,
                           prompts: list[tuple[str, str]],
                           prompts_to_be_sent: list[tuple[str, str]],
                           response: str,
                           retry_prompt: str):
        raise e # base just re-throw without retry

    @property
    def pending_pause(self) -> str|None:
        return self._pending_pause

    def request_pause(self, reason: str|None):
        self._pending_pause = reason

class StepABC(_abc.ABC):

    def __init__(self, *, previous: StepABC|None, description: str, role: str):
        self.previous = previous
        self.description = description
        self.role = role
        self._step_name = None
        self._visible = True

    @property
    @_abc.abstractmethod
    def step_id(self) -> int:
        pass

    @property
    def step_name(self) -> str|None:
        return self._step_name

    def set_step_name(self, name: str|None, forced=False):
        name = _utils.str_or_blank(name)
        if name == '' or self._step_name == name:
            return
        if self._step_name is None or forced:
            self._step_name = name
            self._prepend_step_name_header(name)
        else:
            raise RuntimeError(f"step name has already been set to {self._step_name}")

    def _prepend_step_name_header(self, name):
        self.description = _re.sub(r"\[at step:[^]]+]\s*", "", self.description)
        self.description = f"[at step: {name}]\n\n{self.description}"

    @property
    def visible_in_chain(self) -> bool:
        return self._visible

    def set_visible_in_chain(self, visible: bool):
        self._visible = visible

    @property
    def collected_files(self) -> dict[str, GeneratedFile]:
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
    def collect_files(chain: list[StepABC]) -> dict[str, GeneratedFile]:
        files = dict()
        for step in chain:
            for path, file in step.collected_files.items():
                files[path] = file # override previous ones
        return files
