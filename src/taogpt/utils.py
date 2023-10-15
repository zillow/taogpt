from __future__ import annotations

import typing as _t
from io import StringIO as _StringIO
import sys as _sys
import ast as _ast
import json as _json


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


def cast(obj, to_class: _t.Type[_T], raise_cast_error=True) -> _t.Optional[_T]:
    if obj is not None and safe_is_instance(obj, to_class):
        if raise_cast_error:
            raise TypeError(f"Instance of {type(obj)} cannot be casted to {to_class}")
        return None
    return obj


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


def set_openai_credentials_from_json(path):
    import os
    with open(path, 'r') as f:
        credentials = _json.load(f)
    os.environ["OPENAI_API_KEY"] = credentials['key']
    os.environ["OPENAI_API_BASE"] = credentials['url']
