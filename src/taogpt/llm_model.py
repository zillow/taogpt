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

    def __init__(self,
                 llm: _ChatOpenAI,
                 logger: _utils.MarkdownLogger,
                 approx_token_factor: float=None,
                 long_context_token_threshold: int=None,
                 long_context_llm: _ChatOpenAI=None,
                 long_context_llm_token_factor: float=2.0):
        super().__init__()
        self._total_tokens = 0
        self.llm = llm
        self._logger = logger
        self._approx_token_factor: float | None = approx_token_factor
        if long_context_llm is not None:
            assert long_context_token_threshold is not None and long_context_token_threshold > 0, \
                "If long-context LLM is given, token threshold must be > 0"
            assert long_context_llm_token_factor is not None and long_context_llm_token_factor > 1.0, \
                "If long-context LLM is given, token factor must be > 1.0"
        self.long_context_token_threshold = long_context_token_threshold
        self.long_context_llm = long_context_llm
        self.long_context_llm_token_factor = long_context_llm_token_factor
        self.reset()

    @property
    def model_id(self) -> str:
        return self.llm.model_name

    def __repr__(self) -> str:
        if self.long_context_llm is not None:
            long_ctx = f" ({self.long_context_llm.model_name}@len(ctx)>{self.long_context_token_threshold})"
        else:
            long_ctx = ''
        return f"{self.model_id}{long_ctx}"

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
            if system_prompt not in self.collapsed_contents:
                self._logger.log(system_prompt, demote_h1=True)
                self.collapsed_contents.add(system_prompt)
            else:
                self._logger.log(f"... system_prompt [text of length {len(system_prompt)}] ...")
            self._logger.close_message_section()
            messages.append(SystemMessage(content=system_prompt))

        for i, (role, message) in enumerate(conversation):
            if message == '':
                continue
            effective_role = LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[role]
            self._logger.new_message_section(role, i)
            if len(message) > 500:
                deduped_msg = self.deduplicate_for_logging(message, collapse_contents)
                self._logger.log(deduped_msg, demote_h1=True)
            else:
                self._logger.log(message, demote_h1=True)
            context_tokens += self.count_tokens(message)
            context_len += len(message)
            self._logger.close_message_section()
            chat_message = ChatMessage(role=effective_role, content=message)
            messages.append(chat_message)
        try:
            global _last_conversation
            _last_conversation = messages.copy()
            llm = self.llm
            token_factor = 1.0
            if self.long_context_llm is not None and context_tokens > self.long_context_token_threshold:
                llm = self.long_context_llm
                token_factor = self.long_context_llm_token_factor
            reply = llm.predict_messages(messages)
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
            token_count = context_tokens + self.count_tokens(reply.content)

            eff_tokens = f" (eff. tokens: {token_count * token_factor})" if token_factor != 1.0 else ''
            self._logger.log(f"**Text lengths**: context={context_len} + reply:{reply_len}={total_len}"
                             f" **Total tokens**: {token_count}{eff_tokens}\n")
            self._total_tokens += token_count
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
