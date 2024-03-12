from __future__ import annotations

import json
import typing as _t
import time as _time
import math as _math
import tiktoken as _tiktoken
from langchain_openai import ChatOpenAI as _ChatOpenAI
# subclassing ChatOpenAI, see https://github.com/langchain-ai/langchain/discussions/18561
from langchain_core.language_models.base import LanguageModelInput, BaseMessage
from langchain.schema.messages import ChatMessage, SystemMessage
from langchain_core.runnables.config import ensure_config
from langchain_core.runnables import RunnableConfig
from langchain_core.outputs import ChatGeneration

import taogpt.md_logging
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


class ChatOpenAIWithGenInfo(_ChatOpenAI):
    def invoke_with_gen_info(
            self,
            input: LanguageModelInput,
            config: _t.Optional[RunnableConfig] = None,
            *,
            stop: _t.Optional[_t.List[str]] = None,
            **kwargs: _t.Any,
    ) -> ChatGeneration:
        config = ensure_config(config)
        return _t.cast(
            ChatGeneration,
            self.generate_prompt(
                [self._convert_input(input)],
                stop=stop,
                callbacks=config.get("callbacks"),
                tags=config.get("tags"),
                metadata=config.get("metadata"),
                run_name=config.get("run_name"),
                **kwargs,
            ).generations[0][0],
        )


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
                 logger: taogpt.logging.MarkdownLogger,
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
        super().reset()
        self._total_tokens = 0

    def __delete__(self, instance):
        self._logger = None

    @property
    def total_tokens(self):
        return self._total_tokens

    def ask(self,  system_prompt: str|None, conversation: _t.List[_t.Tuple[str, str]],
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

    def _ask(self,  system_prompt: str|None, conversation: _t.List[_t.Tuple[str, str]],
            reason=None, step_id = None, log_request = True,
            temperature: float|None=None,
            collapse_contents: _t.Dict[str, str]=None) -> str:
        self._logger.start_conversation_chain(f"# SEND TO LLM for {reason}/{step_id}")

        if temperature is not None:
            self.llm.temperature = temperature
        messages: list[BaseMessage] = []
        context_tokens = 0

        if system_prompt is not None and len(system_prompt) > 0:
            tokens = self.count_tokens(system_prompt)
            context_tokens += tokens
            self._logger.new_message_section(ROLE_SYSTEM, -1, tokens=tokens)
            content_to_be_logged = self.deduplicate_for_logging(system_prompt, ROLE_SYSTEM)
            self._logger.log(content_to_be_logged, demote_h1=True, role=ROLE_SYSTEM)
            self._logger.close_message_section()
            messages.append(SystemMessage(content=system_prompt))

        for i, (role, message) in enumerate(conversation):
            if message == '':
                continue
            effective_role = LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[role]
            tokens = self.count_tokens(message)
            context_tokens += tokens
            self._logger.new_message_section(role, i, tokens=tokens)
            if tokens > 500:
                deduped_msg = self.deduplicate_for_logging(message, role=role)
                self._logger.log(deduped_msg, demote_h1=True, role=role)
            else:
                self._logger.log(message, demote_h1=True, role=role)
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
            reply_content = self.invoke_llm(llm, messages)
            reply_content_logged = reply_content
            is_json = ''
            try:
                payload = json.loads(reply_content_logged)
                reply_content_logged = json.dumps(payload, indent=2)
                reply_content_logged = f"```json\n{reply_content_logged}\n```\n"
                is_json = 'JSON '
            except json.JSONDecodeError:
                pass
            reply_tokens = self.count_tokens(reply_content)
            token_count = context_tokens + reply_tokens
            self._logger.log(f"{is_json}Reply: temperature={temperature}n")
            self._logger.log(reply_content_logged, demote_h1=True)

            eff_tokens = f" (eff. tokens: {token_count * token_factor})" if token_factor != 1.0 else ''
            self._logger.log(f"{context_tokens} context tokens, {reply_tokens} reply tokens. "
                             f" **Total tokens**: {token_count}{eff_tokens}\n", role='debug')
            self._total_tokens += token_count
            return reply_content
        except Exception as e:
            print(e)
            _time.sleep(3)
            raise e
        finally:
            if collapse_contents is not None:
                self.merge_collapsed_contents(collapse_contents)

    def invoke_llm(self, llm: _ChatOpenAI, messages: list[BaseMessage],
                   max_tokens: int|None=None):
        if isinstance(llm, ChatOpenAIWithGenInfo):
            to_be_sent = messages.copy()
            reply_content = ''
            while True:
                # will fail when reaching max
                reply_with_gi = llm.invoke_with_gen_info(to_be_sent, max_tokens=max_tokens)
                this_content = reply_with_gi.message.content
                reply_content += this_content
                if reply_with_gi.generation_info.get('finish_reason', '') != 'length':
                    break
                to_be_sent = messages.copy()
                to_be_sent.append(ChatMessage(
                    role=LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[ROLE_TAO], content=reply_content))

                to_be_sent.append(ChatMessage(
                    role=LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[ROLE_SYSTEM], content=CONTINUATION_PROMPT))
        else:
            reply = llm.invoke(messages, max_tokens=max_tokens)
            reply_content = reply.content
        return reply_content

    def count_tokens(self, text: str) -> int:
        text = _utils.str_or_blank(text)
        if self._approx_token_factor is not None:
            return int(_math.ceil(len(text) * self._approx_token_factor))
        if _utils.safe_is_instance(self.llm, _ChatOpenAI):
            enc = _tiktoken.encoding_for_model(self.llm.model_name)
        else:
            enc = _tiktoken.encoding_for_model('gpt-4')
        tokens = enc.encode(text)
        return len(tokens)


def fix_model_name(model_name: str, required=False, default_to: str=None):
    if model_name is None:
        assert not required or default_to is not None
        return default_to
    return GPT_MODEL_ALIAS.get(model_name, model_name)


def get_long_model(model_name: str):
    return GPT_LONG_CONTEXT_MODEL_MAP.get(model_name, model_name)


GPT_MODEL_ALIAS = {
    'gpt-3.5': 'gpt-3.5-turbo',
    'gpt-4-turbo': 'gpt-4-1106-preview'
}
GPT_LONG_CONTEXT_MODEL_MAP = {
    'gpt-3.5-turbo': 'gpt-3.5-turbo-16k',
    'gpt-4': 'gpt-4-32k',
    'gpt-4-1106-preview': 'gpt-4-1106-preview',
}
GPT_OUTPUT_TOKEN_LIMITS = {
    # negative number means the max token limit is `abs(limit) - n_context_tokens`
    'gpt-3.5-turbo': 4096,
    'gpt-4': -8192, # tested experimentally
    'gpt-4-32k': -32 * 1024,
    'gpt-4-1106-preview': 4096,
}

CONTINUATION_PROMPT = ("You reached output token limit in the last reply. "
                       "Please complete the response starting exactly where you dropped off. "
                       "Do not prepend any preambles in your new reply. "
                       "My code will concatenate your previous outputs with your new outputs in one string 'as is'. "
                       "If the last output is indeed completed, then respond empty message only to inform my program")
