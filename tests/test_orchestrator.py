from mocks import MockLLM, create_orchestrator, logger
from taogpt.program import *
from taogpt.parsing import ParseError, parse_final_response

EXAMPLE_STEP_BY_STEP_PLAN = """This is my plan:
```json
{
    "1": {"description": "Do X"},
    "2": {"description": "Do Y"}
}
```
"""

_logger = logger


def test_check_final_solution_success(logger):
    text = """{
    "overall": {"correctness": true, "reason": "All right!"},
    "calculation": {"correctness": true, "reason": "Good math!"}
    }
    """
    overall, concerns = parse_final_response(text)
    assert overall
    assert concerns == "* calculation: Good math!\n* overall: All right!"

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return text

    invocation, llm, orchestrator = create_final_check_chain(reply, logger)
    orchestrator.check_final_solution(invocation)
    assert len(llm.conversation_sequence) == 1
    assert llm.conversation_sequence[-1][0] == 'check_final_solution'


def test_check_final_solution_failed(logger):
    text = """{
    "overall": {"correctness": false, "reason": "The math is wrong."},
    "calculation": {"correctness": false, "reason": "1 + 1 != 3"},
    "etc": {"correctness": true, "reason": "Good"}
    }
    """
    overall, concerns = parse_final_response(text)
    assert not overall
    assert concerns == "* calculation: 1 + 1 != 3\n* etc: Good\n* overall: The math is wrong."

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return text

    invocation, llm, orchestrator = create_final_check_chain(reply, logger)
    try:
        orchestrator.check_final_solution(invocation)
        assert False, "expecting Backtrack not raised"
    except Backtrack:
        pass


def test_check_final_solution_parse_error(logger):
    text = """// missing {
    "overall": {"correctness": true, "reason": "All right!"},
    "calculation": {"correctness": true, "reason": "Good math!"}
    }
    """
    try:
        parse_final_response(text)
        assert False, "expecting ParseError not raised"
    except ParseError:
        pass

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return text

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
    step = DirectAnswerStep(step, "This is an answer", ROLE_TAO)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = FinalAnswerStep(step, "This is the final answer", ROLE_TAO)
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
    step = AskQuestionStep(step, "I have a question", ROLE_TAO)
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
    step = StepByStepPlan(step, EXAMPLE_STEP_BY_STEP_PLAN, ROLE_TAO)
    orchestrator.chain.append(Invocation(step, _executor=orchestrator))
    step = AskQuestionStep(step, "I have a question", ROLE_TAO)
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
    plan_step: StepByStepPlan = StepByStepPlan(expandable, EXAMPLE_STEP_BY_STEP_PLAN, ROLE_TAO)
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
