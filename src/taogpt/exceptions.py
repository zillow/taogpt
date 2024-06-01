from __future__ import annotations

import logging as _logging

_logger = _logging.getLogger(__file__)


class RedoFinalCheck(RuntimeError):
    """
    This error is used internally to signal the repair mechanism to discard all previous criticisms and perform the
    final check again.
    """

    def __init__(self, step_name: str):
        super().__init__(f"Step {step_name} requests redo the final check")


class ThisMaybeTooHardError(RuntimeError):
    pass


class ParseError(ValueError):
    def __init__(self, message: str, original:str=None, *args):
        super().__init__(message, *args)
        self._original = original
        # we want to inspect all of these
        log_text = f"\n{original}" if original is not None else ""
        _logger.warning(f"{self.__class__}: {message}{log_text}")

    @property
    def original_text(self) -> str|None:
        return self._original


class ReplyHeaderParseError(ParseError):
    pass


class UnbalancedBlockParseError(ParseError):
    pass


class UnsolvableError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
