from __future__ import annotations

import abc as _abc
import dataclasses as _dc
import typing as _t
from threading import local

from taogpt.prompts import PromptDb
from taogpt.md_logging import MarkdownLogger
from taogpt import parsing as _parsing
from taogpt import utils as _utils


class LLM:
    collapsed_contents: dict[str, str] = dict()
    _encountered_collapsed_contents: dict[str, str] = dict()

    def __init__(self, max_token_usage: int):
        self._max_token_usage = max_token_usage

    @property
    def max_token_usage(self) -> int:
        return self._max_token_usage

    @max_token_usage.setter
    def max_token_usage(self, new_limit: int):
        self._max_token_usage = new_limit

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
        pass

    @_abc.abstractmethod
    def count_tokens(self, text: str) -> int:
        pass

    def deduplicate_for_logging(self, message, role: str, always_log_first=False):
        content = _utils.str_or_blank(message)
        normalized = content.lower()
        deduped = LLM.collapsed_contents.get(normalized, None)
        if deduped is not None:
            if always_log_first and normalized not in LLM._encountered_collapsed_contents:
                LLM._encountered_collapsed_contents[normalized] = deduped
                return content
            return deduped
        return content

    def merge_collapsed_contents(self, collapse_contents: _t.Dict[str, str], immediate=False):
        for key, content in collapse_contents.items():
            content = _utils.str_or_blank(content).lower()
            tokens = self.count_tokens(content)
            if tokens > 32:
                key = f"[..{key}..]"
                LLM.collapsed_contents[content] = key
                if immediate:
                    LLM._encountered_collapsed_contents[content] = key

    def __repr__(self) -> str:
        return self.model_id


@_dc.dataclass
class Config:
    # hyperparameters
    initial_expansion: int = 2
    first_expansion: int = 1
    first_try_temperature: float = 0.0
    alternative_temperature: float = 0.7
    max_search_expansion: int = 4
    votes: int = 1
    n_final_checks: int = 3

    # behavioral
    ask_questions: bool=True
    ask_genie: bool=True
    file_support: bool=True
    optimized_sequential_next_step: bool = True
    summarize: bool = True

    # token usage controls
    max_tokens: int = 10000
    max_tokens_for_sage_llm: int | None = None
    max_retries: int = 3
    use_sage_llm_for_initial_expansion: bool = True

    # user interactions
    ask_user_questions_in_one_prompt: bool = False
    ask_user_before_execute_codes: bool = True
    pause_after_initial_solving_expansion: bool = True
    pause_on_backtrack: bool = True
    review_file_merges: bool = False
    # logging
    collapse_long_prompts: bool = True

    def get_temperature(self, nth_try: int):
        return self.first_try_temperature if nth_try == 0 else self.alternative_temperature


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
    def file_merging_llm(self) -> LLM:
        """
        The LLM is used for consolidating file revisions. By default, it just returns the regular LLM.
        :return: an LLM
        """
        return self.llm

    @property
    def total_tokens(self) -> int:
        tokens = self.llm.total_tokens
        if self.sage_llm is not None and self.sage_llm is not self.llm:
            tokens += self.sage_llm.total_tokens
        return tokens

    @property
    @_abc.abstractmethod
    def prompts(self) -> PromptDb:
        pass

    @property
    @_abc.abstractmethod
    def chain(self) -> list[StepABC]:
        pass

    @_abc.abstractmethod
    def enqueue(self, step: StepABC):
        pass

    @_abc.abstractmethod
    def remove_steps(self, *, from_step: StepABC=None, to_step: StepABC=None, steps: list[StepABC]=None):
        pass

    def previous_step(self, step: StepABC) -> StepABC|None:
        i = self.chain.index(step)
        return self.chain[i-1] if i > 0 and i < len(self.chain) else None

    @property
    @_abc.abstractmethod
    def logger(self) -> MarkdownLogger:
        pass

    @_abc.abstractmethod
    def check_token_usages(self):
        pass

    @_abc.abstractmethod
    def step_id(self, step):
        pass

    @_abc.abstractmethod
    def select_steps(self, selector: _t.Callable[[int, StepABC], bool]|_t.Type,
                     except_step: StepABC=None, stop_at: StepABC=None) \
            -> list[StepABC]:
        pass

    @_abc.abstractmethod
    def show_conversation_thread(self, with_header=True, with_extras=False,
                                 selector: _t.Callable[[int, StepABC], bool] | None=None,
                                 except_step: StepABC=None,
                                 stop_at: StepABC=None) \
            -> list[tuple[str, str]]:
        pass

    @_abc.abstractmethod
    def is_init_solving_expansion(self) -> bool:
        pass

    def ask_questions(self, questions: list[str]) -> dict[str, str]:
        raise NotImplementedError('No user agent feature in the base')

    def ask_genie(self, codes: list[str], step: StepABC) -> list[str]:
        raise NotImplementedError('No ask genie agent feature in the base')

    @property
    @_abc.abstractmethod
    def current_step_name(self) -> str:
        pass

    @_abc.abstractmethod
    def summarize_final_answer(self) -> StepABC|None:
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

    def __init__(self, *, description: str, role: str, step_name: str|None):
        self.description = _parsing.at_step_re.sub('', description, 1).strip()
        self.role = role
        self._step_name = _parsing.sanitize_step_name(_utils.str_or_blank(step_name))
        self._visible = True

    @property
    def step_name(self) -> str|None:
        return self._step_name

    @property
    def visible_in_chain(self) -> bool:
        return self._visible

    @property
    def visible_in_summarization(self) -> bool:
        return self.visible_in_chain

    def set_visible_in_chain(self, visible: bool):
        self._visible = visible

    @property
    def collected_files(self) -> dict[str, GeneratedFile]:
        return dict()

    @_abc.abstractmethod
    def eval(self, executor: Executor) -> StepABC | None:
        pass


class Backtrack(RuntimeError):
    def __init__(self, reason: str | None, blame: StepABC):
        super().__init__(reason)
        self.blame = blame


class Pause(RuntimeError):
    def __init__(self, reason: str | None, cause: StepABC|None):
        super().__init__(reason)
        self.cause = cause


class TokenUsageError(Pause):
    pass


class UnsolvableError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)

@_dc.dataclass(eq=False)
class GeneratedFile:
    content_type: str
    content: str
    description: str

    @staticmethod
    def collect_files(chain: list[StepABC], stop_at_step: StepABC=None) -> dict[str, GeneratedFile]:
        files = dict()
        for step in chain:
            if stop_at_step is step:
                break
            for path, file in step.collected_files.items():
                files[path] = file # override previous ones
        return files

    def __post_init__(self):
        if self.content is None:
            raise ValueError("Markdown content is None")
        if self.content_type is None:
            self.content_type = ''

    def __eq__(self, other):
        if other is None:
            return False
        if self is other:
            return True
        if not isinstance(other, self.__class__):
            return NotImplemented
        other: GeneratedFile
        return self.content_type == other.content_type and self.content == other.content

    @property
    def markdown_snippet(self) -> str:
        backticks = "`" * max(3, _parsing.get_longest_backticks(self.content) + 1)
        return f"{backticks}{self.content_type}\n{self.content}\n{backticks}"
