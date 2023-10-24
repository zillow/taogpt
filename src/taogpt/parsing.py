from __future__ import annotations

import random as _random
import re
import json
import typing as _t
import dataclasses as _dc
import taogpt.utils as _utils
from taogpt.constants import (
    WILL_ASK_QUESTIONS,
    WILL_ANSWER_DIRECTLY,
    FREE_TEXT,
    NEXT_I_WANT_TO_WORK_AT,
    FINAL_ANSWER,
    UNSOLVABLE
)

_all_step_types = '|'.join([
    WILL_ANSWER_DIRECTLY,
    WILL_ASK_QUESTIONS
])
_step_type_re = re.compile(
    r"(^|\n)#{1,2}\s*(I_WILL_ANSWER_DIRECTLY"
    r"|LET_ME_ASK_THE_PYTHON_GENIE"
    r"|BACKTRACK_ON_ERROR"
    r"|FINAL_ANSWER"
    r"|I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED"
    r"|HERE_IS_MY_STEP_BY_STEP_PLAN).*\n((.|\n)+)"
)
_true_false_answer_re = re.compile(r"^\s*(.+)?\s*(true|false|yes|no)$",
                                   flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
_whitespace_re = re.compile(r"\s+", flags=re.DOTALL)
_ordered_list_re = re.compile(r'\n\s*(\d+)\.\s+(.*?)(?=\n\s*(\d+)|\n\n|\Z)', flags=re.DOTALL)
strip_quotes_re = re.compile(r"^\s+|[\s\"\'.,]+$|[\"\']", flags=re.DOTALL)

class ParseError(ValueError):
    pass


def parse_step_type_spec(text: str) -> _t.Optional[(str, str)]:
    text = _utils.str_or_blank(text)
    if text == '':
        return None, None
    match: re.Match = _step_type_re.search(text)
    if match is None:
        return None, None
    step_type, definition = match.group(2), _utils.str_or_blank(match.group(3))
    if definition == '':
        return None, None
    return step_type, definition


def parse_sections(text: str, section_level: str='##') -> {str: str|None}:
    try:
        fenced_blocks, text = extract_fenced_blocks(text)
    except SyntaxError as e:
        raise ParseError(str(e))
    matched_sections = {FREE_TEXT: ''}
    section = FREE_TEXT
    for line in text.split('\n'):
        match: re.Match = re.match(rf"^{section_level}+\s+([^\n]+)", line)
        if match is not None:
            section = match.group(1).strip()
            while section.endswith(':'):
                section = section[:-1]
            matched_sections[section] = ''
        else:
            matched_sections[section] += line + '\n'

    return {k: (restore_fenced_block(text, fenced_blocks).strip() if text is not None else None)
            for k, text in matched_sections.items()}


def parse_ordered_list(markdown_text) -> [str]:
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
    if len(matches) == 0:
        raise ParseError("No list presented.")
    return matches


_json_response_re = re.compile(r"^.*(```(json)?\n+)(.+)(```).*$|^\s*(\{.+})\s*$", flags=re.DOTALL | re.IGNORECASE)
_final_solution_check_re = re.compile(r"^\s*(yes|no)[.,]?\s+(.+)$", flags=re.DOTALL|re.IGNORECASE)


def parse_final_response(text: str) -> _t.Tuple[bool, _t.Dict[str, str]]:
    judgements: _t.Dict[str, _t.Dict[str, _t.Union[bool, str]]] = parse_json_hash(text, two_level_hashes=True)
    if not _utils.safe_is_instance(judgements, dict) or not all([_utils.safe_is_instance(x, dict) for x in judgements.values()]):
        raise ParseError("The response must be a JSON hash of hashes")
    concerns: _t.Dict[str, str] = dict()
    overall_correctness: bool = True
    for concern, judgement in judgements.items():
        if 'ok' not in judgement:
            raise ParseError(f"{concern} does not have the 'ok' field.")
        item_correctness = judgement['ok']
        if type(item_correctness) != bool:
            raise ParseError(f"the 'ok' field of {concern} is not a JSON boolean.")
        overall_correctness = (overall_correctness and item_correctness)
        if not item_correctness:
            reason = judgement.get('reason', judgement.get('finding', ''))
            concerns[concern] = reason
            # reason = f": {reason}" if reason != '' else ''
            # concerns.add(f"* {concern}{reason}")
    return overall_correctness, concerns


@_dc.dataclass
class StepDescriptor:
    description: str
    why: str


def parse_step_by_step_plan(text: str) -> _t.Dict[int, StepDescriptor]:
    results: {int: StepDescriptor} = dict()
    try:
        plan = parse_json_hash(text, two_level_hashes=True)
    except ParseError as ex:
        if not 'no JSON hash found' in str(ex):
            raise ex
        plan = {str(i + 1): {"description": desc} for i, desc in enumerate(parse_ordered_list(text))}
    for i, item in plan.items():
        if not re.match(r"^\d+$", i):
            raise ParseError(f"JSON hash key '{i}' is not an integer")
        key = int(i)
        index = len(results) + 1
        if key != index:
            raise ParseError(f"Element keys should be a contiguous natural number sequence starting at 1. "
                             f"Key '{key}' should be '{index}'.")
        if 'description' not in item:
            raise ParseError(f'Missing description for step {key}')
        results[index] = StepDescriptor(item['description'], item.get('why', None))
    if len(results) < 2:
        raise ParseError("Should have at least 2 steps in the plan. If only one step, choose answering directly")
    return results


def parse_ranking_response(text: str, expected_number: int) -> _t.Tuple[_t.Dict[int, float], _t.Dict[int, int]]:
    rankings = parse_json_hash(text, two_level_hashes=True)
    results: {int: float} = dict()
    dupes: {int: int} = dict()
    for i, item in rankings.items():
        if not re.match(r"^\d+$", i):
            raise ParseError(f"JSON hash key '{i}' is not an integer")
        i = int(i)
        if i < 1 or i > expected_number:
            raise ParseError(f"Key {i} is not in range [1,{expected_number}]")
        if i in results:
            raise ParseError(f"Approach {i} has multiple scores.")
        if 'score' not in item:
            raise ParseError(f"No 'score' for item {i}")
        score = item['score']
        if not _utils.safe_is_instance(score, (int, float)):
            raise ParseError(f"Score value '{score}' is not a number.")
        results[i] = float(score)
    if len(rankings) != expected_number:
        raise ParseError(f"Expecting {expected_number} score rankings but found {len(rankings)}.")
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


def parse_json_hash(text, two_level_hashes=False):
    match = _json_response_re.match(text)
    responses: _t.Dict[str, _t.Any]
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
    if two_level_hashes and not all([_utils.safe_is_instance(x, dict) for x in responses.values()]):
        raise ParseError("The response must be a JSON hash of hashes")
    return responses


def parse_json_list(text):
    match = _json_response_re.match(text)
    if match is None:
        raise ParseError("no JSON hash found")
    json_text = match.group(3) if match.group(3) is not None else match.group(5)
    try:
        responses: _t.List[str] = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ParseError(f"JSON parse error: {e}")
    if not _utils.safe_is_instance(responses, list) or not all([_utils.safe_is_instance(x, str) for x in responses]):
        raise ParseError("The response must be a JSON list of strings")
    return responses


def parse_next_step_reply(text: str) -> (str, str|None):
    sections: _t.Dict[str, str] = parse_sections(text, section_level='#')
    sections.pop(FREE_TEXT)
    for section in [FINAL_ANSWER, UNSOLVABLE]:
        if section in sections:
            remaining = sections.pop(section)
            return section, (f"# {section}\n{remaining}", None)
    if NEXT_I_WANT_TO_WORK_AT not in sections:
        raise ParseError(f"No section header `# NEXT_I_WANT_TO_WORK_AT`")
    next_step_desc = sections.pop(NEXT_I_WANT_TO_WORK_AT).strip()
    next_step_desc = _utils.single_space(strip_quotes_re.sub('', next_step_desc))
    if _utils.str_or_blank(next_step_desc) == '':
        raise ParseError('Missing next step description')
    if len(sections) == 0:
        raise ParseError("Missing a strategy section for the next step")
    if len(sections) > 1:
        raise ParseError("More than one strategy sections")
    strategy, details = next(iter(sections.items()))
    return NEXT_I_WANT_TO_WORK_AT, (next_step_desc, f"# {strategy}\n{details}")


def is_final_answer(next_step) -> bool:
    next_step = _utils.str_or_blank(next_step).lower()
    return next_step.startswith('none') or 'this is the final step' in next_step


_python_response_re = re.compile(r"```python\n+(.+?)```", flags=re.DOTALL | re.IGNORECASE)


def parse_python_snippets(text: str) -> [str]:
    return [m.group(1) for m in _python_response_re.finditer(text)]


_markdown_fenced_block_re = re.compile(r"```+", flags=re.DOTALL | re.IGNORECASE)


def extract_fenced_blocks(text) -> _t.Tuple[_t.Dict[str, str], str]:
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


_markdown_fenced_block_content_re = re.compile(r'(?P<snippet>```(?P<type>[^\n]*?)\n(?P<content>.*?)```)',
                                               flags=re.DOTALL)

def extract_fenced_content(text) -> _t.Tuple[_t.Optional[str], _t.Optional[str], _t.Optional[str]]:
    match = _markdown_fenced_block_content_re.search(text)
    if match is not None:
        return match.group('type'), match.group('content').strip(), match.group('snippet').strip()
    return None, None, None


file_section_re = re.compile(r"FILE:?\s*(.+)")


def gather_file_contents(sections: _t.Dict[str, str], pop_file_sections=False) \
        -> _t.Dict[str, _t.Tuple[str, str, str, str]]:
    file_sections = set()
    results: _t.Dict[str, _t.Tuple[str, str, str, str]] = dict()
    for section, markdown_full_content in sections.items():
        match = re.match(file_section_re, section)
        if match is None:
            continue
        file_sections.add(section)
        file_path = match.group(1)
        if file_path == '':
            raise ParseError(f"No file path for file section '{section}'")
        content_type, content, snippet = extract_fenced_content(markdown_full_content)
        if content is None:
            raise ParseError(f"No content (in markdown fenced block) for section '{section}'")
        markdown_full_content = markdown_full_content.replace(snippet, '')
        results[file_path] = (content_type, content, snippet, markdown_full_content)
    if pop_file_sections:
        for section in file_sections:
            sections.pop(section)
    return results


def match_step_name(actual: str, expected_step_num: int, expected_step_name: str) -> bool:
    import Levenshtein
    dist = max(Levenshtein.distance(actual, expected_step_name),
               Levenshtein.distance(actual, f"{expected_step_num}: {expected_step_name}"))
    return dist >= 0.95
