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
    "rule conformance": {"ok": true, "reason": "All right!"},
    "calculation": {"ok": true, "reason": "Good math!"}
    }
    """
    overall, concerns = parse_final_response(text)
    assert overall
    assert concerns == ""

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return text

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    step.eval(orchestrator)
    assert len(llm.conversation_sequence) == 1
    assert llm.conversation_sequence[-1][0] == 'check_final_solution'


def test_check_final_solution_failed(logger):
    text = """{
    "calculation": {"ok": false, "reason": "1 + 1 != 3"},
    "etc": {"ok": true, "reason": "Good"}
    }
    """
    overall, concerns = parse_final_response(text)
    assert not overall
    assert concerns == "* calculation: 1 + 1 != 3"

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        assert reason == 'check_final_solution'
        return text

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    try:
        step.eval(orchestrator)
        assert False, "expecting Backtrack not raised"
    except Backtrack:
        pass


def test_check_final_solution_parse_error(logger):
    text = """// missing {
    "calculation": {"ok": true, "reason": "Good math!"}
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

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    try:
        step.eval(orchestrator)
        assert False, "expecting ParseError not raised"
    except ParseError:
        pass


def create_final_check_chain(reply, logger):
    llm = MockLLM(logger, reply_fn=reply)
    orchestrator = create_orchestrator(llm, logger, check_final=True)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(step)
    step = DirectAnswerStep(step, "This is an answer", ROLE_TAO)
    orchestrator.chain.append(step)
    step = FinalAnswerStep(step, "This is the final answer", ROLE_TAO)
    orchestrator.chain.append(step)
    return step, llm, orchestrator


def test_need_full_expansion_at_first_expandable_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    assert orchestrator.is_first_solving_expansion()


def test_need_full_expansion_at_first_expandable_step_followed_by_ask_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    step = AskQuestionStep(step, "I have a question", ROLE_TAO)
    orchestrator.chain.append(step)
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    assert orchestrator.is_first_solving_expansion()


def test_no_full_expansion_at_subsequent_expandable_steps(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    step = StepByStepPlan(step, EXAMPLE_STEP_BY_STEP_PLAN, ROLE_TAO)
    orchestrator.chain.append(step)
    step = AskQuestionStep(step, "I have a question", ROLE_TAO)
    orchestrator.chain.append(step)
    step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    assert not orchestrator.is_first_solving_expansion()


def test_record_criticism_to_expandable_steps(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(step)
    expandable: ProceedStep = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(expandable)
    plan_step: StepByStepPlan = StepByStepPlan(expandable, EXAMPLE_STEP_BY_STEP_PLAN, ROLE_TAO)
    expandable.choices = []
    expandable.choices.append(plan_step)
    orchestrator.chain.append(plan_step)
    expected = f"""[Prior approach#1] {plan_step.description_with_header}
--
[[This approach has been tried and failed with following error:

* error 1
* error 2

]]
"""
    errors = {'error 1', 'error 2'}
    orchestrator.record_criticisms(errors)
    assert len(expandable.collected_criticisms) == 1
    assert expandable.collected_criticisms[0] == errors


def test_backtracking(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    orchestrator.config.ask_user_before_execute_codes = False
    orchestrator.config.max_search_expansion = 2
    step = PresentTaskStep(None, "This is a problem", ROLE_USER)
    orchestrator.chain.append(step)
    proceed_step = ProceedStep(step, "Proceed to solve", ROLE_ORCHESTRATOR)
    orchestrator.chain.append(proceed_step)

    code = f"""```python
no_such_var * 123
```
    """
    step = AskPythonGenieStep(proceed_step, code, ROLE_TAO)
    orchestrator.chain.append(step)
    proceed_step.choices = [step]
    try:
        orchestrator.resume(1000)
    except ParseError:
        pass
    assert "name 'no_such_var' is not defined" in step.description
    assert 0 == len(proceed_step.collected_criticisms) # cleared


def test_parse_direct_answer_and_next_step():
    text = """# I_WILL_ANSWER_DIRECTLY



To fill in the first row, we need to find the numbers that are not already present. The numbers in the first row are 3 and 1. So, the missing numbers are 2 and 4.

We can't put 2 in the first cell because the number 2 is already present in the first column. So, the first cell must be 4. 

Then, the third cell must be 2 because it's the only number left.

So, the first row becomes: 4 3 2 1

### NEXT_I_WANT_TO_WORK_AT:
Fill in the second row [None]
"""
    step = parse_to_step(None, text)
    assert isinstance(step, DirectAnswerStep)
    assert not step.is_final_step
    assert step.next_step == 'Fill in the second row [None]'


def test_parse_step_by_step_no_whys():
    text = """# HERE_IS_MY_STEP_BY_STEP_PLAN



```json
{
  "1": {"description": "Fill in the first row"},
  "2": {"description": "Fill in the second row"},
  "3": {"description": "Fill in the third row"},
  "4": {"description": "Fill in the fourth row"}
}
```
This plan is based on the rules of Sudoku. Each row, column, and 2x2 square must contain all of the numbers from 1 to 4 exactly once. We will fill in the rows one by one, making sure that each number appears exactly once in each row and column, and in each 2x2 square. This is a recursive, top-down approach to solving the puzzle.
"""
    step = parse_to_step(None, text)
    assert isinstance(step, StepByStepPlan)
    assert step.first_step == 'Fill in the first row'
