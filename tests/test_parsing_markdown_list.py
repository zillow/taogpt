import re

import taogpt.exceptions
from taogpt import parsing


def test_parse_order_list_with_single_line_bullets():
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

def test_parse_order_list_with_multi_line_bullets():
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

def test_allowing_one_list():
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
    except taogpt.exceptions.ParseError as e:
        pass

def test_list_bullet_contiguous():
    text = """To calculate x mod y, we need to find the remainder when x is divided by y.

1. Divide x by y using integer division to get the quotient.
3. Multiply the quotient by y.
4. Subtract the result from step 2 from x to get the remainder.
"""
    try:
        parsing.parse_ordered_list(text)
        assert False, "expecting ParseError"
    except taogpt.exceptions.ParseError as e:
        pass

def test_must_have_one_bullet_list():
    text = """To calculate x mod y, we need to find the remainder when x is divided by y.
        
Divide x by y using integer division to get the quotient.
Multiply the quotient by y.
"""
    try:
        parsing.parse_ordered_list(text)
        assert False, "expecting ParseError"
    except taogpt.exceptions.ParseError as e:
        pass

def test_parse_indented_bullet_list():
    text = """
To solve this problem, we need to find a way to use the four numbers (7, 6, 2, 1) with the operations of addition, subtraction, multiplication, and division to get the result of 24.

  1. Try to multiply the numbers together. [Multiplication is a good starting point because it can quickly increase the 
      value.]
  2. If multiplication doesn't work, try to use a combination of multiplication and addition or subtraction. [
     Sometimes, we need to use a combination of operations to reach the target number.]
  3. If the above steps don't work, try to use division along with other operations. [Division can help to decrease the 
     value if it's too high.]
"""
    results: [str] = parsing.parse_ordered_list(text)
    assert len(results) == 3
