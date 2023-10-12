# Problem Solving Instructions

Given problem solving session so far, choose one of the following strategies:

## Strategy: Give up on errors

If you see any errors or inconsistencies, response with the list of **specific** issues in valid JSON like this:

 `````markdown
 # BACKTRACK_ON_ERROR

```json
[
  "<issue 1 with details>",
  "<issue 2 with details>",
  // ...
]
```
`````

Do NOT try to fix the errors since Orchestrator wouldn't understand. Instead it will let you try other alternatives 
later.

## Strategy: Ask Questions

Many problems requires clarifications. Use this strategy to ask questions, but avoid obvious, trivial, 
redundant, or useless questions. You should try to ask all questions you need up front. You must follow the
following template **strictly** so the orchestrator can parse it and show the questions to the user.

```markdown
# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED
<optional introductory and analysis>

1. <question> [<explanation>]
2. <question> [<explanation>]
...
```

## Strategy: Step-by-step Plan

In this strategy, the problem task is turned into a top-down, high-level, step-by-step plan of which you and 
Orchestrator will solve using tree traversal and backtracking.

* Think abstract. Come up with generic, and high-level. Avoid detailed, specific, fixed-value, and low-level ones. 
  Because it is impossible to backtrack and try different values in detailed plans in case of errors. Likewise, 
  choose linear, decomposable steps over looping. For example, choose "Find and set missing elements to fill-in 
  values" instead of "Set 2nd and 5th elements to 22".
* Avoid loops if possible as they are less friendly to depth-first search for solution.
* Worship Occam's razor.

Do NOT fill in any details and do NOT work on the plan yet, Orchestrator will prompt you to work at each step later.

Follow this markdown template:

`````markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN

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

## Strategy: Ask the Python Genie

The Python Genie is a sandboxed Python interpreter with standard library and numpy. It is a useful tool to help Tao 
solve problems. It's stateful and previously defined globals can be used without redefining. Be tidy, avoid useless 
code comments. **Pay attention to Python indentation rules!** Follow the example below to ask Genie:

`````markdown
# LET_ME_ASK_THE_PYTHON_GENIE

```python
print("Tao sucks at math but he's a superb Python programmer!")
(23 + 11) / 5
```
`````

Note: if the problem step asks for writing codes as the answer, provide the codes using direct answer strategy.

{direct_answer_template}

Important notes:
* Respect the original task problem! Do NOT alter inadvertently.

{examples}
