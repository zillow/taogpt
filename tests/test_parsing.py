import taogpt.exceptions
from taogpt import parsing
from taogpt.program import ExpandableStep
from taogpt.constants import *
from taogpt.prompts import PromptDb
from taogpt.utils import eval_and_collect
from taogpt.parsing import extract_fenced_blocks, restore_fenced_block
from taogpt import GeneratedFile

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


def test_fix_fenced_block_backticks():
    original = """
sometimes
````text
digits are inserted after the backticks
```1
like this
  ```
  ````00
other times OK
"""

    expected = """
sometimes
````text
digits are inserted after the backticks
```
like this
```
````
other times OK
"""
    assert parsing.fix_fenced_block_backticks(original) == expected


def test_parse_step_type_spec():
    reply_detail = """This is an answer.

```json
{{
    "next_to_work_at": {{
        "next_step": "setup",
        "done with [step#22: check arithmetics]": true
    }}
}}
```"""
    for left, right in [('', ''), ('# ', ''), ('**', '**'), ('# **', '')]:
        text = f"""{left}{MY_THOUGHT}:{right}
    {reply_detail}
    """
        reply_type, step_def = parsing.parse_step_type_spec(text)
        assert reply_type == MY_THOUGHT, f"for heading {left}{MY_THOUGHT}:{right}"
        assert step_def == reply_detail, f"for heading {left}{MY_THOUGHT}:{right}"


def test_ranking_prompt_format():
    prompts: PromptDb = PromptDb.load_defaults()
    prompts.sage_rank_choices.format(choices='\n\n'.join(
        [f"[Choice # {i+1}]" for i in range(4)]))


def test_parsing_regular_rankings():
    results, dupes = parsing.parse_ranking_response(_REGULAR_RANKINGS, 3)
    assert results[1] == 5.1
    assert results[2] == 0.0
    assert results[3] == 10.0
    assert len(dupes) == 0


def test_checking_rankings_with_valid_dupes():
    results, dupes = parsing.parse_ranking_response(_RANKINGS_WITH_DUPES, 4)
    ranking_types = {
        1: MY_THOUGHT,
        2: HERE_IS_MY_STEP_BY_STEP_PLAN,
        3: HERE_IS_MY_STEP_BY_STEP_PLAN,
        4: MY_THOUGHT
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
        1: MY_THOUGHT,
        2: HERE_IS_MY_STEP_BY_STEP_PLAN,
        3: HERE_IS_MY_STEP_BY_STEP_PLAN,
        4: HERE_IS_MY_STEP_BY_STEP_PLAN
    }
    try:
        ExpandableStep.check_duplicates(dupes, results, ranking_types)
        raise RuntimeError('expecting parse error not raised')
    except taogpt.exceptions.ParseError:
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


def test_parse_next_step_done2():
    answer_details = """I give up."""
    final_answer = f"""I_FOUND_ERRORS:
{answer_details}
"""
    decision, answer = parsing.parse_next_step_reply(final_answer)
    assert decision == REPORT_ERROR
    assert answer == f"{REPORT_ERROR}:\n{answer_details}".strip()


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
    text = f"""RUN_CODE_SNIPPET:

{details}

```json
{{
    "next_to_work_at": {{
        "next_step": "setup",
        "done with [step#22: check arithmetics]": true
    }}
}}
```
"""
    decision, answer = parsing.parse_next_step_reply(text)
    assert decision == NEXT_I_WANT_TO_WORK_AT
    assert isinstance(answer, parsing.NextStepDesc)
    assert answer.next_step_desc == 'setup'
    assert answer.target_plan_id == 22
    assert answer.target_plan_done
    assert answer.target_plan_tag == "step#22: check arithmetics"


