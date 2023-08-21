from __future__ import annotations
import typing as _t
import time as _time
from langchain.chat_models import ChatOpenAI as _ChatOpenAI
from .constants import ROLE_USER, ROLE_ORCHESTRATOR, ROLE_SOLVER, ROLE_SYSTEM, ROLE_SAGE
import taogpt.utils as _utils


class LLM:

    @property
    def total_tokens(self):
        return 0

    def ask(self, system_prompt: str, conversation: _t.List[_t.Tuple[str, str]], reason=None,
            temperature: float|None=None,
            log_request=True, collapse_contents: {str: str}=None,**_):
        pass

    def reset(self):
        pass


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
        ROLE_SOLVER: 'assistant',
        ROLE_ORCHESTRATOR: 'system',
        ROLE_SAGE: 'system',
        ROLE_USER: 'user',
        ROLE_SYSTEM: 'system',
    }

    def __init__(self, llm: _ChatOpenAI,logger: _utils.MarkdownLogger):
        self.llm = llm
        self._logger = logger
        self.reset()

    def reset(self):
        self._total_tokens = 0
        self.collapsed_contents: {str} = set()

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

        if system_prompt is not None and len(system_prompt) > 0:
            context_len += len(system_prompt)
            self._logger.new_message_section(ROLE_SYSTEM, -1)
            if log_request and system_prompt not in self.collapsed_contents:
                self._logger.log(system_prompt, demote_h1=True)
                self.collapsed_contents.add(system_prompt)
            else:
                self._logger.log(f"... [text of length {len(system_prompt)}] ...")
            self._logger.close_message_section()
            messages.append(SystemMessage(content=system_prompt))

        last_chat_message: ChatMessage | None = None
        for i, (role, message) in enumerate(conversation):
            if message == '':
                continue
            effective_role = LangChainLLM.APP_ROLE_TO_OPENAI_ROLE[role]
            self._logger.new_message_section(role, i)
            self._logger.log(f"**{role} >>> said**:\n")
            if log_request:
                content_to_be_logged: str = message
                for key, collapsible in collapse_contents.items():
                    if collapsible in content_to_be_logged:
                        if collapsible in self.collapsed_contents:
                            content_to_be_logged = content_to_be_logged.replace(
                                collapsible,f"[..{key}:{len(collapsible)}..]")
                        self.collapsed_contents.add(collapsible)
                        break
                self._logger.log(content_to_be_logged, demote_h1=True)
            else:
                self._logger.log(f"... [text of length {len(message)}] ...")
            context_len += len(message)
            self._logger.close_message_section()
            chat_message = ChatMessage(role=effective_role, content=message)
            if last_chat_message is None:
                last_chat_message = chat_message
                messages.append(chat_message)
            elif chat_message.role == last_chat_message.role:
                # last message is already appended, just need to update it
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
            reply_len = len(reply.content)
            total_len = context_len + reply_len
            factor = 4 # estimate according to https://platform.openai.com/tokenizer; will use tiktoken later
            self._logger.log(f"**Text lengths**: context={context_len} + reply:{reply_len}={total_len}"
                             f" **Tokens**: context={context_len//factor} "
                             f"+ reply:{reply_len//factor}={total_len//factor}\n")
            self._total_tokens += total_len // factor
            return reply.content
        except Exception as e:
            print(e)
            _time.sleep(3)
            raise e
