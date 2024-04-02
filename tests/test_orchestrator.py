from mocks import MockLLM, create_orchestrator, logger
import typing as _t
from taogpt.program import *
from taogpt.parsing import ParseError, parse_verification_response

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
    "calculation": {"warning": "Can simplify", "blame": ["step13", "step22"]}
    }
    """
    concerns, _ = parse_verification_response(text)
    assert len(concerns) == 1

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        if reason == 'check_final_answer':
            return text
        elif reason == 'summarize':
            return "Here is your answer"

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    step.eval(orchestrator)
    assert len(llm.conversation_sequence) == 3
    assert llm.conversation_sequence[0][0] == 'summarize'
    assert llm.conversation_sequence[1][0] == 'check_final_answer'
    assert llm.conversation_sequence[2][0] == 'summarize'


def test_check_final_solution_failed(logger):
    text = """{
    "calculation": {"error": "1 + 1 != 3", "blame": "calculate total"},
    "etc": {"ok": "Good"}
    }
    """
    concerns, full_json = parse_verification_response(text)
    assert concerns == {"1 + 1 != 3": ("error", ["calculate total"])}
    assert json.loads(text).keys() == full_json.keys()

    def reply(_conversation: [(str, str)], reason: str, _step_id: str) -> str:
        if reason == 'summarize':
            return "3"
        if reason == 'check_final_answer':
            return text
        assert False, f"Unexpected reason: {reason}"

    step, llm, orchestrator = create_final_check_chain(reply, logger)
    _t.cast(DirectAnswerStep, step.previous)._n_tries = orchestrator.config.max_retries
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
        if reason == 'check_final_answer':
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
    step = PresentTaskStep(previous=None, description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = DirectAnswerStep(previous=step, description="This is an answer", role=ROLE_TAO)
    step.set_step_name('calculate total')
    orchestrator.chain.append(step)
    step = SummarizeStep(previous=step, description="This is the final answer", role=ROLE_TAO)
    orchestrator.chain.append(step)
    return step, llm, orchestrator


def test_need_full_expansion_at_first_expandable_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(previous=None, description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(previous=step, description="Proceed to solve", role=ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    assert orchestrator.is_first_solving_expansion()


def test_need_full_expansion_at_first_expandable_step_followed_by_ask_step(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(previous=None, description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(previous=step, description="Proceed to solve", role=ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    step = AskQuestionStep(previous=step, description="I have a question", role=ROLE_TAO)
    orchestrator.chain.append(step)
    step = ProceedStep(previous=step, description="Proceed to solve", role=ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    assert orchestrator.is_first_solving_expansion()


def test_no_full_expansion_at_subsequent_expandable_steps(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    step = PresentTaskStep(previous=None, description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    step = ProceedStep(previous=step, description="Proceed to solve", role=ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    step = StepByStepPlan(previous=step, description=EXAMPLE_STEP_BY_STEP_PLAN, role=ROLE_TAO)
    orchestrator.chain.append(step)
    step = AskQuestionStep(previous=step, description="I have a question", role=ROLE_TAO)
    orchestrator.chain.append(step)
    step = ProceedStep(previous=step, description="Proceed to solve", role=ROLE_ORCHESTRATOR)
    orchestrator.chain.append(step)
    assert not orchestrator.is_first_solving_expansion()


def test_backtracking(logger):
    llm = MockLLM(logger)
    orchestrator = create_orchestrator(llm, logger)
    orchestrator.config.ask_user_before_execute_codes = False
    orchestrator.config.max_search_expansion = 2
    orchestrator.config.max_retries = 1
    step = PresentTaskStep(previous=None, description="This is a problem", role=ROLE_USER)
    orchestrator.chain.append(step)
    proceed_step = ProceedStep(previous=step, description="Proceed to solve", role=ROLE_ORCHESTRATOR)
    orchestrator.chain.append(proceed_step)

    code = f"""```python
no_such_var * 123
```
    """
    step = AskPythonGenieStep(previous=proceed_step, description=code, role=ROLE_TAO)
    orchestrator.chain.append(step)
    proceed_step.choices = [step]
    try:
        orchestrator.resume(1000)
    except ParseError:
        pass
    assert "name 'no_such_var' is not defined" in step.criticisms[0]


def test_parse_direct_answer_and_next_step():
    text = """# I_WILL_ANSWER_DIRECTLY



To fill in the first row, we need to find the numbers that are not already present. The numbers in the first row are 3 and 1. So, the missing numbers are 2 and 4.

We can't put 2 in the first cell because the number 2 is already present in the first column. So, the first cell must be 4. 

Then, the third cell must be 2 because it's the only number left.

So, the first row becomes: 4 3 2 1

### NEXT_I_WANT_TO_WORK_AT:
Fill in the second row [None]
"""
    step = parse_to_step(None, text, config=Config())
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
    step = parse_to_step(None, text, config=Config())
    assert isinstance(step, StepByStepPlan)
    assert step.first_step == 'Fill in the first row'


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
    step = AskPythonGenieStep(previous=None, description=code, role=ROLE_TAO)
    step.eval(orchestrator)
    assert '314.15' in step.description
    assert step.n_tries == 2
