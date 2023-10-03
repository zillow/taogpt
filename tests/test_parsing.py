from taogpt import parsing
from taogpt.program import ExpandableStep
from taogpt.constants import *
from taogpt.prompts import PromptDb
from taogpt.utils import eval_and_collect


_REGULAR_RANKINGS = """This is what I think:
```json
{
  "1": {"score": 5.1, "reason": "It looks acceptable but not too good."},
  "2": {"score": 0.0, "reason": "This is incorrect."},
  "3": {"score": 10, "reason": "This is superb"}
}
```
and other extra text
"""

_RANKINGS_WITH_DUPES = """{
  "1": {"score": 5.1, "reason": "It looks acceptable but not too good."},
  "2": {"score": 10, "reason": "This looks like duplicate of 3.", "duplicate_of": 3},
  "3": {"score": 10, "reason": "This is superb"},
  "4": {"score": 5.1, "reason": "This looks like duplicate of 1.", "duplicate_of": 1}
}
"""


def test_ranking_prompt_format():
    prompts: PromptDb = PromptDb.load_defaults()
    prompts.orchestrator_eval_strategy_choices.format(approaches='\n\n'.join(
        [f"[Approach # {i+1}]" for i in range(4)]))


def test_parsing_regular_rankings():
    results, dupes = parsing.parse_ranking_response(_REGULAR_RANKINGS, 3)
    assert results[1] == 5.1
    assert results[2] == 0.0
    assert results[3] == 10.0
    assert len(dupes) == 0


def test_checking_rankings_with_valid_dupes():
    results, dupes = parsing.parse_ranking_response(_RANKINGS_WITH_DUPES, 4)
    ranking_types = {
        1: WILL_ANSWER_DIRECTLY,
        2: HERE_IS_MY_STEP_BY_STEP_PLAN,
        3: HERE_IS_MY_STEP_BY_STEP_PLAN,
        4: WILL_ANSWER_DIRECTLY
    }
    ExpandableStep.check_duplicates(dupes, results, ranking_types)
    assert len(results) == 4
    assert results[1] == 5.1
    assert results[2] == -10.0
    assert results[3] == 10.0
    assert results[4] == -5.1


def test_checking_rankings_with_invalid_dupes():
    results, dupes = parsing.parse_ranking_response(_RANKINGS_WITH_DUPES, 4)
    ranking_types = {
        1: WILL_ANSWER_DIRECTLY,
        2: HERE_IS_MY_STEP_BY_STEP_PLAN,
        3: HERE_IS_MY_STEP_BY_STEP_PLAN,
        4: HERE_IS_MY_STEP_BY_STEP_PLAN
    }
    try:
        ExpandableStep.check_duplicates(dupes, results, ranking_types)
        raise RuntimeError('expecting parse error not raised')
    except parsing.ParseError:
        pass
    assert len(results) == 3
    assert results[1] == 5.1
    assert results[2] == -10.0
    assert results[3] == 10.0


def test_parsing_rankings_with_dupes():
    results, dupes = parsing.parse_ranking_response(_RANKINGS_WITH_DUPES, 4)
    assert len(results) == 2
    assert results[1] == 5.1
    assert results[3] == 10.0
    assert len(dupes) == 2
    assert dupes[2] == 3
    assert dupes[4] == 1


def test_parse_next_step_done():
    final_answer = """# FINAL_ANSWER
This is my final answer"""
    decision, (answer, decision_detail) = parsing.parse_next_step_reply(final_answer)
    assert decision == FINAL_ANSWER
    assert decision_detail is None
    assert answer == final_answer.strip()


def test_parse_next_step_done2():
    answer_details = """I give up."""
    final_answer = f"""## UNSOLVABLE_I_GIVE_UP
{answer_details}
"""
    decision, (answer, decision_detail) = parsing.parse_next_step_reply(final_answer)
    assert decision == UNSOLVABLE
    assert answer == f"# {UNSOLVABLE}\n{answer_details}".strip()
    step_type, step_def = parsing.parse_step_type_spec(answer)
    assert step_type == UNSOLVABLE
    assert step_def == answer_details



def test_parse_next_step_next_missing_next_work_at():
    next_plan = """# HERE_IS_MY_STEP_BY_STEP_PLAN
1. step A
2. step B
"""
    text = f"""I want to work on: the_next_step

{next_plan}
    """
    try:
        parsing.parse_next_step_reply(text)
        assert False, "Expecting ParseError not raised"
    except parsing.ParseError:
        pass


