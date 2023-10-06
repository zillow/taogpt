from __future__ import annotations

import random as _random
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
        original = message
        try:
            fenced_blocks, message = extract_fenced_blocks(message)
        except SyntaxError:
            return original
        lines = message.split(('\n'))
        for i in range(len(lines)):
            line = lines[i]
            matches: re.Match = MarkdownLogger.H1_RE.match(line)
            lines[i] = f"***{matches.group(1)}***\n\n" if matches is not None else line
        result = '\n'.join(lines)
        return restore_fenced_block(result, fenced_blocks)

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
        self.log(f'<div style="background-color:{color}; padding: 5px; border-bottom: 1px dotted grey">\n'
                 f'<div>[{step_index}] <b>{role}</b>:</div>\n')

    def close_message_section(self):
        self.log('\n</div>')


# credit: https://stackoverflow.com/questions/39379331/python-exec-a-code-block-and-eval-the-last-line
def exec_then_eval(code, global_scope: _t.Dict[str, _t.Any]):
    block = _ast.parse(code, mode='exec')
    # assumes last node is an expression
    last = _ast.Expression(block.body.pop().value)
    exec(compile(block, '<string>', mode='exec'), global_scope, global_scope)
    return eval(compile(last, '<string>', mode='eval'), global_scope, global_scope)


# credit: https://stackoverflow.com/questions/64209815/python-how-can-i-save-the-output-of-eval-in-a-variable
def eval_and_collect(codes: str, global_scope: _t.Dict[str, _t.Any],
                     return_value_indicator='=> ',
                     raise_on_error=True) -> str:
    old_stdout = _sys.stdout
    try:
        _sys.stdout = mystdout = _StringIO()
        try:
            ret = exec_then_eval(codes, global_scope)
            output = mystdout.getvalue()
        except Exception as e:
            if raise_on_error:
                raise e
            output = str(e)
            ret = None
        finally:
            _sys.stdout = old_stdout
        if len(output) > 0 and not output.endswith('\n'):
            output += '\n'
        if ret is not None:
            output += return_value_indicator + str(ret)
        return output
    finally:
        _sys.stdout = old_stdout


def exec_code_and_collect_outputs(prompt: str, codes: str, global_scope: _t.Dict[str, _t.Any]|None=None) -> str:
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
    return eval_and_collect(codes, global_scope or dict())


_markdown_fenced_block_re = re.compile(r"```+", flags=re.DOTALL | re.IGNORECASE)


def extract_fenced_blocks(text):
    fenced_blocks = dict()
    key_prefix = f"fenced_{_random.randint(1000, 10000000)}_"
    while True:
        match = _markdown_fenced_block_re.search(text, 0)
        if match is not None:
            open_pos = match.span()[0]
            n_backquotes = len(match.group(0))
            pattern = re.compile('`' * n_backquotes)
            match = pattern.search(text, open_pos + n_backquotes)
            if match is not None:
                end_pos = match.span()[1]
                key = f"{key_prefix}{len(fenced_blocks)}"
                original = text[open_pos:end_pos]
                fenced_blocks[key] = original
                text = text.replace(original, key) # ok to replace all
            else:
                raise SyntaxError("Missing closing fenced block backquote marks.")
        else:
            break
    return fenced_blocks, text


def restore_fenced_block(text: str, fenced_blocks: _t.Dict[str, str]):
    for key, original in fenced_blocks.items():
        text = text.replace(key, original)
    return text
