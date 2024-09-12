from __future__ import annotations

import re as _re

from taogpt import GeneratedFile, StepABC
from taogpt.exceptions import ParseError
from taogpt.parsing import extract_fenced_blocks, restore_fenced_block, parse_sections, FREE_TEXT, \
    check_and_fix_fenced_blocks


def collect_files(text: str) -> dict[str, GeneratedFile]:
    try:
        fenced_blocks, text = extract_fenced_blocks(text)
    except SyntaxError as e:
        raise ParseError(str(e))

    text = _re.sub(r" *#+ *(Consolidated +)?File: *", "_FILE_HEADING", text, flags=_re.IGNORECASE)
    text = _re.sub(r" *#+ *", "", text) # remove remaining `#` headings
    text = _re.sub(r"_FILE_HEADING", "## File: ", text) # remove remaining `#` headings
    text = restore_fenced_block(text, fenced_blocks)

    sections = parse_sections(text)
    results = dict()
    for section_header, content in sections.items():
        if section_header == FREE_TEXT:
            continue
        if 'FILE:' not in section_header.upper():
            continue
        file_path = normalize_path(_re.sub(r'(Consolidated +)?File: *', '', section_header, 1, flags=_re.IGNORECASE))
        content_type, content, _, desc = gather_file_contents(content, file_path=file_path)
        results[file_path] = GeneratedFile(content_type, content, desc)
    return results


def count_file_updates(chain: list[StepABC], stop_at_step: StepABC=None) -> dict[str, int]:
    files = dict()
    for step in chain:
        if stop_at_step is step:
            break
        for path, file in step.collected_files.items():
            if path in files:
                files[path] += 1
            else:
                files[path] = 1
    return files


def gather_file_contents(markdown_full_content: str, file_path:str='') -> tuple[str,str,str,str]|None:
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
        raise ParseError(f"Need exactly one file content fenced block. "
                         f"Found {len(results)} under `File: {file_path}`. "
                         f"Maybe you accidentally put contents belonging to another file here?")
    content_type, content, snippet, desc = results[0]
    return content_type, content, snippet, desc


def normalize_path(string: str) -> str:
    matched = _re.match(r"""[`"' ]*/*(([.a-zA-Z0-9_\-]+/+)*[.a-zA-Z0-9_]+)[`"' ]*$""", string.strip())
    if not matched:
        raise ParseError("Make sure to include file path consisting slash-separated components of only "
                         f"alphanumeric, period, dash, and underscore characters. Found `{string}`. "
                         "Only file path is allowed, not directory path ending with slash.")
    path = matched.group(1)
    return _re.sub(r'/+', '/', path)
