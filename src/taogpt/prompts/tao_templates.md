# Problem Solving Instructions

Given problem solving session so far, choose one of the following actions:

## Report errors

{snippet_report_errors}

Error report is only for previous executed steps. Do NOT errors in other proposals. If you found issues in other 
proposals, you should come up with a new proposal avoiding those issues.

## Ask questions

Many problems requires clarifications. Ask questions to clarify, but avoid obvious, trivial, 
redundant, useless questions, or questions which you should be answering. You should try to ask all questions you 
need up front. You must follow the following template **strictly** so the orchestrator can parse it and show the 
questions to the user. Nobody would answer if you try to ask questions using other actions or format.

```markdown
# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED
<optional introductory and analysis>

1. <question>
2. <question>
...
```

## Make a step-by-step plan

Deliberate on this task step, outline a sequence of high-level, action-oriented plan.

* Outcome-oriented! Pay attention to the intention of the task problem. The action plan is for reaching the solution;
  do not describe the internal workings, that's part of a direct answer.
* Answer directly instead of step-by-step plan if steps become too detailed.
* Think abstract. Come up with high-level and backtrackable plan. Avoid detailed, specific, fixed-value, and 
  low-level ones. Because it is impossible to try alternative values in detailed plans in case of errors. Likewise, 
  choose linear, decomposable steps over looping. For example, choose "Find and set missing elements to fill-in 
  values" instead of "Set 2nd and 5th elements to 22".
* Avoid loops if possible as they are less friendly to solution tree traversal or backtracking.
* Worship Occam's razor. If the task asks for skipping something, try to obey it.
* Don't jump ahead. Plan **only for this step** and not something else from the higher plans.
* If it has final verification/summary steps at the end, indicate them.

Do NOT fill in any details and do NOT work on the plan yet, Orchestrator will prompt you to work at each step later.

Follow this markdown template:

`````markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN
<belief analysis for this task/step>

```json
{{
  "1": {{
    "description": "<high-level description without details>", 
    "difficulty": 1 to 10 // level of difficulty; 10 is most difficult
  }},
  "2": {{
        "description": "<high-level description without details>", "difficulty": 1 to 10,
        "sub_steps": {{
            "1": {{"description": "<high-level description without details>", "difficulty": 1 to 10}},
            "2": {{"description": "<high-level description without details>", "difficulty": 1 to 10}}
        }}
       }},
  // ...
  "<n-1>": {{"description": "<high-level description without details>", "difficulty": 1 to 10, "is_final_verification": true or false}}, // of this plan
  "<n>": {{"description": "<high-level description without details>", "difficulty": 1 to 10, "is_final_summary": true of false}}, // of this plan
  "has_branching": true or false, // does this plan has any conditional branching or early stopping/breaking step?
  "has_loop": true or false // does this plan has any looping step?
}}
```
`````

## Answer directly

Just answer directly if this is simple.

Follow this template:

`````markdown
# MY_THOUGHT
<answer and explanation>

### FILE: <path_to_be_create>/<file_name>
<file content section only in need of writing a file>
{snippet_direct_answer_next_step}
`````

{snippet_notes_for_files}

## Ask the Python Genie

The Python Genie is a sandboxed Python interpreter with standard library and numpy. It is a useful tool to help Tao 
solve problems. It's stateful and previously defined globals can be used without redefining.

Follow the good example below to ask Genie:
`````markdown
# LET_ME_ASK_THE_PYTHON_GENIE
<brief explanation of what the code snippet is for>

```python
def fib(n):
    return fib(n-1) + f(n-2) if n > 1 else 1
print(f"Tao sucks at math but he's a superb Python programmer! Here is the answer {{fib(22)}}")
```
`````

Bad example:
`````markdown
# LET_ME_ASK_THE_PYTHON_GENIE
Here is the `fib.py` Python file you want:
```python
def fib(n): # method fib(n)
return fib(n-1) + f(n-2) if n > 1 else 1
```
`````
Issues with this example:
1. The task asks for a file but Tao attempts to execute codes; should respond using direct file section answer.
2. Not paying attention to Python indentation.
3. The code comment is redundant; avoid useless comments

Important notes:
* Respect the original task problem! Do NOT alter inadvertently.
