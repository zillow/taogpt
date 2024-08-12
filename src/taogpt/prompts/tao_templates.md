# Problem Solving Instructions

Given problem solving session so far, choose one of the following actions:

## Report errors

{snippet_report_errors}

Error report is only for previous executed steps. Do NOT errors in other proposals. If you found issues in other 
proposals, you should come up with a new proposal avoiding those issues.

## Make a step-by-step plan

Deliberate on this task step, outline a sequence of sub-tasks.
Do NOT fill in any details and do NOT work on the plan yet, Orchestrator will prompt you to work at each sub-task later.

Follow this markdown template:

`````markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN
<belief analysis for this task/step (without listing the steps here)>

```json
{{
  "1": {{
    "description": "<high-level description without details>", 
    "recursive": true or false, // is this sub-step recursive of the parent
    "difficulty": 1 to 10, // level of difficulty; 10 is most difficult
    "sub_steps": {{
        // ... nested sub-tasks ...
    }}
  }},
  "2": {{ ... }},
  // ...
  "branching_among_steps": true or false, // does this plan contain any conditional branching or early stopping/breaking AMONG its peer steps?
  "looping_among_steps": true or false // does this plan contain any loop AMONG its peer steps?
}}
```
`````

No need to declare the next step for this choice because the next step is the first in the plan.

## Answer directly

Just answer directly if this is simple.

Follow this template:

`````markdown
# MY_THOUGHT
<answer and explanation>

<declare the next step to work at; see the notes below.>
`````

{snippet_op_files}

{snippet_op_ask_questions}

{snippet_op_ask_genie}
