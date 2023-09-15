from pathlib import Path
from mocks import MockLLM
from taogpt import MarkdownLogger, Backtrack
from taogpt.constants import ROLE_USER
from taogpt.prompts import PromptDb
from taogpt.orchestrator import Orchestrator, Invocation
from taogpt.program import PresentTaskStep, DirectAnswerStep, FinalAnswerStep
from taogpt.parsing import ParseError


class TestOrchestrator:

    def test_check_final_solution_success(self):
        logger = MarkdownLogger(Path(__file__).parent.parent / 'logs' / 'test_log.md')

        def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
            assert reason == 'check_final_solution'
            return "Yes. It is good."

        invocation, llm, orchestrator = self.create_final_check_chain(reply, logger)
        orchestrator.check_final_solution(invocation)
        assert len(llm.conversation_sequence) == 1
        assert llm.conversation_sequence[-1][0] == 'check_final_solution'

    def test_check_final_solution_failed(self):
        logger = MarkdownLogger(Path(__file__).parent.parent / 'logs' / 'test_log.md')

        def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
            assert reason == 'check_final_solution'
            return "No. It is wrong."

        invocation, llm, orchestrator = self.create_final_check_chain(reply, logger)
        try:
            orchestrator.check_final_solution(invocation)
            assert False, "expecting Backtrack not raised"
        except Backtrack:
            pass


    def test_check_final_solution_parse_error(self):
        logger = MarkdownLogger(Path(__file__).parent.parent / 'logs' / 'test_log.md')

        def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
            assert reason == 'check_final_solution'
            return "I don't know."

        invocation, llm, orchestrator = self.create_final_check_chain(reply, logger)
        try:
            orchestrator.check_final_solution(invocation)
            assert False, "expecting ParseError not raised"
        except ParseError:
            pass

    @staticmethod
    def create_final_check_chain(reply, logger):
        llm = MockLLM(logger, reply_fn=reply)
        orchestrator = Orchestrator(
            llm=llm,
            markdown_logger=logger,
            prompts=PromptDb.load_defaults(),
            check_final=True
        )
        step = PresentTaskStep(None, "This is a problem", ROLE_USER)
        orchestrator.chain.append(Invocation(step, _executor=orchestrator))
        step = DirectAnswerStep(step, "This is an answer", ROLE_USER)
        orchestrator.chain.append(Invocation(step, _executor=orchestrator))
        step = FinalAnswerStep(step, "This is the final answer", ROLE_USER)
        invocation = Invocation(step, _executor=orchestrator)
        orchestrator.chain.append(invocation)
        return invocation, llm, orchestrator