def test_parse_python_code_snippets():
    code_snippets = [
        """
import math

def foo():
    _ = math.sin(1234)
    return 3

1234""",
        """
x = 5
y = 4
z = 0
for i in [1]:
    z += i * x * y
z + foo()
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
    parsed: list[str] = parsing.parse_python_snippets(text)
    assert len(parsed) == 2
    assert parsed[0].strip() == code_snippets[0].strip()
    assert parsed[1].strip() == code_snippets[1].strip()
    global_scope = dict()
    assert eval_and_collect(parsed[0], global_scope) == '=> 1234'
    assert eval_and_collect(parsed[1], global_scope) == '=> 23'


def test_parse_step_by_step_plan_raise_invalid_json():
    text = f"""# HERE_IS_MY_STEP_BY_STP_PLAN
```json
{{
    "1": {{"description": "", "why": ""}},
```
"""
    try:
        parsing.parse_step_by_step_plan(text)
        assert False, "Expecting ParseError but not raised"
    except taogpt.exceptions.ParseError:
        pass


def test_parse_step_by_step_plan_raise_less_than_2_steps():
    text = f"""# HERE_IS_MY_STEP_BY_STP_PLAN
```json
{{
    "1": {{"description": "", "why": ""}}
}}
```
"""
    try:
        parsing.parse_step_by_step_plan(text)
        assert False, "Expecting ParseError but not raised"
    except taogpt.exceptions.ParseError as e:
        assert "Should have at least 2 steps" in str(e)


def test_parse_step_by_step_plan_raise_key_not_integer():
    text = f"""# HERE_IS_MY_STEP_BY_STP_PLAN
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
    except taogpt.exceptions.ParseError as e:
        assert "not an integer" in str(e)


def test_parse_step_by_step_plan_raise_on_invalid_ordering():
    steps = ["step 1", "step 2"]
    reasons = ["reason 1"]
    text = f"""# HERE_IS_MY_STEP_BY_STP_PLAN
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
    except taogpt.exceptions.ParseError as e:
        assert "Element keys should be a contiguous natural number sequence starting at 1" in str(e)


def test_parse_step_by_step_plan():
    steps = ["step 1", "step 2", "final check"]
    reasons = ["reason 1"]
    text = f"""# HERE_IS_MY_STEP_BY_STP_PLAN
```json
{{
    "1": {{"description": "{steps[0]}", "why": "{reasons[0]}"}},
    "2": {{"description": "{steps[1]}"}},
    "3": {{"description": "{steps[2]}"}},
    "has_loop": true
}}
```
"""
    results, has_branching, has_loop = parsing.parse_step_by_step_plan(text)
    assert len(results) == 3
    assert results[1].description == steps[0]
    assert results[1].why == reasons[0]
    assert results[2].description == steps[1]
    assert results[2].why is None
    assert results[3].description == steps[2]
    assert not has_branching
    assert has_loop


def test_replacement_with_multiple_identical_fenced_blocks():
    text = """
These are previous proposals tried and criticisms received going down this step:

[Proposal 1] There is indeed an error in the last step.

```text
+-+-+-+-+
|4|3|2|1|
```

Let's backtrack and correct this error.

---
[Proposal 2] I see that there was an error in the final step of filling in the Sudoku grid.

```text
+-+-+-+-+
|4|3|2|1|
```
"""
    extracted, sub_text = extract_fenced_blocks(text)
    assert len(extracted) == 1
    assert sub_text.strip() != text.strip()
    restored = restore_fenced_block(sub_text, extracted)
    assert restored == text


def test_parse_next_step():
    text = """
```json
{
    "next_to_work_at": {
        "done with [step#1: top-level plan]": true,
        "next_step": "all done",
        "difficulty": 8
    }
}
```
"""
    next_step, _ = parsing.parse_next_step_spec(text)
    assert next_step.next_step_desc == "all done"
    assert next_step.target_plan_id == 1
    assert next_step.difficulty == 8


def test_parse_next_step_invalid():
    text = """
```json
{
    "next_to_work_at": {"done with [top-level plan]": true, "next_step": "foo"}
}
```
"""
    try:
        parsing.parse_next_step_spec(text)
        assert False, "Expecting ParseError not raised"
    except taogpt.exceptions.ParseError as e:
        pass


def test_parse_step_id_and_name():
    assert parsing.parse_step_id_and_name("step#100: some step") == (100, "some step")
    assert parsing.parse_step_id_and_name("[at step#100: some step]") == (100, "some step")
    assert parsing.parse_step_id_and_name("[at step#123: some step]") == (123, "some step")
    assert parsing.parse_step_id_and_name("[at step#123:some step]") == (123, "some step")
    assert parsing.parse_step_id_and_name("  [step#123: some step]") == (123, "some step")
    for invalid in ["some step", "step#: some step"]:
        try:
            parsing.parse_step_id_and_name(invalid)
            raise AssertionError(f"expecting ParseError not raised for patten '{invalid}'")
        except taogpt.exceptions.ParseError:
            pass


def test_check_and_fix_fenced_block_extraction():
    fixed, blocks = parsing.check_and_fix_fenced_blocks("""
````markdown
 a + b
````11

```text
text

```0
trailing text
""")

    for i, (digest, block) in enumerate(blocks.items()):
        if i == 0:
            assert block[0] == """````markdown
 a + b
````"""
        elif i == 1:
            assert block[0] == """```text
text

```"""
        else:
            assert i <= 1, "Unexpected blocks extracted"


def test_check_and_fix_fenced_block_collapsed():
    fixed, blocks = parsing.check_and_fix_fenced_blocks("""
````markdown
a + b
````11

```text
text
```0
trailing text
""", collapse_blocks=True)

    for i, (digest, block) in enumerate(blocks.items()):
        if i == 0:
            assert block[0] == """````markdown
a + b
````"""
            assert digest in fixed
            assert "a + b" not in fixed
        elif i == 1:
            assert block[0] == """```text
text
```"""
        else:
            assert i <= 1, "Unexpected blocks extracted"
            assert digest in fixed
            assert "text" not in fixed


def test_check_and_fix_fenced_block_extraction_nested():
    fixed, blocks = parsing.check_and_fix_fenced_blocks("""
````markdown
a + b

```text
text
```0
````11
""")

    for i, (digest, block) in enumerate(blocks.items()):
        if i == 0:
            assert block[0] == """````markdown
a + b

```text
text
```
````"""
        else:
            assert i <= 1, "Unexpected blocks extracted"


def test_check_and_fix_fenced_block_collapsed_with_nested():
    fixed, blocks = parsing.check_and_fix_fenced_blocks("""
````markdown
a + b

```text
text
```0
````11
""", collapse_blocks=True)

    for i, (digest, block) in enumerate(blocks.items()):
        if i == 0:
            assert block[0] == """````markdown
a + b

```text
text
```
````"""
            assert digest in fixed
            assert "a + b" not in fixed
            assert "text" not in fixed
        else:
            assert i <= 1, "Unexpected blocks extracted"


def test_check_and_fix_unquoted_html_tags():
    html_block = """````html
<html>
<body><div>but don't quoted the ones in html fenced block</div></body>
</html>
````
"""
    fixed, blocks = parsing.check_and_fix_fenced_blocks(f"""
some html tags like <div> or `<table> are not quoted by backtick. Others `<div>` OK.
{html_block}
""", collapse_blocks=False)
    assert fixed.strip() == f"""
some html tags like `<div>` or `<table>` are not quoted by backtick. Others `<div>` OK.
{html_block}""".strip(), fixed
    for i, (digest, block) in enumerate(blocks.items()):
        if i == 0:
            assert block[0] == html_block.strip()
        else:
            assert i <= 1, "Unexpected blocks extracted"


def test_sanitize_step_name():
    original = "[\"'do\n''something]"
    fixed = parsing.sanitize_step_name(original)
    assert fixed == 'do something'


def test_fix_nested_fenced_blocks():
    original = """MY_THOUGHT:
[at step#14: Set up a basic README file in the root directory]

To provide basic guidance on setting up and running the application, we will create a README file in the root directory of the project. This file will include instructions on how to install dependencies, set up the virtual environment, and run the Flask application.

```markdown
1. Clone the repository to your local machine.
2. Navigate to the project directory.
3. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
```

```json
{
    "done with [at step#4: Set up the project structure including necessary directories and files for a Python Flask web application]": true
}
```"""
    expected_annotated = """MY_THOUGHT:
[at step#14: Set up a basic README file in the root directory]

To provide basic guidance on setting up and running the application, we will create a README file in the root directory of the project. This file will include instructions on how to install dependencies, set up the virtual environment, and run the Flask application.

```markdown # BACKTICK1
1. Clone the repository to your local machine.
2. Navigate to the project directory.
3. Create a virtual environment:
   ```bash # BACKTICK2
   python -m venv venv
   ``` # BACKTICK3
``` # BACKTICK4

```json # BACKTICK5
{
    "done with [at step#4: Set up the project structure including necessary directories and files for a Python Flask web application]": true
}
``` # BACKTICK6"""
    annotated = parsing.annotate_fenced_block_backtick_quotes(original)
    assert annotated.strip() == expected_annotated.strip()




def test_parse_issue_report():
    issue = "The calculation (6 / (1 + 2)) * 7 results in 14, not 24."
    blamed_desc = "Derive result equals 24."
    text = f"""
```json
{{
  "Final solution verification": {{
    "error": "{issue}",
    "content": "(6 / (1 + 2)) * 7 = 24",
    "blame": ["step#10: {blamed_desc}"],
    "affecting": []
  }}
}}
```
"""
    all_issues, no_culprit_issues = parsing.parse_issue_report(text)
    assert len(all_issues) == 1
    level, blames = all_issues[issue]
    assert level == 'error'
    assert len(blames) == 1
    assert  blames[0][0] == 10
    assert blames[0][1] == blamed_desc
    assert len(no_culprit_issues) == 0


def test_file_comparison():
    f1 = GeneratedFile("text", """
Line 1
```json
{}
```
""", "desc")
    f2 = GeneratedFile("text", """
Line 1
```json
{}
```
""", "desc2")
    assert f1 == f2
    assert not f1 != f2
    f3 = GeneratedFile("text", """
Line 1
```json
123
```
""", "desc")
    assert not f1 == f3
    assert f1 != f3

