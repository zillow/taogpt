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


def test_final_direct_answer_with_next_step():
    content = f"""22

"""
    text = f"""{MY_THOUGHT}:
{content}                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                

```json
{{
    "next_to_work_at": {{ "next_step": "all done" }}
}}
```
"""
    step = _t.cast(DirectAnswerStep, parse_to_step(text))
    assert step.description == '22'
    assert step.next_step.is_final_step


def test_step_by_step_with_next_step():
    text = f"""{HERE_IS_MY_STEP_BY_STEP_PLAN}:

1. step 1
2. step 2

```json
{{
    "next_to_work_at": {{ "next_step": "all done" }}
}}
```
"""
    step = _t.cast(StepByStepPlan, parse_to_step(text))
    step.parse_and_set_step_plan("""
```json
{
  "1": {"description": "<high-level description without details>step 1", "difficulty": 1},
  "2": {"description": "step 2", "difficulty": 10}
}
```
""")
    assert len(step.steps) == 2
    assert step._next_step is None


def test_parse_error_report_with_blame_string(logger):
    report_json = """
{
    "Placement of numbers": {
      "error": "Incorrect placement of numbers",
      "blame": "step#4: response to Fill in the missing numbers in the first row"
    }
}"""
    step = ReportErrorStep(description=report_json, role='tao')

    assert step.description.strip() == report_json.strip()


def test_next_step():
    dn = DirectAnswerStep(description="""
some text

```json
{
    "next_to_work_at": {
        "done with [at step#12: this plan]": true,
        "plan_of_next_step": "step#10: parent plan",
        "next_step": "next thing to do",
        "difficulty": 4,
        "next_step_seq": 2
    }
}
```
""", role="Tao", step_name="test")
    assert dn.next_step.target_plan_done
    assert dn.next_step.target_plan_id == 12
    assert dn.next_step.next_step_desc == 'next thing to do'
    assert dn.next_step.difficulty == 4


def test_parse_to_file_steps():
    text = f"""
Write some file

## File: path1/file1.txt

```text
file 1 text
```

## File: path2//file2.txt

```text
file 2 text
```
"""
    step = parse_to_step(f"""{WRITE_FILE}:
{text}""")
    assert step.description == text.strip()
    files = step.collected_files
    assert len(files) == 2
    assert files['path1/file1.txt'].content == 'file 1 text'
    assert files['path2/file2.txt'].content == 'file 2 text'
