from __future__ import annotations
import re
import typing as _t
import taogpt.utils as _utils
from taogpt.constants import WILL_ASK_QUESTIONS, WILL_ANSWER_DIRECTLY, \
    DONE, FREE_TEXT, MY_ANSWER

_all_step_types = '|'.join([
    WILL_ANSWER_DIRECTLY,
    WILL_ASK_QUESTIONS
])
_step_type_re = re.compile(
    r"^#\s*(I_WILL_ANSWER_THIS_STEP_DIRECTLY"
    r"|UNSOLVABLE_I_GIVE_UP"
    r"|I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED"
    r"|HERE_IS_MY_STEP_BY_STEP_PLAN).*\n((.|\n)+)"
)
_true_false_answer_re = re.compile(r"^\s*(.+)?\s*(true|false|yes|no)$",
                                   flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
# _all_look_good_answer_re = re.compile(r"^\s*(all look good)?\.?\s*(.+)$",
#                                       flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)


class ParseError(ValueError):
    pass


def parse_step_type_spec(text: str) -> _t.Optional[(str, str)]:
    text = _utils.str_or_blank(text)
    if text == '':
        return None
    match: re.Match = _step_type_re.match(text)
    if match is None:
        return None
    step_type, definition = match.group(1), _utils.str_or_blank(match.group(2))
    if definition == '':
        return None
    return step_type, definition


def parse_sections(text: str) -> {str: str|None}:
    matched_sections = {FREE_TEXT: ''}
    section = FREE_TEXT
    for line in text.split('\n'):
        match: re.Match = re.match(r"^##\s+([^:]+):?\s*", line)
        if match is not None:
            section = match.group(1)
            matched_sections[section] = ''
        else:
            matched_sections[section] += line + '\n'
    return {k: (text.strip() if text is not None else None) for k, text in matched_sections.items()}


def parse_ordered_list(text: str) -> [str]:
    items = []
    current_index: _t.Optional[int] = None
    current_item = ''
    for line in text.split('\n'):
        match: re.Match = re.match(r"^(\d)+\.\s+(.+)$", line)
        if match is not None:
            ith = int(match.group(1))
            if current_index is not None:
                assert ith == (current_index + 1), f"expecting {current_index + 1}, got {ith}"
                items.append(current_item.strip())
                current_item = '' # reset
            current_index = ith
            current_item += match.group(2)
        elif current_index is not None:
            current_item += line + ' '
    if current_index is not None:
        items.append(current_item.strip())
    return items


def parse_step_unordered_list(text: str) -> [str]:
    items = []
    in_bullet = False
    current_item = ''
    for line in text.split('\n'):
        match: re.Match = re.match(r"^(\*)+\s+(.+)$", line)
        if match is not None:
            assert match.group(1) == '*'
            if in_bullet:
                items.append(current_item.strip())
                current_item = '' # reset
            in_bullet = True
            current_item += match.group(2).strip() + '\n'
        elif in_bullet:
            current_item += line.strip() + '\n'
    if in_bullet:
        items.append(current_item.strip())
    return items


def parse_final_response(text: str) -> (bool, str):
    return 'the answer is correct' in text.lower(), _utils.str_or_blank(text)


def parse_dead_end_check_response(text: str) -> (bool, str):
    match: re.Match = _true_false_answer_re.match(text)
    if match is None:
        raise ParseError("No true/false answer at the end")
    prediction = match.group(2)
    return 'true' in prediction or 'yes' in prediction, _utils.remove_brackets(match.group(1))


def parse_ranking_response(text: str, expected_number: int) -> {int: float}:
    rankings = parse_ordered_list(text)
    if len(rankings) == 0:
        raise ParseError(f"No rankings found in response: {text[:20]}...")

    pattern = re.compile(r'\s*score:? +(-?\d+(\.\d+)?)\s*(\[.*])?')
    results = dict()
    for i, item in enumerate(rankings):
        match: re.Match = pattern.match(item)
        if match:
            results[i+1] = float(match.group(1))
    if len(results) != expected_number:
        assert ParseError(f"Expecting {expected_number} rankings, received {len(results)}")
    return results


def parse_next_step_reply(text: str) -> (str, str|None):
    sections = parse_sections(text)
    free_text = sections.get(FREE_TEXT, '')
    match: re.Match = re.match(r"^\s*I'm done", free_text, flags=re.IGNORECASE)
    if match:
        return DONE, sections.get(MY_ANSWER, None)
    match: re.Match = re.match(r"^\s*I want to work on:?\s+(.+)", free_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(), None
    raise ParseError(f'Unexpected next step reply')
