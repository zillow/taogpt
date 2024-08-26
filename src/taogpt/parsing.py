from __future__ import annotations

import logging as _logging
import dataclasses
import random as _random
import hashlib as _hashlib
import json
import re as _re
import typing as _t
import dataclasses as _dc
import taogpt.utils as _utils
from taogpt.constants import *
from taogpt.exceptions import ParseError, UnbalancedBlockParseError

FREE_TEXT = '_FREE_TEXT'

_logger = _logging.getLogger(__file__)

_dash_or_slash = r'[_ \-]'

_action_re = (rf"{MY_THOUGHT.replace('_', _dash_or_slash)}"
    rf"|{WILL_ASK_GENIE.replace('_', _dash_or_slash)}"
    rf"|{WRITE_FILE.replace('_', _dash_or_slash)}"
    rf"|{REPORT_ERROR.replace('_', _dash_or_slash)}"
    rf"|{WILL_ASK_QUESTIONS.replace('_', _dash_or_slash)}"
    rf"|{HERE_IS_MY_STEP_BY_STEP_PLAN.replace('_', _dash_or_slash)}")

step_type_re = _re.compile(r"(^)\s*(" + _action_re + r"):\s*((.|\n)+)")
action_type_re = _re.compile(r"\s*(" + _action_re + r"):")

_true_false_answer_re = _re.compile(r"^\s*(.+)?\s*(true|false|yes|no)$",
                                   flags=_re.MULTILINE|_re.DOTALL|_re.IGNORECASE)
_whitespace_re = _re.compile(r"\s+", flags=_re.DOTALL)
_ordered_list_re = _re.compile(r'\n\s*(\d+)\.\s+(.*?)(?=\n\s*(\d+)|\n\n|\Z)', flags=_re.DOTALL)
_fix_fenced_block_backticks_re = _re.compile(r"^(\s*)(```+)(\d*)")

strip_quotes_re = _re.compile(r"^\s+|[\s\"\'.,]+$|[\"\']", flags=_re.DOTALL)
step_name_re = _re.compile(r"^\s*(((\d|\.)+)\s+)?(.+)")


def sanitize_step_name(step_name: str) -> str:
    return _re.sub(r"\s+", " ", _re.sub(r"[\"'`\n\[\]]", " ", step_name)).strip()


def get_longest_backticks(content: str) -> int:
    if content is None:
        return 0
    backticks = [len(b) for b in _re.findall(r"`+", content)]
    return max(backticks) if len(backticks) > 0 else 0


def fix_fenced_block_backticks(original: str|None) -> str|None:
    """
    Deprecated
    """
    if original is None:
        return None
    return '\n'.join([_fix_fenced_block_backticks_re.sub(r"\2", line) for line in original.split('\n')])


def parse_step_name(text: str|None) -> tuple[str|None, str|None]:
    if _utils.is_blank(text):
        return None, None
    match = step_name_re.search(text)
    return (match.group(2), match.group(4)) if match is not None else (None, None)


def parse_step_type_spec(text: str, working_on:str=None) -> tuple[str|None, str|None]|None:
    text = _utils.str_or_blank(text)
    if text == '':
        return None, None
    actions = action_type_re.findall(text)
    if len(actions) > 1:
        actions_str = ', '.join(actions)
        msg = f"""Expecting 1 action heading but found {len(actions)}: {actions_str}. 
Don't work on more than one step. Take only one action when working at one step. Like:

```markdown
<ACTION_HEADING>:

... response content for this action ...
```
"""
        if _utils.str_or_blank(working_on) != '':
            msg += f" Please respond with one action for the step '{working_on}' only."
        raise ParseError(msg)
    match: _re.Match = step_type_re.search(text)
    if match is None:
        return None, None
    step_type: str
    step_type, definition = match.group(2), _utils.str_or_blank(match.group(3))
    if definition == '':
        return None, None
    step_type = _re.sub(r'[\- ]', '_', step_type)
    return step_type, definition


