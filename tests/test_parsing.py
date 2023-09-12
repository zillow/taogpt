from taogpt import parsing
from taogpt.program import ExpandableStep
from taogpt.constants import *
from taogpt.prompts import PromptSet


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


class TestParsingRankings:

    def test_ranking_prompt_format(self):
        prompts: PromptSet = PromptSet.load_defaults()
        prompts.orchestrator_eval_strategy_choices.format(approaches='\n\n'.join(
            [f"[Approach # {i+1}]" for i in range(4)]))

    def test_parsing_regular_rankings(self):
        results, dupes = parsing.parse_ranking_response(_REGULAR_RANKINGS, 3)
        assert results[1] == 5.1
        assert results[2] == 0.0
        assert results[3] == 10.0
        assert len(dupes) == 0

    def test_checking_rankings_with_valid_dupes(self):
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

    def test_checking_rankings_with_invalid_dupes(self):
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

    def test_parsing_rankings_with_dupes(self):
        results, dupes = parsing.parse_ranking_response(_RANKINGS_WITH_DUPES, 4)
        assert len(results) == 2
        assert results[1] == 5.1
        assert results[3] == 10.0
        assert len(dupes) == 2
        assert dupes[2] == 3
        assert dupes[4] == 1

