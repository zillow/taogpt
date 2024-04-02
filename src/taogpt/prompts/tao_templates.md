# Problem Solving Instructions

Given problem solving session so far, choose one of the following strategies:

## Strategy: Report errors

{snippet_report_errors}

## Strategy: Ask Questions

Many problems requires clarifications. Use this strategy to ask questions, but avoid obvious, trivial, 
redundant, useless questions, or questions which you should be answering. You should try to ask all questions you 
need up front. You must follow the following template **strictly** so the orchestrator can parse it and show the 
questions to the user.

```markdown
# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED
<optional introductory and analysis>

1. <question> [<explanation>]
2. <question> [<explanation>]
...
```

## Strategy: Step-by-step Plan

In this strategy, the current step is turned into a top-down, high-level, step-by-step plan of which you and 
Orchestrator will solve using tree traversal and backtracking.

* Think abstract. Come up with generic, and high-level. Avoid detailed, specific, fixed-value, and low-level ones. 
  Because it is impossible to backtrack and try different values in detailed plans in case of errors. Likewise, 
  choose linear, decomposable steps over looping. For example, choose "Find and set missing elements to fill-in 
  values" instead of "Set 2nd and 5th elements to 22".
* Avoid loops if possible as they are less friendly to depth-first search for solution.
* Worship Occam's razor.
* Don't jump ahead. Plan **only for this step** and not something else from the higher plans.

Do NOT fill in any details and do NOT work on the plan yet, Orchestrator will prompt you to work at each step later.

Follow this markdown template:

`````markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN
<brief explanation of your plan>

```json
{{
  "1": {{"description": "<high-level description without details>"}},
  "2": {{
        "description": "<high-level description without details>",
        "sub_steps": {{
            "1": {{"description": "<high-level description without details>"}},
            "2": {{"description": "<high-level description without details>"}}
        }}
       }},
  // ...
}}
```
`````

{snippet_direct_answer}

{snippet_notes_for_files}

## Strategy: Ask the Python Genie

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
