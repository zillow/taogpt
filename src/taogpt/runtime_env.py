from __future__ import annotations
import abc as _abc
import dataclasses as _dc
import typing as _t
from .utils import MarkdownLogger


class Executor(_abc.ABC):

    @property
    @_abc.abstractmethod
    def logger(self) -> MarkdownLogger:
        pass

    @_abc.abstractmethod
    def show_conversation_thread(self) -> [(str, str)]:
        pass

    def ask_user(self, questions: [str]) -> str:
        raise NotImplementedError('No user agent feature in the base')

    @_abc.abstractmethod
    def find_last_criticisms(self, invocation: Invocation) -> [str]:
        pass

    @property
    def max_search_branching_factor(self) -> int:
        return 4

class StepABC(_abc.ABC):
    @property
    @_abc.abstractmethod
    def step_id(self) -> int:
        pass


@_dc.dataclass(repr=False)
class Invocation:
    step: StepABC
    current_choice: int = 0
    execution_count: int = 0
    _executor: Executor | None = None

    def __repr__(self) -> str:
        c = self.__class__.__name__
        step = self.step.step_id
        sc = self.step.__class__.__name__
        return f"{c}(step={sc}#{step},ptr={self.current_choice},exec={self.execution_count})"

    @property
    def executor(self):
        return self._executor


class Backtrack(RuntimeError):
    def __init__(self, reason: str | None, blame: Invocation):
        super().__init__(reason)
        self.blame = blame


class UnsolvableError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