def parse_sections(text: str, section_level: str='##') -> dict[str, str|None]:
    try:
        fenced_blocks, text = extract_fenced_blocks(text)
    except SyntaxError as e:
        raise ParseError(str(e))
    matched_sections = {FREE_TEXT: ''}
    section = FREE_TEXT
    for line in text.split('\n'):
        match: _re.Match = _re.match(rf"^{section_level}+\s+([^\n]+)", line)
        if match is not None:
            section = match.group(1).strip()
            while section != 'FILE:' and section.endswith(':'):
                section = section[:-1]
            matched_sections[section] = ''
        else:
            matched_sections[section] += line + '\n'

    return {k: (restore_fenced_block(text, fenced_blocks).strip() if text is not None else None)
            for k, text in matched_sections.items()}


def parse_ordered_list(markdown_text, at_least_one_list=True) -> list[str]:
    """
    Parse a simplified markdown list without consideration to multi-line indentation.
    :param markdown_text: markdown text
    :return: a list of string
    """
    markdown_text = '\n' + _utils.str_or_blank(markdown_text)
    expected_number = 1
    matches = []
    for m in _ordered_list_re.finditer(markdown_text):
        bullet = m.group(1)
        if int(bullet) != expected_number:
            raise ParseError("Unexpected bullet number or multiple lists presented.")
        expected_number += 1
        matches.append(_whitespace_re.sub(' ', m.group(2)).strip())
    if at_least_one_list and len(matches) == 0:
        raise ParseError("No list presented.")
    return matches


_json_response_re = _re.compile(r"^.*(```(json)?\n+)(.+)(```).*$|^\s*(\{.+})\s*$", flags=_re.DOTALL | _re.IGNORECASE)
_final_solution_check_re = _re.compile(r"^\s*(yes|no)[.,]?\s+(.+)$", flags=_re.DOTALL|_re.IGNORECASE)

at_step_re = _re.compile(r"\s*\[ *at +step(.*?)]", flags=_re.IGNORECASE)
_step_re = _re.compile(r"^( *\[? *(at )?(step#)?(\d+): *)?(.*?)[\s\]]*$", flags=_re.IGNORECASE)
_next_step_re = _re.compile(r"^( *\[? *(at )?step#?\d*:? *)?(response to +)?(.*?)[\s\]]*$", flags=_re.IGNORECASE)

def parse_step_id_and_name(text: str, key='') -> tuple[int|None, str]:
    if key != '':
        key = f"{key}: "
    text = _utils.str_or_blank(text)
    match = _step_re.match(text)
    if match is None:
        raise ParseError(f"{key}Step ID and description must be in the format of "
                         f"'step#<ID>: <string description>'.")
    try:
        step_num = int(match.group(4))
        return (step_num, match.group(5))
    except TypeError:
        raise ParseError(f"{key}Step ID and description must be in the format of "
                         f"'step#<ID>: <string description>'.")


@dataclasses.dataclass
class NextStepDesc:
    target_plan_id: int | None
    target_plan_tag: str | None
    target_plan_done: bool
    next_step_desc: str|None
    difficulty: int=6

    @property
    def is_final_step(self):
        next_step = _utils.str_or_blank(self.next_step_desc).lower()
        completed_plan_tag = _utils.str_or_blank(self.target_plan_tag).lower()
        return ('all done' in next_step
                or _utils.normalized_levenstein_distance(completed_plan_tag, "top-level plan/answer") <= 0.05)

    def to_json_string(self, as_markdown=False):
        next_step_dict = self.to_dict()
        next_step_json = json.dumps(next_step_dict) if len(next_step_dict) > 0 else None
        if next_step_json is not None and as_markdown:
            next_step_json = f"```json\n{next_step_json}\n```"
        return next_step_json

    def to_dict(self):
        next_step_dict: dict[str, str|bool] = dict()
        if self.target_plan_tag is not None:
            next_step_dict[f'done with [{self.target_plan_tag}]'] = self.target_plan_done
        if self.next_step_desc is not None:
            next_step_dict['next_step'] = self.next_step_desc
        return next_step_dict


