from __future__ import annotations

import random as _random
import re
import hashlib as _hashlib
import json
import typing as _t
import dataclasses as _dc
import taogpt.utils as _utils
from taogpt.constants import (
    WILL_ASK_QUESTIONS,
    MY_THOUGHT,
    FREE_TEXT,
    NEXT_I_WANT_TO_WORK_AT,
    PRIOR_PROPOSAL,
    REPORT_ERROR
)

_all_step_types = '|'.join([
    MY_THOUGHT,
    WILL_ASK_QUESTIONS
])
step_type_re = re.compile(
    r"(^|\n)#{1,2}\s*(MY_THOUGHT"
    r"|LET_ME_ASK_THE_PYTHON_GENIE"
    r"|I_FOUND_ERRORS"
    r"|FINAL_ANSWER"
    r"|I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED"
    r"|HERE_IS_MY_STEP_BY_STEP_PLAN).*\n((.|\n)+)"
)
_true_false_answer_re = re.compile(r"^\s*(.+)?\s*(true|false|yes|no)$",
                                   flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
_whitespace_re = re.compile(r"\s+", flags=re.DOTALL)
_ordered_list_re = re.compile(r'\n\s*(\d+)\.\s+(.*?)(?=\n\s*(\d+)|\n\n|\Z)', flags=re.DOTALL)
_fix_fenced_block_backticks_re = re.compile(r"^(\s*)(```+)(\d*)")

strip_quotes_re = re.compile(r"^\s+|[\s\"\'.,]+$|[\"\']", flags=re.DOTALL)
step_name_re = re.compile(r"^\s*(((\d|\.)+)\s+)?(.+)")


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


class ParseError(ValueError):
    pass


def parse_step_type_spec(text: str) -> tuple[str|None, str|None]|None:
    text = _utils.str_or_blank(text)
    if text == '':
        return None, None
    match: re.Match = step_type_re.search(text)
    if match is None:
        return None, None
    step_type, definition = match.group(2), _utils.str_or_blank(match.group(3))
    if definition == '':
        return None, None
    return step_type, definition


def parse_sections(text: str, section_level: str='##') -> dict[str, str|None]:
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


_json_response_re = re.compile(r"^.*(```(json)?\n+)(.+)(```).*$|^\s*(\{.+})\s*$", flags=re.DOTALL | re.IGNORECASE)
_final_solution_check_re = re.compile(r"^\s*(yes|no)[.,]?\s+(.+)$", flags=re.DOTALL|re.IGNORECASE)

at_step_re = re.compile(r"\[ *at +step(.*?)]", flags=re.IGNORECASE)
_step_re = re.compile(r"^( *\[? *(at )?(step#)?(\d+): *)?(.*?)[\s\]]*$", flags=re.IGNORECASE)
_next_step_re = re.compile(r"^( *\[? *(at )?step#?\d*:? *)?(response to +)?(.*?)[\s\]]*$", flags=re.IGNORECASE)
_proposal_re = re.compile(f"^\s*\[?{PRIOR_PROPOSAL}", flags=re.IGNORECASE)

def parse_step_id_and_name(text: str) -> tuple[int, str]:
    text = _utils.str_or_blank(text)
    if _proposal_re.search(text) is not None:
        raise ParseError("You tried to report error in other proposals. Error report is only for previous executed "
                         "steps. Either report issues in previous steps or try different strategies.")
    match = _step_re.match(text)
    if match is None:
        raise ParseError("Step number and description must be in the format of 'step#<num>: <string description>'.")
    try:
        step_num = int(match.group(4))
        return (step_num, match.group(5))
    except TypeError:
        raise ParseError("Step number and description must be in the format of 'step#<num>: <string description>'.")


def parse_next_step_name(text: str) -> str:
    match = _next_step_re.match(text)
    return match.group(4) if match is not None else None


def parse_verification_response(text: str) -> tuple[dict[str, tuple[str, list[tuple[int, str]]|None]], dict]:
    judgements: dict[str, dict[str, _t.Union[bool, str]]] = parse_json_hash(text, nested_hashes=True)
    if (not _utils.safe_is_instance(judgements, dict)
            or not all([_utils.safe_is_instance(x, dict) for x in judgements.values()])):
        raise ParseError("The response must be a JSON hash of hashes")
    concerns: dict[str, tuple[str, tuple[int, str]|None]] = dict()
    overall_correctness: bool = True
    for concern, judgement in judgements.items():
        has_ok = 'ok' in judgement
        has_warning = 'warning' in judgement
        has_error = 'error' in judgement
        has_fatal = 'fatal' in judgement
        total = int(has_ok) + int(has_warning) + int(has_error) + int(has_fatal)
        if total != 1:
            raise ParseError(f"{concern} must have exactly one of 'ok', 'warning',or 'error' field.")
        overall_correctness = (overall_correctness and not has_error and not has_fatal)
        blame = judgement.get('blame', None)
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
            if affecting is not None:
                affected_by = ', '.join(f"step#{b[0]}" for b in blame_steps)
                affected_by = f"prior {affected_by} has been changed due to {issue}"
                affecting_steps: list[tuple[int, str]]|None
                affecting_steps = [parse_step_id_and_name(b) for b in affecting if len(_utils.str_or_blank(b)) > 0]
                concerns[affected_by] = ('affected', affecting_steps)
        if has_fatal:
            concerns[judgement['fatal']] = ('fatal', blame_steps)
    return concerns, judgements


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


@_dc.dataclass
class StepDescriptor:
    description: str
    why: str|None
    sub_steps: dict[str, _t.Any]|None = None


def parse_step_by_step_plan(text: str) -> dict[int, StepDescriptor]:
    try:
        plan = parse_json_hash(text, nested_hashes=True)
    except ParseError as ex:
        if not 'no JSON hash found' in str(ex):
            raise ex
        plan = {str(i + 1): {"description": desc} for i, desc in enumerate(parse_ordered_list(text))}
    return validate_step_by_step_plan(plan)


def validate_step_by_step_plan(plan: dict[str, _t.Any]) -> dict[int, StepDescriptor]:
    results: dict[int, StepDescriptor] = dict()
    last_index = -1
    for i, item in plan.items():
        if not re.match(r"^\d+$", i):
            raise ParseError(f"JSON hash key '{i}' is not an integer")
        key = int(i.split('.')[-1]) # sometimes we get step number in the form like "3.1", take the last
        if key <= last_index:
            raise ParseError(f"Element keys should be a contiguous natural number sequence starting at 1. "
                             f"Invalid key: '{key}'.")
        last_index = key
        if 'description' not in item:
            raise ParseError(f'Missing description for step {key}')
        results[len(results) + 1] = StepDescriptor(item['description'], item.get('why', None),
                                                   item.get('sub_steps', None))
    if len(results) == 0:
        raise ParseError("Should have at least 2 steps in the plan. If only one step, answer directly")
    if len(results) == 1:
        sub_steps = next(iter(results.values())).sub_steps
        if sub_steps is None or len(sub_steps) == 0:
            raise ParseError("Should have at least 2 steps in the plan. If only one step, answer directly")
        return validate_step_by_step_plan(sub_steps)
    return results


def parse_ranking_response(text: str, expected_number: int) -> tuple[dict[int, float], dict[int, int]]:
    rankings = parse_json_hash(text, nested_hashes=True)
    results: {int: float} = dict()
    dupes: {int: int} = dict()
    removing = set()
    for i, item in rankings.items():
        if not re.match(r"^\d+$", i):
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


def parse_json_hash(text, nested_hashes=False, nested_list=False):
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
    if nested_hashes and not all([_utils.safe_is_instance(x, dict) for x in responses.values()]):
        raise ParseError("The response must be a JSON hash of hashes")
    elif nested_list and not all([_utils.safe_is_instance(x, list) for x in responses.values()]):
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


def parse_next_step_reply(text: str) -> tuple[str, tuple[str, str|None]]:
    sections: dict[str, str] = parse_sections(text, section_level='#')
    sections.pop(FREE_TEXT)
    for section in [REPORT_ERROR]:
        if section in sections:
            remaining = sections.pop(section)
            return section, (f"# {section}\n{remaining}", None)
    if NEXT_I_WANT_TO_WORK_AT not in sections:
        raise ParseError(f"No section header `# {NEXT_I_WANT_TO_WORK_AT}`")
    next_step_desc = sections.pop(NEXT_I_WANT_TO_WORK_AT).strip()
    next_step_desc = _utils.single_space(strip_quotes_re.sub('', next_step_desc))
    if _utils.str_or_blank(next_step_desc) == '':
        raise ParseError('Missing next step description')
    next_step_desc = parse_next_step_name(next_step_desc)
    return NEXT_I_WANT_TO_WORK_AT, (next_step_desc, None)


def is_final_answer(next_step) -> bool:
    next_step = _utils.str_or_blank(next_step).lower()
    return next_step.startswith('none') or 'this is the final step' in next_step


_python_response_re = re.compile(r"```python\n+(.+?)```", flags=re.DOTALL | re.IGNORECASE)


def parse_python_snippets(text: str) -> list[str]:
    return [m.group(1) for m in _python_response_re.finditer(text)]


_markdown_fenced_block_re = re.compile(r"```+", flags=re.DOTALL | re.IGNORECASE)


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


def restore_fenced_block(text: str, fenced_blocks: dict[str, str]):
    for key, original in fenced_blocks.items():
        text = text.replace(key, original)
    return text


file_section_re = re.compile(r"FILE[\s:]+[\s\"\'`]*([^\s\"\'`]+)?[\s\"\'`]*")


def gather_file_contents(sections: dict[str, str], pop_file_sections=False) \
        -> dict[str, tuple[str, str, str, str]]:
    file_sections = set()
    results: dict[str, tuple[str, str, str, str]] = dict()
    for section, markdown_full_content in sections.items():
        match = re.match(file_section_re, section)
        if match is None:
            continue
        file_path = match.group(1)
        if file_path is None or file_path.strip() == '':
            raise ParseError(f"No file path for file section '{section}'")
        file_sections.add(section)
        collapsed, blocks = check_and_fix_fenced_blocks(markdown_full_content, collapse_blocks=True)
        if len(blocks) != 1:
            raise ParseError(f"File section {section} must have exactly one markdown block.")
        digest, (snippet, content_type, line_number) = next(iter(blocks.items()))
        if snippet is None:
            raise ParseError(f"No content (in markdown fenced block) for section '{section}'")
        block_lines = snippet.split('\n')
        content = '\n'.join(block_lines[1:-1])
        desc = collapsed.replace(digest + '\n', '')
        desc = desc.replace(digest, '') # to be safe
        results[file_path] = (content_type, content, snippet, desc)
    if pop_file_sections:
        for section in file_sections:
            sections.pop(section)
    return results


def match_step_name(actual: str, expected_step_num: int, expected_step_name: str) -> bool:
    import Levenshtein
    dist = min(Levenshtein.distance(actual, expected_step_name),
               Levenshtein.distance(actual, f"{expected_step_num}: {expected_step_name}"))
    return dist < (0.95 * len(actual))


_fenced_block_quote_re = re.compile(r"^(\s*)(`{3,})(\S*)\s*$")


def check_and_fix_fenced_blocks(markdown_text: str, collapse_blocks=False) \
        -> tuple[str, dict[str, tuple[str, str, int]]]:
    stack = []
    top_level_blocks: dict[int, list[str]] = dict()
    blocks_by_hash: dict[str, tuple[str, str, int]] = dict()

    lines = markdown_text.split('\n')
    result = []

    current_top_level_block_lines = None
    for line_number, line in enumerate(lines, start=1):
        m = _fenced_block_quote_re.match(line)
        if m is not None:
            indentation: str = m.group(1).replace("\t", "    ")
            backticks: str = m.group(2)
            content_type: str = m.group(3)
            if re.match(r"^\d+$", content_type):
                content_type = ''
            normalized_backticks = f"{indentation}{backticks}{content_type}"

            last_block = stack[-1] if len(stack) > 0 else None
            if last_block is None or backticks != last_block[1][1]:
                # It's an opening fence, push onto the stack
                if last_block is not None:
                    if len(last_block[1][1]) < len(backticks):
                        raise ParseError(
                            f"Outer block open fence at line {last_block[0]} has less backticks than inner block"
                            f" at line {line_number}; likely the block at {last_block[0]} is not closed properly, "
                            f"or the rule that outer block is fenced with more backticks than inner blocks is not "
                            f"followed.")
                    if last_block[1][2] != 'markdown':
                        raise ParseError(
                            f"Outer block at line {last_block[0]} is not of markdown type "
                            f"but contains nested fenced block. This is not supported. ")
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
                    raise ParseError(f"Unbalanced indentation for fenced block at {open_line}:{line_number}.")
                if len(content_type) > 0:
                    raise ParseError(f"New fenced block detected at line {line_number} before the block at line"
                                     f" {open_line} is closed properly.")
                if current_top_level_block_lines is not None:
                    current_top_level_block_lines.append(normalized_backticks)
                if len(stack) == 0:
                    block_content = '\n'.join(current_top_level_block_lines)
                    digest = _hashlib.sha256(block_content.encode('UTF-8')).hexdigest()
                    blocks_by_hash[digest] = (block_content, open_fence[2], open_line)
                    if collapse_blocks:
                        result.append(digest)
                    current_top_level_block_lines = None
            if not collapse_blocks:
                result.append(normalized_backticks)
        else:
            if current_top_level_block_lines is not None:
                current_top_level_block_lines.append(line)
            if len(stack) == 0 or not collapse_blocks:
                result.append(line)

    if stack:
        unmatched_lines = list(str(block[0]) for block in stack)
        unmatched_lines = ('line ' if len(unmatched_lines) == 1 else 'lines ') + ', '.join(unmatched_lines)
        raise ParseError(f"Unbalanced fenced block detected. No matching closing backticks for fenced block "
                         f"stating at line {unmatched_lines}.")
    return '\n'.join(result), blocks_by_hash
