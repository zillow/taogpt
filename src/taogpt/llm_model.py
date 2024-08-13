from __future__ import annotations

import json
import typing as _t
import time as _time
import math as _math
import re as _re
import logging as _logging

import openai
import tiktoken as _tiktoken
from langchain_openai import ChatOpenAI as _ChatOpenAI
# subclassing ChatOpenAI, see https://github.com/langchain-ai/langchain/discussions/18561
from langchain_core.language_models.base import LanguageModelInput, BaseMessage
from langchain.schema.messages import ChatMessage, SystemMessage
from langchain_core.runnables.config import ensure_config
from langchain_core.runnables import RunnableConfig
from langchain_core.outputs import ChatGeneration

import taogpt
from taogpt import md_logging
from .constants import ROLE_USER, ROLE_ORCHESTRATOR, ROLE_TAO, ROLE_SYSTEM, ROLE_SAGE, ROLE_GENIE
import taogpt.utils as _utils
from . import LLM
from taogpt.parsing import check_and_fix_fenced_blocks, annotate_fenced_block_backtick_quotes, fix_nested_markdown_blocks_by_report
from taogpt import exceptions as _exceptions

_dev_logger = _logging.getLogger(__file__)
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
                 logger: md_logging.MarkdownLogger,
                 *,
                 max_token_usage: int,
                 approx_token_factor: float=None,
                 long_context_token_threshold: int=None,
                 long_context_llm: _ChatOpenAI=None,
                 long_context_llm_token_factor: float=2.0):
        super().__init__(max_token_usage=max_token_usage)
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
            temperature: float|None=None) -> str:
        old_temp = self.llm.temperature
        try:
            return self._ask(system_prompt, conversation,
                             reason=reason, step_id=step_id,
                             log_request=log_request, temperature=temperature)
        finally:
            if temperature is not None:
                self.llm.temperature = old_temp

    def _ask(self,  system_prompt: str|None, conversation: _t.List[_t.Tuple[str, str]],
            reason=None, step_id = None, log_request = True,
            temperature: float|None=None) -> str:
        if log_request:
            self._logger.start_conversation_chain(f"# SEND TO LLM for {reason}/{step_id}")

        if temperature is not None:
            self.llm.temperature = temperature
        messages: list[BaseMessage] = []
        context_tokens = 0

        if system_prompt is not None and len(system_prompt) > 0:
            tokens = self.count_tokens(system_prompt)
            context_tokens += tokens
            content_to_be_logged = self.deduplicate_for_logging(system_prompt, ROLE_SYSTEM)
            if log_request:
                self._logger.new_message_section(ROLE_SYSTEM, -1, tokens=tokens)
                self._logger.log(content_to_be_logged, demote_h1=True, role=ROLE_SYSTEM)
                self._logger.close_message_section()
            messages.append(SystemMessage(content=system_prompt))

        for i, (role, message) in enumerate(conversation):
            message = _utils.str_or_blank(message)
            if message == '':
                continue
            effective_role = LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[role]
            tokens = self.count_tokens(message)
            context_tokens += tokens
            deduped_msg = self.deduplicate_for_logging(message, role=role)
            deduped_tokens = self.count_tokens(deduped_msg)
            if log_request:
                self._logger.new_message_section(role, i, tokens=tokens, collapsible=deduped_tokens > 32)
                self._logger.log(deduped_msg, demote_h1=True, role=role)
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
            self._logger.log("\n<span></span>\n\n") # to make browser scrolling smoother
            reply_content, context_tokens = self.invoke_llm(llm, messages, return_context_token_usages=True)
            # if the whole reply is just a Markdown, then extract the markdown content
            g = _re.match(r"^```+markdown\n(.*)```+$", reply_content, flags=_re.MULTILINE|_re.DOTALL)
            if g is not None:
                reply_content = g.group(1)
            reply_content_logged = reply_content
            is_json = ''
            try:
                payload = json.loads(reply_content_logged)
                reply_content_logged = json.dumps(payload, indent=2)
                reply_content_logged = f"```json\n{reply_content_logged}\n```\n"
                reply_content = reply_content_logged
            except json.JSONDecodeError:
                pass
            reply_tokens = self.count_tokens(reply_content)
            token_count = context_tokens + reply_tokens
            eff_tokens = f" (eff. tokens: {token_count * token_factor})" if token_factor != 1.0 else ''
            self._total_tokens += token_count

            if log_request:
                self._logger.new_message_section(role='reply', step_index=None, tokens=reply_tokens)
                self._logger.log(reply_content_logged, demote_h1=True)
                self._logger.log(f"temperature={temperature}. context tokens: {context_tokens}, "
                                 f"subtotal: {token_count}{eff_tokens}. cumulative total: {self.total_tokens}\n")
                self._logger.close_message_section()
            return reply_content
        except openai.InternalServerError as e:
            if is_chatgpt_timeout(e):
                _time.sleep(5)
                raise _exceptions.ThisMaybeTooHardError("time-out")
            raise
        except Exception as e:
            raise e

    def invoke_llm(self, llm: _ChatOpenAI, messages: list[BaseMessage],
                   max_tokens: int|None=None, return_context_token_usages=False, fenced_block_fixes=0):
        context_tokens = 0
        for msg in messages:
            role = LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[ROLE_SYSTEM] # just in case we can't tell the role
            if isinstance(msg, ChatMessage):
                role = msg.role
            context_tokens += self.count_tokens(role)
            context_tokens += self.count_tokens(msg.content)
        total_context_tokens = context_tokens
        if isinstance(llm, ChatOpenAIWithGenInfo):
            if max_tokens is None:
                max_tokens = GPT_OUTPUT_TOKEN_LIMITS.get(self.model_id, None)
                if max_tokens is not None and max_tokens < 0:
                    max_tokens = None # let it reach the remaining allowance
                assert max_tokens is None or max_tokens > 0, f"No more output tokens allowed: {max_tokens}"

            to_be_sent = messages.copy()
            reply_content = ''
            while True:
                # will fail when reaching max
                if self._total_tokens >= self.max_token_usage:
                    raise taogpt.Pause(f"Cumulative token usage is {self._total_tokens}, "
                                f"exceeding max limit {self.max_token_usage}", cause=None)
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
                total_context_tokens += (context_tokens + self.count_tokens(reply_content)
                                         + self.count_tokens(CONTINUATION_PROMPT))
        else:
            reply = llm.invoke(messages, max_tokens=max_tokens)
            reply_content = reply.content
        reply_content = fix_nested_markdown_backticks(llm, reply_content)
        _old = reply_content
        reply_content = _utils.str_or_blank(reply_content)
        return (reply_content, total_context_tokens) if return_context_token_usages else reply_content

    def count_tokens(self, text: str) -> int:
        text = _utils.str_or_blank(text)
        if self._approx_token_factor is not None:
            return int(_math.ceil(len(text) * self._approx_token_factor))
        if _utils.safe_is_instance(self.llm, _ChatOpenAI):
            try:
                enc = _tiktoken.encoding_for_model(self.llm.model_name)
            except KeyError:
                enc = _tiktoken.encoding_for_model('gpt-4')
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


