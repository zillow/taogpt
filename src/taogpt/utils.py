from __future__ import annotations

import re
import typing as _t
import re as _re
from io import StringIO as _StringIO
import sys as _sys
import ast as _ast

from pathlib import Path as _Path
from dataclasses import  MISSING as _MISSING
from typing import Generic, TypeVar
from taogpt.constants import (
    ROLE_GENIE,
    ROLE_ORCHESTRATOR,
    ROLE_SAGE,
    ROLE_TAO,
    ROLE_SYSTEM,
    ROLE_USER
)

_T = TypeVar('_T')


# credit: https://stackoverflow.com/questions/61237131/how-to-make-attribute-in-dataclass-read-only
class Frozen(Generic[_T]):
    __slots__ = (
        '_default',
        '_private_name',
    )

    def __init__(self, default: _T = _MISSING):
        self._default = default

    def __set_name__(self, owner, name):
        self._private_name = '_' + name

    def __get__(self, obj, objtype=None) -> _T:
        value = getattr(obj, self._private_name, self._default)
        return value

    def __set__(self, obj, value):
        if hasattr(obj, self._private_name):
            msg = f'Attribute `{self._private_name[1:]}` is immutable!'
            raise TypeError(msg) from None

        setattr(obj, self._private_name, value)


def str_or_blank(s: str) -> str:
    return s.strip() if s is not None else ''


def remove_brackets(s: str) -> str:
    s = s.strip() if s is not None else ''
    if s.startswith('['):
        s = s[1:]
    if s.endswith(']'):
        s =s [:-1]
    return s


def is_blank(text: str) -> bool:
    return text is None or str_or_blank(text) == ''


_debugged: int = 0


def enable_debugging(level=1):
    global _debugged
    _debugged = level


def log_debug(obj: _t.Any, level: int=1):
    global _debugged
    if level > _debugged:
        return
    print(obj)


def safe_subn(text: str | None, n=20, default='') -> str:
    return text[:n].strip() if text is not None else default


class MarkdownLogger:
    # H1_RE = _re.compile(r"^# +([^\n]+)", flags=_re.MULTILINE|_re.DOTALL)
    H1_RE = _re.compile(r"^# +(.+)")
    role_color_map = {
        'system': 'lightgrey',
        ROLE_USER: 'lightgreen',
        ROLE_TAO: 'lightyellow',
        'assistant': 'lightyellow',
        ROLE_ORCHESTRATOR: 'lightcyan',
        ROLE_SAGE: 'lightcyan',
        ROLE_GENIE: 'lightsteelblue'
    }

    def __init__(self, log_path: str|_Path):
        self._log_path = _Path(log_path)
        self._log = open(self._log_path, 'w')

    def close(self):
        if self._log is not None:
            self._log.close()
            self._log = None

    def __delete__(self, instance):
        if instance._log is not None:
            instance._log.close()

    def log(self, *msgs, demote_h1=False):
        try:
            msg = ''
            for msg in msgs:
                if demote_h1:
                    msg = MarkdownLogger.demote_h1(msg)
                self._log.write(msg)
            if len(msg) > 0 and msg[-1] != '\n':
                self._log.write('\n') # assume markdown file paragraph
            self._log.write('\n')
        finally:
            self._log.flush()

    @staticmethod
    def demote_h1(message: str):
        lines = message.split(('\n'))
        for i in range(len(lines)):
            line = lines[i].strip()
            matches: re.Match = MarkdownLogger.H1_RE.match(line)
            lines[i] = f"***{matches.group(1)}***\n\n" if matches is not None else line
        return '\n'.join(lines)

    def log_conversation(self, conversation: [(str, str)], skip_system_message=1, title='Final path history'):
        if title:
            self.log('<div style="background-color: beige; text-align: center; padding: 5px">\n\n')
            self.log(f'# {title}')
            self.log('</div>')
        system_message_count = 0
        for i, (role, message) in enumerate(conversation):
            self.new_message_section(role, i)
            if role == 'system':
                system_message_count += 1
                if system_message_count <= skip_system_message:
                    continue
            self.log(message, demote_h1=True)
            self.close_message_section()

    def new_message_section(self, role, step_index):
        color = MarkdownLogger.role_color_map.get(role, 'white')
        self.log(f'<div style="background-color:{color}; display: flex; border-bottom: 1px dotted grey">\n\n'
                 f'<div style="flex: 130px">\n\n[{step_index}] **{role}**\n\n</div>\n'
                 f'<div style="flex: 100%; border-left: 1px dotted grey; padding-left: 5px">')

    def close_message_section(self):
        self.log('\n</div>\n</div>')


# credit: https://stackoverflow.com/questions/39379331/python-exec-a-code-block-and-eval-the-last-line
def exec_then_eval(code):
    block = _ast.parse(code, mode='exec')
    # assumes last node is an expression
    last = _ast.Expression(block.body.pop().value)
    _globals, _locals = {}, {}
    exec(compile(block, '<string>', mode='exec'), _globals, _locals)
    return eval(compile(last, '<string>', mode='eval'), _globals, _locals)


# credit: https://stackoverflow.com/questions/64209815/python-how-can-i-save-the-output-of-eval-in-a-variable
def eval_and_collect(codes: str, return_value_indicator='=> ') -> str:
    old_stdout = _sys.stdout
    try:
        _sys.stdout = mystdout = _StringIO()
        try:
            ret = exec_then_eval(codes)
            _sys.stdout = old_stdout
            output = mystdout.getvalue()
        except Exception as e:
            output = str(e)
            ret = None
        if len(output) > 0 and not output.endswith('\n'):
            output += '\n'
        if ret is not None:
            output += return_value_indicator + str(ret)
        return output
    finally:
        _sys.stdout = old_stdout


def exec_code_and_collect_outputs(prompt: str, codes: str) -> str:
    while prompt is not None:
        answer = input(f"""{prompt}
    
```python
{codes}
```
Reply "yes" to execute this code snippet, or "no" to cancel.
        """)
        if answer.strip().lower() == 'yes':
            break
        elif answer.strip().lower() == 'no':
            raise KeyboardInterrupt("User cancelled the request")
    return eval_and_collect(codes)
