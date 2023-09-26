from taogpt import parsing
from taogpt.program import ExpandableStep
from taogpt.constants import *
from taogpt.prompts import PromptDb


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
    text = f"""I'm done.

{final_answer}
    """
    decision, answer = parsing.parse_next_step_reply(text)
    assert decision == DONE
    assert answer == final_answer.strip()


def test_parse_next_step_done2():
    answer_details = """This answer is correct one."""
    final_answer = f"""## FINAL_ANSWER
{answer_details}
"""
    text = f"""
I'm done.

{final_answer}
    """
    decision, answer = parsing.parse_next_step_reply(text)
    assert decision == DONE
    assert answer == final_answer.strip()
    step_type, step_def = parsing.parse_step_type_spec(answer)
    assert step_type == FINAL_ANSWER
    assert step_def == answer_details



def test_parse_next_step_next():
    next_plan = """# HERE_IS_MY_STEP_BY_STEP_PLAN
1. step A
2. step B
"""
    text = f"""I want to work on: the_next_step

{next_plan}
    """
    decision, answer = parsing.parse_next_step_reply(text)
    assert decision == 'the_next_step'
    assert answer == next_plan.strip()
