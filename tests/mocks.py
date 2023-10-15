import typing as _t

import pytest
import tiktoken

from taogpt import LLM, MarkdownLogger, PromptDb, Config
from taogpt.orchestrator import Orchestrator
from taogpt.utils import str_or_blank


class MockLLM(LLM):
    def __init__(self,
                 logger: MarkdownLogger,
                 reply_fn: _t.Callable[[(str, str), str, str], str]=None):
        super().__init__()
        self._logger = logger
        self._total_tokens = 0
        self._n_requests = 0
        self.conversation_sequence: [(str, str)] = list()
        self.reply_fn = reply_fn
        self.encoder = tiktoken.encoding_for_model('gpt-4')

    @property
    def model_id(self) -> str:
        return 'mock_llm'

    @property
    def total_tokens(self):
        return self._total_tokens

    def ask(self, system_prompt: str, conversation: _t.List[_t.Tuple[str, str]], reason=None,
            temperature: float=None, log_request=True, collapse_contents: {str: str}=None,
            step_id='0', **_) -> str:
        self.collapsed_contents.update(collapse_contents or dict())
        self._logger.log(f"# SEND TO LLM for {reason}/{step_id}\n")
        if len(str_or_blank(system_prompt)) > 0:
            self._total_tokens += self.send('system', system_prompt, -1)
        for i, (role, message) in enumerate(conversation):
            self._total_tokens += self.send(role, message, i)
        self._n_requests += 1
        self.conversation_sequence.append((reason, step_id))
        reply = f"reply#{self._n_requests}"
        if self.reply_fn is not None:
            reply = self.reply_fn(conversation, reason, step_id)
        self._total_tokens += len(self.encoder.encode(reply))
        return reply

    def send(self, role, message, i):
        tokens = len(self.encoder.encode(message))
        self._logger.new_message_section(role, i)
        self._logger.log(f"**{role} >>> said**:\n")
        deduped_msg = self.deduplicate_for_logging(message, role=role)
        self._logger.log(deduped_msg, demote_h1=True)
        self._logger.close_message_section()
        return tokens

    def reset(self):
        self._n_requests = 0
        self._total_tokens = 0
        self.conversation_sequence.clear()


@pytest.fixture
def logger():
    return MarkdownLogger('/tmp/taogpt_test_log.md')


def create_orchestrator(llm: MockLLM, logger: MarkdownLogger, check_final=True):
    return Orchestrator(
        config=Config(check_final=check_final),
        llm=llm,
        markdown_logger=logger,
        prompts=PromptDb.load_defaults()
    )
