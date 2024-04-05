from __future__ import annotations

import re as _re
from pathlib import Path as _Path
from io import TextIOBase as _TextIOBase

from taogpt.constants import role_color_map, ROLE_ORCHESTRATOR
from taogpt.parsing import extract_fenced_blocks, restore_fenced_block
from taogpt import utils as _utils

_fix_fenced_block_backticks_re = _re.compile(r"(`{3,})(\d+)")


class MarkdownLogger:
    H1_RE = _re.compile(r"^# +(.+)")

    def __init__(self, log_path: str|_Path, log_debug=False,
                 console_out: _TextIOBase=None,
                 limit_console_for_roles=None):
        if limit_console_for_roles is None:
            limit_console_for_roles = {ROLE_ORCHESTRATOR, 'debug'}
        self._log_path = _Path(log_path)
        self._log_path.parent.mkdir(exist_ok=True)
        self._log = open(self._log_path, 'w')
        self._log_debug = log_debug
        self._console_out = console_out
        self._limit_console_for_roles = limit_console_for_roles

    def close(self):
        if self._log is not None:
            self._log.close()
            self._log = None

    def __delete__(self, instance):
        if instance._log is not None:
            instance._log.close()

    def start_conversation_chain(self, heading: str):
        if not heading.startswith('# '):
            heading = f"# {heading}"
        self._log.write('\n\n')
        self._log.write(heading)
        self._log.write('\n')
        if self._console_out is not None:
            print(f"========== {heading.strip()} ==========", file=self._console_out)

    def log(self, *msgs, demote_h1=False, role: str=None):
        try:
            msg = ''
            for msg in msgs:
                if demote_h1:
                    msg = MarkdownLogger.demote_h1(msg)
                msg = _fix_fenced_block_backticks_re.sub(r"\1", msg)
                self._log.write(msg)
                if self._console_out is not None:
                    print(_utils.safe_subn(msg, n=200, escape_new_line=False)
                          if role in self._limit_console_for_roles else msg, file=self._console_out)
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
            matches: _re.Match = MarkdownLogger.H1_RE.match(line)
            lines[i] = f"***{matches.group(1)}***\n\n" if matches is not None else line
        result = '\n'.join(lines)
        return restore_fenced_block(result, fenced_blocks)

    def log_conversation(self, conversation: list[tuple[str, str]], skip_system_message=1, title='Final path history'):
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


    def log_debug(self, markup):
        if not self._log_debug:
            return
        orig_log_to_stdout = self._console_out
        try:
            self.new_message_section('debug', 'DEBUG')
            self.log(markup, demote_h1=False, role='debug')
            self.close_message_section()
        finally:
            self._console_out = orig_log_to_stdout

    def new_message_section(self, role, step_index, tokens: int=None):
        tokens = f"(tokens: {tokens})" if tokens is not None else ""
        color = role_color_map.get(role, 'white')
        if role == 'debug':
            color = 'aliceblue'
        self._log.write(f'<div style="background-color:{color}; padding: 5px; border-bottom: 1px dotted grey">\n'
                 f'<div>[{step_index}] <b>{role}</b>: {tokens}</div>\n\n')
        if self._console_out is not None:
            print(f"--- [{step_index:03d}] {role.strip()} ---", file=self._console_out)

    def close_message_section(self):
        self._log.write('\n</div>\n\n')
        if self._console_out is not None:
            self._console_out.write('\n')
            self._console_out.flush()
