# Problem Solving Instructions:

Assess the difficulty of the task/step in the range of 1 to 10 and then choose one of the following actions to solve 
this task/step:

## Report errors in previous steps

Error report is only for previous executed steps. Do NOT use this action report errors in other proposals. If you found 
issues in other proposals, you should come up with a new proposal avoiding those issues.

{snippet_report_errors}

## Make a step-by-step plan

Deliberate on this task step, outline a sequence of sub-tasks. 

Choose this action only if the task step is hard, not because it can be broken down into sub-steps; 
if steps become too detailed, choose other types of actions instead.

Do NOT fill in any details and do NOT work on the plan yet, Orchestrator will prompt you to work at each sub-task later.

Plan should solve only this task step. Avoid duplicated work item already planned in the parent plans or prior steps.

The plan can contain go-to loop, conditional branch, or recursion. Also estimate the difficulty level for each sub-step.

Follow this markdown template:

```markdown
HERE_IS_MY_STEP_BY_STEP_PLAN:

<briefly explain the rationales>

1. <description>. Difficulty: 1 to 10
2. <description>. Difficulty: 1 to 10
...
```

## Answer directly

Just answer directly if this is simple.

Follow this template:

`````markdown
MY_THOUGHT:
<answer and explanation>
`````

{snippet_op_files}

{snippet_op_ask_questions}

{snippet_op_ask_genie}

---

If you find task step has already been done in one of the prior steps, then point out this fact in a direct answer.
