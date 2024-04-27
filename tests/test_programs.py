import typing as _t
from taogpt.program import *
from mocks import logger

_logger = logger


def test_consolidate_multiple_questions():
    choices = [
        DirectAnswerStep(description="This is an answer", role=ROLE_TAO, step_name='answer'),
        AskQuestionStep(description="1. Question 1.1\n2. Question 1.2", role=ROLE_TAO, step_name='q1'),
        AskQuestionStep(description="1. Question 2.1\n2. Question 2.2", role=ROLE_TAO, step_name='q2'),
        DirectAnswerStep(description="This is another answer", role=ROLE_TAO, step_name='answer2'),
        AskQuestionStep(description="1. Question 3.1\n2. Question 3.2", role=ROLE_TAO, step_name='q3'),
    ]
    original_choices = choices.copy()
    expected_merged_questions = f"{choices[2].description}\n\n---\n\n" \
                                f"{choices[1].description}\n\n---\n\n" \
                                f"{choices[4].description}"
    indices = [3, 2, 4, 1]
    ask_step: AskQuestionStep = choices[2]
    ExpandableStep.consolidate_questions(choices, indices)
    assert choices == original_choices # no changes to choices
    assert indices == [3, 2]
    assert ask_step.description == expected_merged_questions


def test_consolidate_do_nothing_if_one_question():
    choices = [
        DirectAnswerStep(description="This is an answer", role=ROLE_TAO, step_name='answer'),
        AskQuestionStep(description="1. Question 1.1\n2. Question 1.2", role=ROLE_TAO, step_name='q1'),
        DirectAnswerStep(description="This is another answer", role=ROLE_TAO, step_name='answer2'),
    ]
    original_choices = choices.copy()
    expected_merged_questions = choices[1].description
    indices = [2, 1, 0]
    ask_step: AskQuestionStep = choices[1]
    ExpandableStep.consolidate_questions(choices, indices)
    assert choices == original_choices # no changes to choices
    assert indices == [2, 1, 0]
    assert ask_step.description == expected_merged_questions


def test_consolidate_do_nothing_if_no_questions():
    choices = [
        DirectAnswerStep(description="This is an answer", role=ROLE_TAO, step_name='answer'),
        DirectAnswerStep(description="This is another answer", role=ROLE_TAO, step_name='answer2'),
    ]
    original_choices = choices.copy()
    indices = [1, 0]
    ExpandableStep.consolidate_questions(choices, indices)
    assert choices == original_choices # no changes to choices
    assert indices == [1, 0]


def test_step_types():
    step = ProceedStep(description='1. do X\n2. do Y', role=ROLE_TAO, step_name=None)
    assert isinstance(step, ExpandableStep)


def test_final_direct_answer_with_nonstandard_heading():
    content = f"""22

### FILE: dir/foo.py
```python
# return constant
1234
```"""
    text = f"""# {MY_THOUGHT}
{content}

# {NEXT_I_WANT_TO_WORK_AT}
```json
{{
    "next": "all done"
}}
```
"""
    step = _t.cast(DirectAnswerStep, parse_to_step(text, config=Config()))
    assert step.description == '22'
    assert step.next_step.is_final_step


def test_parse_error_report_with_blame_string(logger):
    step = GiveUpStep(description="""
{
    "Placement of numbers": {
      "error": "Incorrect placement of numbers",
      "blame": "step#4: response to Fill in the missing numbers in the first row"
    }
}""", role='tao')

    assert step.description.strip() == """
* error: Incorrect placement of numbers at [step#4: response to Fill in the missing numbers in the first row]
""".strip()
