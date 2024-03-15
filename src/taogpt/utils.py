from __future__ import annotations

import os.path
import re
import typing as _t
from io import StringIO as _StringIO
import os as _os
import sys as _sys
import ast as _ast
import json as _json
import configparser as _config
import Levenshtein as _leven

_T = _t.TypeVar('_T')


def safe_is_instance(obj, class_or_tuple: _t.Type|_t.Iterable[_t.Type]) -> bool:
    """
    When using autoreload (in Jupyter notebook), `isinstance` is not safe. This walk up the hierarchy
    and check using `__qualname__`.
    :param obj:
    :param class_or_tuple:
    :return:
    """
    if isinstance(obj, class_or_tuple): # try using the default one
        return True

    if not isinstance(class_or_tuple, (tuple, list, set)):
        class_or_tuple = (class_or_tuple, )

    check_classes = [cls.__qualname__ if isinstance(cls, type) else cls for cls in class_or_tuple]
    mro_classes = [cls.__qualname__ for cls in obj.__class__.mro()]
    return any(check_class in mro_classes for check_class in check_classes)


def cast(obj, to_class: _t.Type[_T]) -> _T:
    _ = to_class
    return obj


def single_space(s: str) -> str:
    return re.sub(r"\s{2,}", " ", str_or_blank(s))

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


def safe_subn(text: str | None, n=20, default='', escape_new_line=True, append='...') -> str:
    if text is None:
        return ''
    text = text.strip()
    if escape_new_line:
        text = text.replace("\n", r"\n").replace("\t", r" ")
    orig_len = len(text)
    text = text[:n].strip() if text is not None else default
    if orig_len > len(text):
        text += append
    return text


def normalized_levenstein_distance(s1: str|None, s2: str|None, normalized_to: int|str|None=None) -> float:
    s1 = s1 or ''
    s2 = s2 or ''
    if normalized_to is None:
        normalized_to = s1 if len(s1) > len(s2) else s2
    elif isinstance(normalized_to, int):
        assert normalized_to in (1, 2)
        normalized_to = s1 if normalized_to == 1 else s2
    dist = _leven.distance(s1, s2)
    n = len(normalized_to)
    if n == 0:
        return 0. if dist == 0 else 1.
    return float(dist) / n


# credit: https://stackoverflow.com/questions/39379331/python-exec-a-code-block-and-eval-the-last-line
def exec_then_eval(code, global_scope: _t.Dict[str, _t.Any]):
    block = _ast.parse(code, mode='exec')
    # assumes last node is an expression
    last_statement = None
    try:
        last_statement = block.body.pop()
        last = _ast.Expression(last_statement.value)
    except AttributeError as e:
        print(str(e))
        if "'If' object has no attribute 'value'" in str(e):
            raise SyntaxError("Trying to return value from the last `if` statement, "
                              "but `if` statement does not have return value.")
        if last_statement is not None: # still need to execute it
            block.body.append(last_statement)
        last = None
    exec(compile(block, '<string>', mode='exec'), global_scope, global_scope)
    return eval(compile(last, '<string>', mode='eval'), global_scope, global_scope) \
        if last is not None else 'Python Genie: no return value from last statement'


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
Reply "yes" to execute this code snippet, or "no" to cancel: """)
        if answer.strip().lower() == 'yes':
            break
        elif answer.strip().lower() == 'no':
            raise KeyboardInterrupt("User cancelled the request")
    return eval_and_collect(codes, global_scope or dict())


def set_openai_credentials(path: str):
    path = os.path.expanduser(path)
    with open(path, 'r') as f:
        if path.endswith('.json'):
            credentials = _json.load(f)
        else:
            config = _config.ConfigParser()
            config.read_file(f)
            credentials = config['DEFAULT']
    for k, v in credentials.items():
        _os.environ[k.upper()] = v
