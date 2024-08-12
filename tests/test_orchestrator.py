from mocks import MockLLM, create_orchestrator, logger
import typing as _t
from taogpt.program import *
from taogpt.parsing import parse_verification_response
from taogpt.exceptions import ParseError

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
"rule conformance": {"ok": "All right!"},
"calculation": {
        "warning": "Can simplify", 
        "blame": ["step#1: calculate total", "step#2: summarize"],
        "affecting": ["step#2: summarize"]
    }
}
    """
    concerns, _ = parse_verification_response(text)
    assert len(concerns) == 1
    assert concerns == {"Can simplify": ("warning", [(1, "calculate total"), (2, "summarize")])}

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        if reason in ('verify', 'merge_criticisms'):
            return text
        elif reason == 'SummarizeStep':
            return "Here is your answer"

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    orchestrator.config.verification_votes = 2
    orchestrator.config.max_repairs = 0
    step.eval(orchestrator)
    assert len(llm.conversation_sequence) == 4
    assert llm.conversation_sequence[0][0] == 'verify'
    assert llm.conversation_sequence[1][0] == 'verify'
    assert llm.conversation_sequence[2][0] == 'merge_criticisms'
    assert llm.conversation_sequence[3][0] == 'SummarizeStep'


def test_check_final_solution_failed(logger):
    text = """{
    "calculation": {"error": "1 + 1 != 3", "blame": "step#1: calculate total", "affecting": ["step#2: goofy step"]},
    "etc": {"ok": "Good"}
}
    """
    concerns, full_json = parse_verification_response(text)
    assert concerns == {
        "1 + 1 != 3": ("error", [(1, "calculate total")]),
        "prior step#1 has been changed due to 1 + 1 != 3": ("affected", [(2, "goofy step")])
    }
    assert json.loads(text).keys() == full_json.keys()

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        if reason == 'SummarizeStep':
            return "3"
        if reason in ('verify', 'merge_criticisms'):
            return text
        assert False, f"Unexpected reason: {reason}"

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    _t.cast(DirectAnswerStep, orchestrator.previous_step(step))._n_tries = orchestrator.config.max_repairs
    step._reset_chain_retry_count = True
    try:
        step.eval(orchestrator)
        assert False, "expecting Backtrack not raised"
    except Backtrack:
        pass


def test_check_final_solution_parse_error(logger):
    text = """// missing {
    "calculation": {"huh": "I don't know!"}
    }
    """
    try:
        parse_verification_response(text)
        assert False, "expecting ParseError not raised"
    except ParseError:
        pass

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        if reason == 'verify':
            return text
        return 'huh'

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    try:
        step.eval(orchestrator)
        assert False, "expecting ParseError not raised"
    except ParseError:
        pass


def create_final_check_chain(reply, logger):
    llm = MockLLM(logger, reply_fn=reply)
    orchestrator = create_orchestrator(llm, logger, check_final=True)
    step = PresentTaskStep(description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = DirectAnswerStep(description="This is an answer", role=ROLE_TAO, step_name='calculate total')
    orchestrator.chain.append(step)
    step = SummarizeStep()
    orchestrator.chain.append(step)
    return step, llm, orchestrator


def test_need_full_expansion_at_first_expandable_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(description="Proceed to solve", role=ROLE_ORCHESTRATOR, step_name='start')
    orchestrator.chain.append(step)
    assert orchestrator.is_init_solving_expansion()


def test_need_full_expansion_at_first_expandable_step_followed_by_ask_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(description="Proceed to solve", role=ROLE_ORCHESTRATOR, step_name='start')
    orchestrator.chain.append(step)
    step = AskQuestionStep(description="1. How are you?", role=ROLE_TAO, step_name='ask')
    orchestrator.chain.append(step)
    step = ProceedStep(description="Proceed to solve", role=ROLE_ORCHESTRATOR, step_name='next step')
    orchestrator.chain.append(step)
    assert orchestrator.is_init_solving_expansion()


def test_no_full_expansion_at_subsequent_expandable_steps(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(description="Proceed to solve", role=ROLE_ORCHESTRATOR, step_name='start')
    orchestrator.chain.append(step)
    step = StepByStepPlan(description=EXAMPLE_STEP_BY_STEP_PLAN, role=ROLE_TAO, step_name='plan')
    orchestrator.chain.append(step)
    step = AskQuestionStep(description="1. How are you?", role=ROLE_TAO, step_name='ask')
    orchestrator.chain.append(step)
    step = ProceedStep(description="Proceed to solve", role=ROLE_ORCHESTRATOR, step_name='next')
    orchestrator.chain.append(step)
    assert not orchestrator.is_init_solving_expansion()


def test_backtracking(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    orchestrator.config.ask_user_before_execute_codes = False
    orchestrator.config.max_search_expansion = 2
    orchestrator.config.max_retries = 1
    step = PresentTaskStep(description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    proceed_step = ProceedStep(description="Proceed to solve", role=ROLE_ORCHESTRATOR, step_name='start')
    orchestrator.chain.append(proceed_step)

    code = f"""```python
no_such_var * 123
```
    """
    step = AskPythonGenieStep(description=code, role=ROLE_TAO, step_name='ask')
    orchestrator.chain.append(step)
    proceed_step.choices = [step]
    try:
        orchestrator.resume(1000)
    except ParseError:
        pass
    assert "name 'no_such_var' is not defined" in step.criticisms[0]


def test_parse_direct_answer_and_next_step():
    text = """# MY_THOUGHT