_debug_content = None
_debug_reply = None


def fix_nested_markdown_backticks(llm: ChatOpenAIWithGenInfo, original_content: str):
    try:
        fixed, _ = check_and_fix_fenced_blocks(original_content)
        return fixed
    except _exceptions.ParseError as e:
        pass

    content = annotate_fenced_block_backtick_quotes(original_content)

    task = """
A Markdown content generator fails to understand the backtick rules on nested fenced block and produce corrupted 
fenced blocks. In the following content snippet, I annotate each open and close backtick quote with `BACKTICK<n>` 
markers:

---
{content}
---
I want to identify the matching backticks as well as the level of the block enclosed. Respond using the following JSON 
format:

```json
[
    {{"open": "BACKTICK<n1>", "close": "BACKTICK<n2>", level: 1}}, // topmost level is 1
    {{"open": "BACKTICK<n3>", "close": "BACKTICK<n4>", level: 3}},
    {{"open": "BACKTICK<n5>", "close": null}} // no match
]
```
""".format(content=content)

    n_retries, ex = 0, None
    task_to_be_sent = task
    while n_retries < 3:
        try:
            invoke_with_gen_info = llm.invoke_with_gen_info(task_to_be_sent, temperature=0.)
            reply = invoke_with_gen_info.message.content
            json_match = _re.match(r".*`{3,}json\n([^`]+)`{3,}", reply, flags=_re.DOTALL|_re.MULTILINE)
            if json_match is None:
                return original_content
            report = json.loads(json_match.group(1))
            return fix_nested_markdown_blocks_by_report(content, report)
        except json.JSONDecodeError as ex:
            n_retries += 1
            task_to_be_sent = task + f"\n\nParse error: {ex}\nPlease fix the error and repeat the full correct answer"
    if ex is not None:
        raise ex


GPT_MODEL_ALIAS = {
    'gpt-3.5': 'gpt-3.5-turbo',
    'gpt-4-turbo': 'gpt-4-turbo-2024-04-09'
}
GPT_LONG_CONTEXT_MODEL_MAP = {
    'gpt-3.5-turbo': 'gpt-3.5-turbo-16k',
    'gpt-4': 'gpt-4-32k',
    # no need to specify for the gpt-4-turbo or gpt-4o
}
GPT_OUTPUT_TOKEN_LIMITS = {
    # negative number means the max token limit is `abs(limit) - n_context_tokens`
    'gpt-3.5-turbo': 4096,
    'gpt-4': -8192, # tested experimentally
    'gpt-4-32k': -32 * 1024,
    'gpt-4-1106-preview': 4096,
    'gpt-4-turbo-2024-04-09': 4096,
    'gpt-4o': 4096,
}

CONTINUATION_PROMPT = ("You reached output token limit in the last reply. "
                       "Please complete the response starting exactly where you dropped off. "
                       "Do not prepend any preambles in your new reply. "
                       "My code will concatenate your previous outputs with your new outputs in one string 'as is'. "
                       "If the last output is indeed completed, then respond empty message only to inform my program")

CORRUPTED_RESPONSE_MARKER = "Corrupted fenced block is found in your response above:"


def is_chatgpt_timeout(exception: Exception):
    return '504 Gateway Time-out'.lower() in str(exception).lower()