def parse_next_step_spec(text: str, required=False) -> tuple[NextStepDesc|None, str]:
    text, fenced_blocks = check_and_fix_fenced_blocks(text, collapse_blocks=True)
    next_step_response: dict[str, _t.Any]|None = None
    for block_key, (fenced_block, content_type, backticks, block_content) in fenced_blocks.items():
        try:
            payload = json.loads(block_content)
            if isinstance(payload, dict) and 'next_to_work_at' in payload:
                next_step_response = payload['next_to_work_at']
                text = text.replace(block_key, '')
                continue
        except json.JSONDecodeError:
            pass
        text = text.replace(block_key, fenced_block)
    if next_step_response is None:
        if required:
            raise ParseError("Expecting a fenced block of JSON type with key `next_to_work_at`, but not found")
        return None, text

    difficulty = next_step_response.get('difficulty', 5)
    target_plan_id: int|None = None
    target_plan_tag: str|None = None
    target_done: bool|None = None

    for key, value in next_step_response.items():
        matched = _re.match(r"^\s*done\s+with\s+\[*([^]]+)", key)
        if matched:
            target_plan_id, target_plan_desc = parse_step_id_and_name(matched.group(1), key=key)
            target_plan_tag = f"step#{target_plan_id}: {target_plan_desc}"
            target_done = value
            break

    plan_of_next_step: str|None = next_step_response.get('plan_of_next_step', None)
    if target_done:
        if plan_of_next_step is not None:
            try:
                next_plan_id, next_plan_desc = parse_step_id_and_name(plan_of_next_step)
            except ParseError:
                next_plan_id = None
            if target_plan_id == next_plan_id:
                raise ParseError(f"You claim step#{target_plan_id} is done "
                                 f"while declare it as the plan of next step. This is contradictory.")

    next_step: str|None = next_step_response.get('step', next_step_response.get('next_step', None))
    if target_done:
        return NextStepDesc(target_plan_id, target_plan_tag, target_done, next_step, difficulty=difficulty), text

    if next_step is None or next_step == '':
        raise ParseError(f'No next step specified. Set next step description to the `next_step` key.')
    elif next_step in ('all done', 'done'):
        return NextStepDesc(None, None, True, "all done"), text

    return NextStepDesc(target_plan_id, target_plan_tag, target_done, next_step, difficulty=difficulty), text


def parse_verification_response(text: str) -> tuple[dict[str, tuple[str, list[tuple[int, str]]|None]], dict]:
    judgements: dict[str, dict[str, _t.Union[bool, str]]] = parse_json_hash(text, nested_hashes=True)
    if (not _utils.safe_is_instance(judgements, dict)
            or not all([_utils.safe_is_instance(x, dict) for x in judgements.values()])):
        raise ParseError("The response must be a JSON hash of hashes")
    concerns: dict[str, tuple[str, tuple[int, str]|None]] = dict()
    overall_correctness: bool = True
    fixed_concerns = set()
    for concern, judgement in judgements.items():
        blame = judgement.get('blame', None)
        fixed = judgement.get("fixed_in_subsequent_step", False)
        if fixed: # GPT seems not understanding an issues already fixed subsequently are OK
            fixed_concerns.add(concern)
            continue
        should_be_fixed_by = _utils.str_or_blank(judgement.get("should_be_fixed_by", ''))
        if should_be_fixed_by != '' and should_be_fixed_by != blame:
            raise ParseError(f"Blaming {blame} but think it should be fixed at {should_be_fixed_by}. Skip.")
        has_ok = 'ok' in judgement
        has_warning = 'warning' in judgement
        has_error = 'error' in judgement
        has_fatal = 'fatal' in judgement
        total = int(has_ok) + int(has_warning) + int(has_error) + int(has_fatal)
        if total != 1:
            raise ParseError(f"{concern} must have exactly one of 'ok', 'warning',or 'error' field.")
        overall_correctness = (overall_correctness and not has_error and not has_fatal)
        blame_steps: list[tuple[int, str]]|None = None
        if blame is not None:
            if isinstance(blame, str):
                blame = [blame]
            blame_steps = [parse_step_id_and_name(b) for b in blame if len(_utils.str_or_blank(b)) > 0]
        affecting = judgement.get('affecting', None)
        if has_warning:
            concerns[judgement['warning']] = ('warning', blame_steps)
        if has_error:
            issue = judgement['error']
            concerns[issue] = ('error', blame_steps)
            if affecting is not None and len(affecting) > 0:
                affected_by = ', '.join(f"step#{b[0]}" for b in blame_steps)
                affected_by = f"prior {affected_by} has been changed due to {issue}"
                affecting_steps: list[tuple[int, str]]|None
                affecting_steps = [parse_step_id_and_name(b) for b in affecting if len(_utils.str_or_blank(b)) > 0]
                blamed_step_ids = set(s[0] for s in blame_steps)
                last_blamed_step = max(blamed_step_ids)
                affecting_steps = [s for s in affecting_steps if s[0] not in blamed_step_ids and s[0] > last_blamed_step]
                concerns[affected_by] = ('affected', affecting_steps)
        if has_fatal:
            concerns[judgement['fatal']] = ('fatal', blame_steps)
    for concern in fixed_concerns:
        judgements.pop(concern)
    return concerns, judgements


