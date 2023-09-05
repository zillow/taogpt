import re

from taogpt import parsing


class TestParsingOrderedList:

    def test_parse_order_list_with_single_line_bullets(self):
        steps = [
            "Do ABC [This is critical.]",
            "Do XYZ [This is interesting.]",
            "Summarize [We are done]"
        ]
        text = f"""Here is my step-by-step plan:

1.  {steps[0]} 
2. {steps[1]}
3. {steps[2]}

some other text"""
        results: [str] = parsing.parse_ordered_list(text)
        assert len(results) == 3
        for i in range(len(steps)):
            assert results[i] == steps[i], f"mismatched: step[{i}]='{steps[i]}', results[{i}]='{results[i]}'"

    def test_parse_order_list_with_multi_line_bullets(self):
        steps = [
            """Do ABC [This is critical
step so need more explanation.]""",
            """Do XYZ [This is interesting
step so need more explanation as well""",
            "Summarize [We are done]"
        ]
        text = f"""Here is my step-by-step plan:

1.  {steps[0]} 
2. {steps[1]}
3. {steps[2]}
        """
        expected_steps = [re.sub(r'\s+', ' ', s).strip() for s in steps]
        results: [str] = parsing.parse_ordered_list(text)
        assert len(results) == 3
        for i in range(len(expected_steps)):
            assert results[i] == expected_steps[i], \
                f"mismatched: expected step[{i}]='{expected_steps[i]}', results[{i}]='{results[i]}'"