def test_parse_next_step_reply_next_step_to_work_at():
    json_plan = """```json
{
    "1": {"description": "step A"},
    "2": {"description": "step B"}
}
```
"""
    next_plan = f"""# HERE_IS_MY_STEP_BY_STEP_PLAN
{json_plan}
"""
    text = f"""# NEXT_I_WANT_TO_WORK_AT
Do stuff

{next_plan}
    """
    decision, (answer, decision_details) = parsing.parse_next_step_reply(text)
    assert decision == NEXT_I_WANT_TO_WORK_AT
    assert answer == 'Do stuff'
    assert decision_details == next_plan.strip()


def test_parse_next_step_reply_example():
    details = """```python
# Python code with comment
x = 123
```

and

`````markdown
# HEADING 1
some text
```python
a + b
```
`````

The end"""
    text = f"""
# NEXT_I_WANT_TO_WORK_AT
Evaluate possible addition combinations.

## LET_ME_ASK_THE_PYTHON_GENIE

{details}
"""
    decision, (answer, decision_details) = parsing.parse_next_step_reply(text)
    assert decision == NEXT_I_WANT_TO_WORK_AT
    assert answer == 'Evaluate possible addition combinations.'
    assert WILL_ASK_GENIE in decision_details
    assert decision_details == f"# {WILL_ASK_GENIE}\n{details}"


def test_parse_python_code_snippets():
    code_snippets = [
        "1234",
        """
x = 5
y = 4
z = 0
for i in [1]:
    z += i * x * y
z
"""
    ]
    text = f"""free text before

```python
{code_snippets[0]}
```

```python
{code_snippets[1]}
```

free text after
    """
    parsed: [str] = parsing.parse_python_snippets(text)
    assert len(parsed) == 2
    assert parsed[0].strip() == code_snippets[0].strip()
    assert parsed[1].strip() == code_snippets[1].strip()
    assert eval_and_collect(parsed[0]) == '=> 1234'
    assert eval_and_collect(parsed[1]) == '=> 20'


def test_parse_step_by_step_plan_raise_invalid_json():
    text = f"""# HERE_IS_MY_STEP_BY_STP_PALN
```json
{{
    "1": {{"description": "", "why": ""}},
```
"""
    try:
        parsing.parse_step_by_step_plan(text)
        assert False, "Expecting ParseError but not raised"
    except parsing.ParseError:
        pass


def test_parse_step_by_step_plan_raise_less_than_2_steps():
    text = f"""# HERE_IS_MY_STEP_BY_STP_PALN
```json
{{
    "1": {{"description": "", "why": ""}}
}}
```
"""
    try:
        parsing.parse_step_by_step_plan(text)
        assert False, "Expecting ParseError but not raised"
    except parsing.ParseError as e:
        assert "Should have at least 2 steps" in str(e)


def test_parse_step_by_step_plan_raise_key_not_integer():
    text = f"""# HERE_IS_MY_STEP_BY_STP_PALN
```json
{{
    "1": {{"description": "", "why": ""}},
    "a": {{"description": "", "why": ""}}
}}
```
"""
    try:
        parsing.parse_step_by_step_plan(text)
        assert False, "Expecting ParseError but not raised"
    except parsing.ParseError as e:
        assert "not an integer" in str(e)


def test_parse_step_by_step_plan_raise_on_invalid_ordering():
    steps = ["step 1", "step 2"]
    reasons = ["reason 1"]
    text = f"""# HERE_IS_MY_STEP_BY_STP_PALN
```json
{{
    "2": {{"description": "{steps[1]}"}},
    "1": {{"description": "{steps[0]}", "why": "{reasons[0]}"}}
}}
```
"""
    try:
        parsing.parse_step_by_step_plan(text)
        assert False, "Expecting ParseError but not raised"
    except parsing.ParseError as e:
        assert "Element keys should be a contiguous natural number sequence starting at 1" in str(e)


def test_parse_step_by_step_plan():
    steps = ["step 1", "step 2"]
    reasons = ["reason 1"]
    text = f"""# HERE_IS_MY_STEP_BY_STP_PALN
```json
{{
    "1": {{"description": "{steps[0]}", "why": "{reasons[0]}"}},
    "2": {{"description": "{steps[1]}"}}
}}
```
"""
    results = parsing.parse_step_by_step_plan(text)
    assert len(results) == 2
    assert results[0].description == steps[0]
    assert results[0].why == reasons[0]
    assert results[1].description == steps[1]
    assert results[1].why is None