So, the first row becomes: 4 3 2 1

```json
{
    "next_to_work_at": {"done with [step#2: sub-plan]": true, "next_step": "Fill in the second row"}
}
```
"""
    step = parse_to_step(text)
    assert isinstance(step, DirectAnswerStep), str(type(step))
    assert not step.is_final_step
    assert step.next_step.next_step_desc == 'Fill in the second row'
    assert step.next_step.target_plan_tag == 'step#2: sub-plan'
    assert step.next_step.target_plan_id == 2
    assert step.next_step.target_plan_done


def test_parse_sequential_step_by_step_and_stepping():
    text = """# HERE_IS_MY_STEP_BY_STEP_PLAN



```json
{
  "1": {"description": "Fill in the first row", "difficulty": 1},
  "2": {"description": "Fill in the second row"},
  "has_branching": false,
  "has_loop": false
}
```
This plan is based on the rules of Sudoku. Each row, column, and 2x2 square must contain all of the numbers from 1 to 4 exactly once. We will fill in the rows one by one, making sure that each number appears exactly once in each row and column, and in each 2x2 square. This is a recursive, top-down approach to solving the puzzle.
"""
    step = parse_to_step(text)
    assert isinstance(step, StepByStepPlan)
    next_step = step.advance_to_next_step()
    assert next_step[0] == 1
    assert next_step[1] == 'Fill in the first row'
    assert next_step[2] == 1
    next_step = step.advance_to_next_step(trial=True)
    assert next_step[0] == 2
    assert next_step[1] == 'Fill in the second row'
    next_step = step.advance_to_next_step()
    assert next_step[0] == 2
    assert next_step[1] == 'Fill in the second row'
    assert next_step[2] == 5
    next_step = step.advance_to_next_step()
    assert next_step is None


def test_parse_looping_step_by_step_and_stepping():
    text = """# HERE_IS_MY_STEP_BY_STEP_PLAN

```json
{
  "1": {"description": "Fill in the first row"},
  "2": {"description": "Repeat step 1"},
  "has_branching": false,
  "has_loop": true
}
```
This plan is based on the rules of Sudoku. Each row, column, and 2x2 square must contain all of the numbers from 1 to 4 exactly once. We will fill in the rows one by one, making sure that each number appears exactly once in each row and column, and in each 2x2 square. This is a recursive, top-down approach to solving the puzzle.
"""
    step = parse_to_step(text)
    assert isinstance(step, StepByStepPlan)
    next_step = step.advance_to_next_step()
    assert next_step[0] == 1
    assert next_step[1] == 'Fill in the first row'
    next_step = step.advance_to_next_step()
    assert next_step is None


def test_python_genie_execution_error(logger):
    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        if reason == 'repair':
            return """
```python
(10 ** 2) * 3.1415
```
"""
        return 'huh'

    llm = MockLLM(logger, reply_fn=reply)
    orchestrator = create_orchestrator(llm, logger)
    orchestrator.config.ask_user_before_execute_codes = False
    code = f"""```python
no_such_var * 123
```
    """
    step = AskPythonGenieStep(description=code, role=ROLE_TAO, step_name='ask')
    step.eval(orchestrator)
    assert '314.15' in step.description
    assert step.n_tries == 1


def test_validate_next_step_spec(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step_by_step = StepByStepPlan(description="""
```json
{
  "1": {"description": "Fill in the first row"},
  "2": {"description": "Fill in the second row"}
}
```""", role=ROLE_TAO, step_name='start')
    orchestrator.chain.append(step_by_step)
    step_by_step2 = StepByStepPlan(description="""
```json
{
  "1": {"description": "Find unfilled slots"},
  "2": {"description": "Fill slots"}
}
```""", role=ROLE_TAO, step_name='Fill in the first row')
    orchestrator.chain.append(step_by_step2)
    grandchild = DirectAnswerStep(description="Slot 2 and 3",
                                  role=ROLE_TAO, step_name='Find unfilled slots')
    orchestrator.chain.append(grandchild)

    next_step = NextStepDesc(None, None, False, "Fill in the second row", plan_of_next_step='step#1: start')
    validate_next_step_spec(orchestrator, next_step)

    # next step in parent
    next_step = NextStepDesc(2, 'step#2: Fill in the first row', True, "Fill in the second row",
                             plan_of_next_step='step#1: start')
    validate_next_step_spec(orchestrator, next_step)
    assert next_step.next_step_desc is None # reset to ask later

    # next step in grandparent
    next_step = NextStepDesc(2, 'step#2: Fill in the first row', True, "Fill in the second row",
                             plan_of_next_step='step#2: Fill in the first row')
    validate_next_step_spec(orchestrator, next_step)
    assert next_step.next_step_desc is None

    try:
        next_step = NextStepDesc(0, "step#0: This is a problem", True, "Fill in the second row",
                                 plan_of_next_step='step#0: This is a problem')
        validate_next_step_spec(orchestrator, next_step, current_plan=step_by_step)
        raise AssertionError("Expecting ParseError not raised")
    except ParseError:
        pass