def parse_issue_report(response, step_number_cutoff: int=None) \
        -> tuple[dict[str, _t.Tuple[str, list[tuple[int, str]]|None]], set[str]]:
    all_issues, _ = parse_verification_response(response)
    no_culprit_issues = set()
    for issue, (level, steps) in all_issues.items():
        if level in ('error', 'fatal'):
            if steps is None or len(steps) == 0:
                raise ParseError(f'Error "{issue}" has missing culprit. '
                                 f'Please add the "blame" attribute to assign the culprit step.')
            for si, (step_num, step_desc) in enumerate(steps):
                if step_num < 0 or step_number_cutoff is not None and step_num >= step_number_cutoff:
                    raise ParseError(f"Unknown step ID: step#{step_num}")
        if len(steps) == 0:
            no_culprit_issues.add(issue)
    return all_issues, no_culprit_issues


def parse_give_up_response(description: str) -> dict[str, tuple[str, list[tuple[int, str]]]]:
    description = _utils.str_or_blank(description)
    if len(description) == 0:
        raise ParseError("Must provide explanation why you gave up.")
    parsed = parse_json_hash(description)
    issues: dict[str, tuple[str, list[tuple[int, str]]]] = dict()

    def extract(subset, level):
        if subset is None or isinstance(subset, dict) and len(subset) == 0:
            return
        if not isinstance(subset, dict):
            raise ParseError("Invalid response format. Values of 'errors' and 'warnings' must be hashes of a list.")
        for issue, blamed_steps in subset.items():
            if isinstance(blamed_steps, str):
                blamed_steps = [blamed_steps]
            if not isinstance(blamed_steps, list):
                raise ParseError("Invalid response format. Values of 'errors' and 'warnings' must be hashes of a list.")
            blamed_steps = [parse_step_id_and_name(b) for b in blamed_steps]
            issues[issue] = (level, blamed_steps)
    extract(parsed.get('errors', None), 'fatal')
    extract(parsed.get('warnings', None), 'warning')
    if len(issues) == 0:
        raise ParseError("Must list issues under `errors` or `warning` JSON keys.")
    return issues


@_dc.dataclass(eq=False)
class StepDescriptor:
    description: str
    why: str|None
    sub_steps: dict[str, _t.Any]|None = None
    difficulty: int = 6

    def __eq__(self, __value):
        if self is __value:
            return True
        if not isinstance(__value, self.__class__):
            return False
        return self.description == __value.description


def parse_step_by_step_plan(text: str) -> tuple[dict[int, StepDescriptor], bool, bool]:
    try:
        plan = parse_json_hash(
            text, nested_hashes=True,
            except_keys={'has_branching', 'branching_among_steps', 'has_loop', 'looping_among_steps'})
    except ParseError as ex:
        if not 'no JSON hash found' in str(ex):
            raise ex
        plan = {str(i + 1): {"description": desc} for i, desc in enumerate(parse_ordered_list(text))}
    return validate_step_by_step_plan(plan)


