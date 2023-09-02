from taogpt import parsing
from taogpt.program import ExpandableStep
from taogpt.constants import *

_REGULAR_RANKINGS = """This is what I think:

1. score 5.1 [It looks acceptable but not too good]
2. score 0 [This is incorrect]
3. score 10 [This is superb.]
"""

_RANKINGS_WITH_DUPES = """This is what I think:

1. score 5.1 [It looks acceptable but not too good]
2. duplicate of 3 [This looks like the same as 3]
3. score 10 [This is superb.]
4. duplicate of 1 [This looks like the same as 1]
"""


class TestParsingRankings:

    def test_parsing_regular_rankings(self):
        results, dupes = parsing.parse_ranking_response(_REGULAR_RANKINGS, 3)
        assert results[1] == 5.1
        assert results[2] == 0.0
        assert results[3] == 10.0
        assert len(dupes) == 0


    def test_parsing_rankings_with_dupes(self):
        self._help_test_parsing_rankings_with_dupes(_RANKINGS_WITH_DUPES)

    def test_parsing_rankings_with_dupes_colon(self):
        self._help_test_parsing_rankings_with_dupes(_RANKINGS_WITH_DUPES.replace('of', 'of:'))

    def test_checking_rankings_with_valid_dupes(self):
        results, dupes = parsing.parse_ranking_response(_RANKINGS_WITH_DUPES, 3)
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
        results, dupes = parsing.parse_ranking_response(_RANKINGS_WITH_DUPES, 3)
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

    @staticmethod
    def _help_test_parsing_rankings_with_dupes(text):
        results, dupes = parsing.parse_ranking_response(text, 3)
        assert len(results) == 2
        assert results[1] == 5.1
        assert results[3] == 10.0
        assert len(dupes) == 2
        assert dupes[2] == 3
        assert dupes[4] == 1

