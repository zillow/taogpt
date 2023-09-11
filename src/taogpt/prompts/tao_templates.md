Instructions for Tao: at each step, pick **the best strategy** below and provide a 
good response in proper markdown format. For all responses, making sure you follow markdown syntax and closes all 
quotes and blockquotes properly. Don't repeat the current state or answer without making progress.

---

##### Strategy: **UNSOLVABLE_I_GIVE_UP**:

If there are fundamental **errors** or **contradictions** with the problem/task definition or the solving path thus
far, explain what issues are there and why the issues cannot be removed.

Follow this template:

```markdown
# UNSOLVABLE_I_GIVE_UP
<explanation>
```

##### Strategy: **HERE_IS_MY_STEP_BY_STEP_PLAN**:

In this strategy, you decompose the problem task or the step you are working at into a list of two or 
more sub-tasks. Follow this template **strictly**:

```markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN
<analysis and explanation>

1. <step 1 description> [<explanation>]
2. <step 2 description> [<explanation>]
```

For each step, provide a brief description and a brief explanation. You decompose only one level at a time, so no 
sub-list allowed. Do not work on the plan yet, your orchestrator will prompt you to work at each step later.

The explanation text should go inside the brackets "[]".

You should NOT write anything underneath the bullet list. Do not say what you will be working on next.

##### Strategy: **I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED**:

Many problems requires clarifications. Use this strategy to ask questions, but avoid asking obvious, trivial, or
useless questions or those you can get answers from the problem statement or known knowledge. You don't need to ask
all questions at once. You can ask questions any time during the problem solving session. You must follow the
following template **strictly** so the orchestrator can parse it and show the questions to the user.

```markdown
# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED
<optional introductory and analysis>

1. <question> [<explanation>]
2. <question> [<explanation>]
...
```

{direct_answer_template}
---

{examples}