def validate_step_by_step_plan(plan: dict[str, _t.Any]) -> tuple[dict[int, StepDescriptor], bool, bool]:
    results: dict[int, StepDescriptor] = dict()
    has_branching = plan.pop('has_branching', plan.pop('branching_among_steps', False))
    has_loop = plan.pop('has_loop', plan.pop('looping_among_steps', False))
    last_index = -1
    for i, item in plan.items():
        if not _re.match(r"^\d+$", i):
            raise ParseError(f"JSON hash key '{i}' is not an integer")
        key = int(i.split('.')[-1]) # sometimes we get step number in the form like "3.1", take the last
        if key <= last_index:
            raise ParseError(f"Element keys should be a contiguous natural number sequence starting at 1. "
                             f"Invalid key: '{key}'.")
        last_index = key
        if 'description' not in item:
            raise ParseError(f'Missing description for step {key}')

        descriptor = StepDescriptor(item['description'], item.get('why', None), item.get('sub_steps', None),
                                    difficulty=item.get('difficulty', 5))
        results[len(results) + 1] = descriptor
    if len(results) == 0:
        raise ParseError("Should have at least 2 steps in the plan. If only one step, answer directly")
    if len(results) == 1:
        sub_steps = next(iter(results.values())).sub_steps
        if sub_steps is None or len(sub_steps) == 0:
            raise ParseError("Should have at least 2 steps in the plan. If only one step, answer directly")
        return validate_step_by_step_plan(sub_steps)
    return results, has_branching, has_loop


def parse_ranking_response(text: str, expected_number: int) -> tuple[dict[int, float], dict[int, int]]:
    rankings = parse_json_hash(text, nested_hashes=True)
    results: {int: float} = dict()
    dupes: {int: int} = dict()
    removing = set()
    for i, item in rankings.items():
        if not _re.match(r"^\d+$", i):
            raise ParseError(f"JSON hash key '{i}' is not an integer")
        i = int(i)
        if i < 1 or i > expected_number:
            removing.add(str(i))
            print(f"WARNING: Key {i} is not in range [1,{expected_number}]")
            continue
        if i in results:
            raise ParseError(f"Proposal#{i} has multiple scores.")
        if 'score' not in item:
            raise ParseError(f"No 'score' for item {i}")
        score = item['score']
        if not _utils.safe_is_instance(score, (int, float)):
            raise ParseError(f"Score value '{score}' is not a number.")
        results[i] = float(score)
    for not_found in removing:
        del rankings[not_found]
    if len(rankings) < expected_number:
        raise ParseError(f"Expecting {expected_number} score rankings but found {len(rankings)}.")
    if len(rankings) != expected_number:
        print(f"WARNING: Expecting {expected_number} score rankings but found {len(rankings)}.")
    for i, item in rankings.items():
        i = int(i)
        if 'duplicate_of' in item:
            duplicate_of = item['duplicate_of']
            if duplicate_of is not None:
                dupes[i] = duplicate_of
                del results[i]
    if len(results) + len(dupes) != expected_number:
        raise ParseError(f"Expecting {expected_number} rankings, received {len(results)}")
    assert len(results.keys() & dupes.keys()) == 0
    return results, dupes


def parse_json_hash(text, nested_hashes=False, nested_list=False, except_keys: set[str]=None):
    except_keys = except_keys or set()
    match = _json_response_re.match(text)
    responses: dict[str, _t.Any]
    if match is None:
        try:
            responses = json.loads(text)
        except json.JSONDecodeError as e:
            raise ParseError("no JSON hash found or invalid JSON")
    else:
        json_text = match.group(3) if match.group(3) is not None else match.group(5)
        try:
            responses = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ParseError(f"JSON parse error: {e}")
    if not _utils.safe_is_instance(responses, dict):
        raise ParseError("The response must be a JSON hash")
    if nested_hashes and not all([_utils.safe_is_instance(x, dict)
                                  for k, x in responses.items() if k not in except_keys]):
        raise ParseError("The response must be a JSON hash of hashes")
    elif nested_list and not all([_utils.safe_is_instance(x, list)
                                  for k, x in responses.items() if k not in except_keys]):
        raise ParseError("The response must be a JSON hash of lists")
    return responses


def parse_json_list(text):
    match = _json_response_re.match(text)
    if match is None:
        raise ParseError("no JSON hash found")
    json_text = match.group(3) if match.group(3) is not None else match.group(5)
    try:
        responses: list[str] = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ParseError(f"JSON parse error: {e}")
    if not _utils.safe_is_instance(responses, list) or not all([_utils.safe_is_instance(x, str) for x in responses]):
        raise ParseError("The response must be a JSON list of strings")
    return responses


def parse_next_step_reply(text: str) -> tuple[str, NextStepDesc|str]:
    text = text.strip()
    if REPORT_ERROR in text:
        return REPORT_ERROR, text
    next_step, _ = parse_next_step_spec(text, required=True)
    return NEXT_I_WANT_TO_WORK_AT, next_step


