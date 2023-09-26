from mocks import MockLLM, create_orchestrator, logger
from taogpt.program import *
from taogpt.parsing import ParseError

_logger = logger


def test_check_final_solution_success(logger):
    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return "Yes. It is good."

    invocation, llm, orchestrator = create_final_check_chain(reply, logger)
    orchestrator.check_final_solution(invocation)
    assert len(llm.conversation_sequence) == 1
    assert llm.conversation_sequence[-1][0] == 'check_final_solution'


def test_check_final_solution_failed(logger):
    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return "No. It is wrong."

    invocation, llm, orchestrator = create_final_check_chain(reply, logger)
    try:
        orchestrator.check_final_solution(invocation)
        assert False, "expecting Backtrack not raised"
    except Backtrack:
        pass


def test_check_final_solution_parse_error(logger):
    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return "I don't know."

    invocation, llm, orchestrator = create_final_check_chain(reply, logger)
    try:
        orchestrator.check_final_solution(invocation)
        assert False, "expecting ParseError not raised"
    except ParseError:
        pass


def create_final_check_chain(reply, logger):
    llm = MockLLM(logger, reply_fn=reply)
    orchestrator = create_orchestrator(llm, logger, check_final=True)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = DirectAnswerStep(step, "This is an answer", ROLE_SOLVER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = FinalAnswerStep(step, "This is the final answer", ROLE_SOLVER)
    invocation = Invocation(step, _executor=orchestrator)
    orchestrator.chain.append(invocation)
    return invocation, llm, orchestrator


def test_need_full_expansion_at_first_expandable_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    assert orchestrator.need_search_expansion_at_next_step()


def test_need_full_expansion_at_first_expandable_step_followed_by_ask_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = AskQuestionStep(step, "I have a question", ROLE_SOLVER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = UserReplyStep(step, "This is your answer", ROLE_USER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    assert orchestrator.need_search_expansion_at_next_step()


def test_no_full_expansion_at_subsequent_expandable_steps(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = PlanStep(step, "This is my plan:\n1. Do X\n2. Do Y", ROLE_SOLVER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = AskQuestionStep(step, "I have a question", ROLE_SOLVER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = UserReplyStep(step, "This is your answer", ROLE_USER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    assert not orchestrator.need_search_expansion_at_next_step()


def test_record_criticism_to_expandable_steps(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    expandable: ProceedStep = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(Invocation(expandable, _executor=orchestrator))
    plan_step: PlanStep = PlanStep(expandable, "This is my plan:\n1. Do X\n2. Do Y", ROLE_SOLVER)
    expandable.choices = []
    expandable.choices.append(plan_step)
    orchestrator.chain.append(Invocation(plan_step, _executor=orchestrator))
    errors = {'error 1', 'error 2'}
    orchestrator.record_criticisms(errors)
    assert len(expandable.collected_criticisms) == 1
    assert expandable.collected_criticisms[0] == errors
    expected = f"""[Prior approach 1] {plan_step.description}

criticism:
* error 1
* error 2"""
    gathered = expandable.gather_choices_with_criticisms()
    assert len(gathered) == 1
    gathered[0] = gathered[0].replace("* error 2\n* error 1", "* error 1\n* error 2")
    assert gathered[0] == expected
