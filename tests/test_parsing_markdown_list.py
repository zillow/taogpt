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

    def test_allowing_one_list(self):
        text = """To calculate x mod y, we need to find the remainder when x is divided by y.

1. Divide x by y using integer division to get the quotient.
2. Multiply the quotient by y.
3. Subtract the result from step 2 from x to get the remainder.

Now, let's calculate x mod y using this plan.

1. Divide x by y using integer division to get the quotient.

I will now perform this step.
"""
        try:
            parsing.parse_ordered_list(text)
            assert False, "expecting ParseError"
        except parsing.ParseError as e:
            pass

    def test_list_bullet_contiguous(self):
        text = """To calculate x mod y, we need to find the remainder when x is divided by y.

1. Divide x by y using integer division to get the quotient.
3. Multiply the quotient by y.
4. Subtract the result from step 2 from x to get the remainder.
"""
        try:
            parsing.parse_ordered_list(text)
            assert False, "expecting ParseError"
        except parsing.ParseError as e:
            pass

    def test_msut_have_one_bullet_list(self):
        text = """To calculate x mod y, we need to find the remainder when x is divided by y.
        
Divide x by y using integer division to get the quotient.
Multiply the quotient by y.
"""
        try:
            parsing.parse_ordered_list(text)
            assert False, "expecting ParseError"
        except parsing.ParseError as e:
            pass