_python_response_re = _re.compile(r"```python\n+(.+?)```", flags=_re.DOTALL | _re.IGNORECASE)


def parse_python_snippets(text: str) -> list[str]:
    return [m.group(1) for m in _python_response_re.finditer(text)]


_markdown_fenced_block_re = _re.compile(r"```+", flags=_re.DOTALL | _re.IGNORECASE)


def extract_fenced_blocks(text) -> tuple[dict[str, str], str]:
    """
    Deprecated. Use `check_and_fix_fenced_blocks`
    """
    fenced_blocks = dict()
    key_prefix = f"fenced_{_random.randint(1000, 10000000)}_"
    while True:
        match = _markdown_fenced_block_re.search(text, 0)
        if match is not None:
            open_pos = match.span()[0]
            n_backquotes = len(match.group(0))
            pattern = _re.compile('`' * n_backquotes)
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


def restore_fenced_block(text: str, fenced_blocks: dict[str, str]):
    for key, original in fenced_blocks.items():
        text = text.replace(key, original)
    return text


def gather_file_contents(markdown_full_content: str) -> tuple[str,str,str,str]|None:
    results: list[tuple[str, str, str, str]] = list()
    collapsed, blocks = check_and_fix_fenced_blocks(markdown_full_content, collapse_blocks=True)
    for digest, (snippet, content_type, line_number, _) in blocks.items():
        if snippet is None:
            continue
        block_lines = snippet.split('\n')
        content = '\n'.join(block_lines[1:-1])
        desc = collapsed.replace(digest + '\n', '').strip()
        desc = desc.replace(digest, '').strip() # to be safe
        results.append((content_type, content, snippet, desc))
    if len(results) != 1:
        raise ParseError(f"Need exactly one file content fenced block. Found {len(results)}")
    content_type, content, snippet, desc = results[0]
    return content_type, content, snippet, desc


def match_step_name(actual: str, expected_step_num: int, expected_step_name: str) -> bool:
    import Levenshtein
    dist = min(Levenshtein.distance(actual, expected_step_name),
               Levenshtein.distance(actual, f"{expected_step_num}: {expected_step_name}"))
    return dist < (0.95 * len(actual))


_fenced_block_quote_re = _re.compile(r"^(\s*)(`{3,})(\S*)\s*$")


