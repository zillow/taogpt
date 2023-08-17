from __future__ import annotations
import dataclasses as _dc
import pathlib as _path
import typing as _t
import time as _time
from collections import defaultdict as _defaultdict
import langchain as lc
from .constants import ROLE_USER, ROLE_ORCHESTRATOR, ROLE_SOLVER, ROLE_SYSTEM, ROLE_SAGE
import taogpt.utils as _utils
import taogpt._dummies as _d


class LLM:

    def ask(self, system_prompt: str, conversation: _t.List[_t.Tuple[str, str]], reason=None, log_request=True, **_):
        pass

    def reset(self):
        pass


class DummyLLM(LLM):
    def __init__(self, n_log_per_reason=1):
        self.request_counts_by_reason = _defaultdict(lambda: 0)
        self.n_log_per_reason = n_log_per_reason

    def reset(self):
        self.request_counts_by_reason.clear()

    def ask(self,  system_prompt: str, conversation: _t.List[_t.Tuple[str, str]],
            reason=None, log_request=True, always_shown=False, dummy_resp=None, step_id=None) -> str:
        print(f"  == {reason} @ {step_id} ==")
        if reason is not None:
            n_logged_for_reason = self.request_counts_by_reason[reason]
            self.request_counts_by_reason[reason] += 1
        else:
            n_logged_for_reason = 0
        if dummy_resp is None:
            dummy_resp = _d.get_dummy(reason, n_logged_for_reason)
        if dummy_resp is not None and '{step_id}' in dummy_resp:
            dummy_resp = dummy_resp.format(step_id=step_id)
        if n_logged_for_reason >= self.n_log_per_reason and not always_shown:
            return dummy_resp
        print(f"system>", system_prompt)
        for role, text in conversation:
            text = _utils.str_or_blank(text)
            if text == '':
                continue
            print(f"{role}> {text}\n\n")
        return dummy_resp


_last_conversation: _t.List|None = None


def get_last_conversation():
    global _last_conversation
    return _last_conversation


class LangChainLLM(LLM):
    APP_ROLE_TO_OPENAI_ROLE = {
        ROLE_SOLVER: 'assistant',
        ROLE_ORCHESTRATOR: 'system',
        ROLE_SAGE: 'system',
        ROLE_USER: 'user',
        ROLE_SYSTEM: 'system',
    }

    def __init__(self, llm: lc.llms.openai.OpenAIChat,logger: _utils.MarkdownLogger):
        self.llm = llm
        self._logger = logger

    def reset(self):
        pass

    def __delete__(self, instance):
        self._logger = None

    def ask(self,  system_prompt: str, conversation: _t.List[_t.Tuple[str, str]],
            reason=None, always_shown=False, step_id=None, log_request=True) -> str:
        self._logger.log(f"# SEND TO LLM for {reason}/{step_id}\n")
        from langchain.schema.messages import ChatMessage, SystemMessage

        self._logger.new_message_section(ROLE_SYSTEM, -1)
        if log_request:
            self._logger.log(system_prompt, demote_h1=True)
        else:
            self._logger.log(f"... [text of length {len(system_prompt)}] ...")
        self._logger.close_message_section()
        messages = [
            SystemMessage(content=system_prompt),
        ]

        last_chat_message: ChatMessage | None = None
        for i, (role, message) in enumerate(conversation):
            if message == '':
                continue
            effective_role = LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[role]
            self._logger.new_message_section(role, i)
            self._logger.log(f"**{role} >>> said**:\n")
            if log_request:
                self._logger.log(message, demote_h1=True)
            else:
                self._logger.log(f"... [text of length {len(message)}] ...")
            self._logger.close_message_section()
            chat_message = ChatMessage(role=effective_role, content=message)
            if last_chat_message is None:
                last_chat_message = chat_message
                messages.append(chat_message)
            elif chat_message.role == last_chat_message.role:
                # last message is already appended, just nedd to update it
                last_content = last_chat_message.content.strip() # ensure no trailing newlines
                last_chat_message.content = last_content + '\n\n' + chat_message.content # then add newlines
            else:
                messages.append(chat_message)
        try:
            global _last_conversation
            _last_conversation = messages
            reply = self.llm.predict_messages(messages)
            self._logger.log(f"Reply: **{type(reply)}**\n")
            self._logger.log(reply.content, demote_h1=True)
            return reply.content
        except Exception as e:
            print(e)
            _time.sleep(3)
            raise e


@_dc.dataclass
class PromptSet:
    system_step_expansion: str # main system prompt
    tao_templates: str
    tao_templates_examples: str
    orchestrator_ask_init_analysis: str
    orchestrator_eval_strategy_choices: str
    orchestrator_next_step: str
    orchestrator_proceed: str
    orchestrator_proceed2: str
    orchestrator_expand_parse_error: str
    orchestrator_next_step_parse_error: str
    orchestrator_critics: str
    sage: str
    sage_check_dead_end: str
    sage_final_check: str

    @staticmethod
    def load_defaults():
        path = _path.Path(__file__).parent / 'prompts'

        def _read(path):
            with open(path, 'r') as f:
                return f.read()

        return PromptSet(
            system_step_expansion=_read(path / 'tao.md'),
            tao_templates=_read(path / 'tao_templates.md'),
            tao_templates_examples=_read(path / 'tao_templates_examples.md'),
            orchestrator_ask_init_analysis=_read(path / 'orchestrator_ask_init_analysis.md'),
            orchestrator_eval_strategy_choices=_read(path / 'rank_choices.md'),
            orchestrator_next_step=_read(path / 'next_step.md'),
            orchestrator_proceed=_read(path / 'proceed.md'),
            orchestrator_proceed2=_read(path / 'proceed2.md'),
            orchestrator_expand_parse_error=_read(path / 'orchestrator_expand_parse_error.md'),
            orchestrator_next_step_parse_error=_read(path / 'orchestrator_next_step_parse_error.md'),
            orchestrator_critics=_read(path / 'orchestrator_critics.md'),
            sage=_read(path / 'sage.md'),
            sage_check_dead_end=_read(path / 'sage_dead_end_detect.md'),
            sage_final_check=_read(path / 'sage_final_check.md'),
        )
