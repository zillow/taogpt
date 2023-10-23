from taogpt.program import *
from mocks import logger

_logger = logger


def test_consolidate_multiple_questions():
    choices = [
        DirectAnswerStep(None, "This is an answer", ROLE_TAO),
        AskQuestionStep(None, "1. Question 1.1\n2. Question 1.2", ROLE_TAO),
        AskQuestionStep(None, "1. Question 2.1\n2. Question 2.2", ROLE_TAO),
        DirectAnswerStep(None, "This is another answer", ROLE_TAO),
        AskQuestionStep(None, "1. Question 3.1\n2. Question 3.2", ROLE_TAO),
    ]
    original_choices = choices.copy()
    expected_merged_questions = f"{choices[2].description}\n\n---\n\n" \
                                f"{choices[1].description}\n\n---\n\n" \
                                f"{choices[4].description}"
    indices = [3, 2, 4, 1]
    ask_step: AskQuestionStep = choices[2]
    assert not ask_step.need_consolidate
    ExpandableStep.consolidate_questions(choices, indices)
    assert choices == original_choices # no changes to choices
    assert indices == [3, 2]
    assert ask_step.description == expected_merged_questions
    assert ask_step.need_consolidate


def test_consolidate_do_nothing_if_one_question():
    choices = [
        DirectAnswerStep(None, "This is an answer", ROLE_TAO),
        AskQuestionStep(None, "1. Question 1.1\n2. Question 1.2", ROLE_TAO),
        DirectAnswerStep(None, "This is another answer", ROLE_TAO),
    ]
    original_choices = choices.copy()
    expected_merged_questions = choices[1].description
    indices = [2, 1, 0]
    ask_step: AskQuestionStep = choices[1]
    assert not ask_step.need_consolidate
    ExpandableStep.consolidate_questions(choices, indices)
    assert choices == original_choices # no changes to choices
    assert indices == [2, 1, 0]
    assert ask_step.description == expected_merged_questions
    assert not ask_step.need_consolidate


def test_consolidate_do_nothing_if_no_questions():
    choices = [
        DirectAnswerStep(None, "This is an answer", ROLE_TAO),
        DirectAnswerStep(None, "This is another answer", ROLE_TAO),
    ]
    original_choices = choices.copy()
    indices = [1, 0]
    ExpandableStep.consolidate_questions(choices, indices)
    assert choices == original_choices # no changes to choices
    assert indices == [1, 0]


def test_step_types():
    step = ProceedStep(None, '1. do X\n2. do Y', ROLE_TAO)
    assert isinstance(step, ExpandableStep)


def test_final_direct_answer_with_nonstandard_heading():
    content = f"""22

### FILE: dir/foo.py
```python
# return constant
1234
```"""
    text = f"""# {WILL_ANSWER_DIRECTLY}
{content}

# {NEXT_I_WANT_TO_WORK_AT}
None. I'm done.
"""
    step: DirectAnswerStep = parse_to_step(None, text)
    assert step.is_final_step
    assert step.description == '22'