def check_and_fix_fenced_blocks(markdown_text: str, collapse_blocks=False) \
        -> tuple[str, dict[str, tuple[str, str, int, str]]]:
    stack = []
    top_level_blocks: dict[int, list[str]] = dict()
    blocks_by_hash: dict[str, tuple[str, str, int, str]] = dict()

    lines = markdown_text.split('\n')
    result = []

    current_top_level_block_lines = None
    for line_number, line in enumerate(lines, start=1):
        m = _fenced_block_quote_re.match(line)
        if m is not None:
            indentation: str = m.group(1).replace("\t", "    ")
            backticks: str = m.group(2)
            content_type: str = m.group(3)
            if _re.match(r"^\d+$", content_type):
                content_type = ''
            normalized_backticks = f"{indentation}{backticks}{content_type}"

            last_block = stack[-1] if len(stack) > 0 else None
            if last_block is None or backticks != last_block[1][1]:
                # It's an opening fence, push onto the stack
                if last_block is not None:
                    if len(last_block[1][1]) < len(backticks):
                        err_msg = """\
Outer block open fence at line {last_block} has less backticks than inner block at line {line_number}; 
likely the block at {last_block} is not closed properly, or if there is nested fenced block, follow the rule below:

````markdown
An outer fenced block's backtick quote
* must has more backticks than
  ```
  an inner block
  ```
````
""".format(last_block=last_block[0], line_number=line_number)
                        raise UnbalancedBlockParseError(err_msg, original=markdown_text)
                    if last_block[1][2] is not None and last_block[1][2] not in ('markdown', ''):
                        raise ParseError(
                            f"Outer block at line {last_block[0]} is not of `markdown` type "
                            f"but contains nested fenced block. This is not supported. ", original=markdown_text)
                if current_top_level_block_lines is not None:
                    current_top_level_block_lines.append(normalized_backticks)
                else: # new block
                    current_top_level_block_lines = [line]
                    top_level_blocks[line_number] = current_top_level_block_lines
                stack.append((line_number, (indentation, backticks, content_type)))
            else:
                # It's a closing fence, pop from the stack
                open_line, open_fence = stack.pop()
                if indentation != open_fence[0]:
                    raise ParseError(f"Unbalanced indentation for fenced block at {open_line}:{line_number}.",
                                     original=markdown_text)
                if len(content_type) > 0:
                    raise UnbalancedBlockParseError(
                        f"New fenced block detected at line {line_number} before the block at line"
                        f" {open_line} is closed properly. Also check the nested block syntax.", original=markdown_text)
                if current_top_level_block_lines is not None:
                    current_top_level_block_lines.append(normalized_backticks)
                if len(stack) == 0:
                    markdown_block = '\n'.join(current_top_level_block_lines)
                    digest = _hashlib.sha256(markdown_block.encode('UTF-8')).hexdigest()
                    block_content = '\n'.join(current_top_level_block_lines[1:])
                    block_content = block_content.replace(open_fence[1], '')
                    blocks_by_hash[digest] = (markdown_block, open_fence[2], open_line, block_content)
                    if collapse_blocks:
                        result.append(digest)
                    current_top_level_block_lines = None
            if not collapse_blocks:
                result.append(normalized_backticks)
        else:
            if current_top_level_block_lines is not None:
                current_top_level_block_lines.append(line)
            else:
                # this is to make the Markdown logging not corrupted by unquoted HTML tags
                unquoted_html_tag_re = _re.compile(r"([^`])(`+)?(<[a-z]+>)(`+)?", flags=_re.IGNORECASE)
                line = unquoted_html_tag_re.sub(r"\1`\3`", line)
            if len(stack) == 0 or not collapse_blocks:
                result.append(line)

    if stack:
        unmatched_lines = list(str(block[0]) for block in stack)
        unmatched_lines = ('line ' if len(unmatched_lines) == 1 else 'lines ') + ', '.join(unmatched_lines)
        raise ParseError(f"Unbalanced fenced block detected. No matching closing backticks for fenced block "
                         f"stating at line {unmatched_lines}.", original=markdown_text)
    return '\n'.join(result), blocks_by_hash


def annotate_fenced_block_backtick_quotes(content):
    marker_count = 0

    def annotate_backticks(match: _re.Match):
        nonlocal marker_count
        marker_count += 1
        return f"{match.group(1)}{match.group(2) or ''} # BACKTICK{marker_count}\n"

    content = _re.sub(r"(`{3,})([a-z][a-z0-9]+)?\d*(\n|$)", annotate_backticks, content)
    return content


def fix_nested_markdown_blocks_by_report(content: str, match_results: list[dict[str, str | int | None]]):
    max_level = max(item['level'] for item in match_results if item['open'] is not None) if len(match_results) > 0 else 3
    report_sorted = sorted(match_results, key=lambda x: x['level'], reverse=True)
    for item in report_sorted:
        open_tag = item['open']
        close_tag = item['close']
        level = item['level']

        if close_tag is None:
            _logger.error(f"Missing close tag:\n{json.dumps(match_results, indent=2)}")
            raise ParseError(f"Unmatched backtick quote.")

        num_backticks = 3 + max_level - level

        new_backticks = '`' * num_backticks
        content = _re.sub(rf"`{{3,}}(\S*) *# {open_tag}.*", rf"{new_backticks}\1", content)
        content = _re.sub(rf"`{{3,}} *# {close_tag}.*", new_backticks, content)

    # Remove all remaining backtick markers
    content = _re.sub(r" # BACKTICK\d+", "", content)
    return content


def normalize_path(string: str) -> str:
    matched = _re.match(r"/*(([.a-zA-Z0-9_\-]+/+)*[.a-zA-Z0-9_]+)$", string.strip())
    if not matched:
        raise ParseError("Make sure to include file path consisting slash-separated components of only "
                         "alphanumeric, period, dash, and underscore characters. "
                         "Only file path is allowed, not directory path ending with slash.")
    path = matched.group(1)
    return _re.sub(r'/+', '/', path)
