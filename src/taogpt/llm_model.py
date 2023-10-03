from __future__ import annotations

import json
import typing as _t
import time as _time
import math as _math
import tiktoken as _tiktoken
from langchain.chat_models import ChatOpenAI as _ChatOpenAI
from .constants import ROLE_USER, ROLE_ORCHESTRATOR, ROLE_TAO, ROLE_SYSTEM, ROLE_SAGE, ROLE_GENIE
import taogpt.utils as _utils
from . import LLM

_last_conversation: _t.List|None = None


def get_last_conversation() -> _t.List|None:
    """
    Get the last conversation thread sent (for debugging purposes.) For `LangChainLLM`, the items are the `ChatMessage`
    objects.

    :return: a list of message items
    """
    global _last_conversation
    return _last_conversation


class LangChainLLM(LLM):
    APP_ROLE_TO_OPENAI_ROLE = {
        ROLE_TAO: 'assistant',
        ROLE_ORCHESTRATOR: 'system',
        ROLE_SAGE: 'system',
        ROLE_USER: 'user',
        ROLE_SYSTEM: 'system',
        ROLE_GENIE: 'system',
    }

    def __init__(self, llm: _ChatOpenAI,logger: _utils.MarkdownLogger, approx_token_factor: float=None):
        super().__init__()
        self.llm = llm
        self._logger = logger
        self._approx_token_factor: float | None = approx_token_factor
        self.reset()

    @property
    def model_id(self) -> str:
        return self.llm.model_name

    def reset(self):
        self._total_tokens = 0

    def __delete__(self, instance):
        self._logger = None

    @property
    def total_tokens(self):
        return self._total_tokens

    def ask(self,  system_prompt: str, conversation: _t.List[_t.Tuple[str, str]],
            reason=None, always_shown=False, step_id = None, log_request = True,
            temperature: float|None=None,
            collapse_contents: {str:str}=None) -> str:
        old_temp = self.llm.temperature
        try:
            return self._ask(system_prompt, conversation,
                             reason=reason, step_id=step_id,
                             log_request=log_request, temperature=temperature,
                             collapse_contents=collapse_contents)
        finally:
            if temperature is not None:
                self.llm.temperature = old_temp

    def _ask(self,  system_prompt: str, conversation: _t.List[_t.Tuple[str, str]],
            reason=None, step_id = None, log_request = True,
            temperature: float|None=None,
            collapse_contents: {str:str}=None) -> str:
        self._logger.log(f"# SEND TO LLM for {reason}/{step_id}\n")
        from langchain.schema.messages import ChatMessage, SystemMessage

        if temperature is not None:
            self.llm.temperature = temperature
        collapse_contents = collapse_contents or dict()
        messages: [ChatMessage] = []
        context_len = 0
        context_tokens = 0

        if system_prompt is not None and len(system_prompt) > 0:
            context_len += len(system_prompt)
            context_tokens += self.count_tokens(system_prompt)
            self._logger.new_message_section(ROLE_SYSTEM, -1)
            if log_request and system_prompt not in self.collapsed_contents:
                self._logger.log(system_prompt, demote_h1=True)
                self.collapsed_contents.add(system_prompt)
            else:
                self._logger.log(f"... [text of length {len(system_prompt)}] ...")
            self._logger.close_message_section()
            messages.append(SystemMessage(content=system_prompt))

        for i, (role, message) in enumerate(conversation):
            if message == '':
                continue
            effective_role = LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[role]
            self._logger.new_message_section(role, i)
            self._logger.log(f"**{role} >>> said**:\n")
            if log_request:
                deduped_msg = self.deduplicate_for_logging(message, collapse_contents)
                self._logger.log(deduped_msg, demote_h1=True)
            else:
                self._logger.log(f"... [text of length {len(message)}] ...")
            context_tokens += self.count_tokens(message)
            context_len += len(message)
            self._logger.close_message_section()
            chat_message = ChatMessage(role=effective_role, content=message)
            messages.append(chat_message)
        try:
            global _last_conversation
            _last_conversation = messages.copy()
            reply = self.llm.predict_messages(messages)
            reply_content_logged = reply.content
            is_json = ''
            try:
                payload = json.loads(reply_content_logged)
                reply_content_logged = json.dumps(payload, indent=2)
                reply_content_logged = f"```json\n{reply_content_logged}\n```\n"
                is_json = 'JSON '
            except json.JSONDecodeError:
                pass
            self._logger.log(f"{is_json}Reply: **{type(reply)}** temperature={temperature}\n")
            self._logger.log(reply_content_logged, demote_h1=True)
            reply_len = len(reply.content)
            total_len = context_len + reply_len
            total_tokens_for_this = context_tokens + self.count_tokens(reply.content)

            self._logger.log(f"**Text lengths**: context={context_len} + reply:{reply_len}={total_len}"
                             f" **Total tokens**: {total_tokens_for_this}\n")
            self._total_tokens += total_tokens_for_this
            return reply.content
        except Exception as e:
            print(e)
            _time.sleep(3)
            raise e

    def count_tokens(self, text: str) -> int:
        text = _utils.str_or_blank(text)
        if self._approx_token_factor is not None:
            return int(_math.ceil(len(text) * self._approx_token_factor))
        if isinstance(self.llm, _ChatOpenAI):
            enc = _tiktoken.encoding_for_model(self.llm.model_name)
        else:
            enc = _tiktoken.encoding_for_model('gpt-4')
        tokens = enc.encode(text)
        return len(tokens)
