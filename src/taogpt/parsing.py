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
    r"|MY_FINAL_ANSWER"
    r"|UNSOLVABLE_I_GIVE_UP"
    r"|I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED"
    r"|HERE_IS_MY_STEP_BY_STEP_PLAN).*\n((.|\n)+)"
)
_true_false_answer_re = re.compile(r"^\s*(.+)?\s*(true|false|yes|no)$",
                                   flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
_whitespace_re = re.compile(r"\s+", flags=re.DOTALL)

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
        match: re.Match = re.match(r"^##+\s+([^:]+):?\s*", line)
        if match is not None:
            section = match.group(1)
            matched_sections[section] = ''
        else:
            matched_sections[section] += line + '\n'
    return {k: (text.strip() if text is not None else None) for k, text in matched_sections.items()}


_ordered_list_re = re.compile(r'\n?(\d+)\.\s+(.*?)(?=\n\d+\.|\n\n|\Z)', flags=re.DOTALL)


def parse_ordered_list(md) -> [str]:
    """
    Parse a simplified markdown list without consideration to multi-line indentation.
    :param md: markdown text
    :return: a list of string
    """
    expected_number = 1
    matches = []
    for m in _ordered_list_re.finditer(md):
        bullet = m.group(1)
        assert int(bullet) == expected_number
        expected_number += 1
        matches.append(_whitespace_re.sub(' ', m.group(2)).strip())
    return matches


_final_solution_check_re = re.compile(r"^\s*(yes|no)[.,]?\s+(.+)$", flags=re.DOTALL|re.IGNORECASE)


def parse_final_response(text: str) -> (bool, str):
    match = _final_solution_check_re.match(text)
    if match:
        return 'yes' == match.group(1).lower(), match.group(2)
    raise ParseError("Response must start with 'yes' or 'no'.")
    # return 'the answer is correct' in text.lower(), _utils.str_or_blank(text)


def parse_ranking_response(text: str, expected_number: int) -> _t.Tuple[_t.Dict[int, float], _t.Dict[int, int]]:
    rankings = parse_ordered_list(text)
    if len(rankings) == 0:
        raise ParseError(f"No rankings found in response: {text[:20]}...")

    pattern = re.compile(r'\s*(score:?|duplicate of:?) +(-?\d+(\.\d+)?)\s*(\[.*])?')
    results: {int: float} = dict()
    dupes: {int: int} = dict()
    for i, item in enumerate(rankings):
        match: re.Match = pattern.match(item)
        if match:
            if 'duplicate' in match.group(1).lower():
                dupes[i+1] = int(match.group(2))
            else:
                results[i+1] = float(match.group(2))
    if len(results) + len(dupes) != expected_number:
        assert ParseError(f"Expecting {expected_number} rankings, received {len(results)}")
    assert len(results.keys() & dupes.keys()) == 0
    return results, dupes


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
