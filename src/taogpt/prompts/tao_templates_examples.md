### Bad example 1: ###

```markdown
I will answer this step directly.
The lucky number is 13.

next, I will proceed to work at roll the dice again.
```

Issues:
1. Missing heading `# I_WILL_ANSWER_THIS_STEP_DIRECTLY`.
2. Declare next step outside of `### NEXT_I_WANT_TO_WORK_AT:` section.

### Bad example 2: ###

```markdown
# I_WILL_ANSWER_THIS_STEP_DIRECTLY
The final answer is 13.

### NEXT_I_WANT_TO_WORK_AT:
None. This is the final answer to the problem.
```

Issues:
1. Wrong strategy used. Must use `# MY_FINAL_ANSWER` for final summary answer.
2. No need for `NEXT_I_WANT_TO_WORK_AT` section in a final answer.

### Bad example 3: ###

```markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN

1. Find a random number.
2. Roll the dice again. [Because it is fun.]

Now, I will proceed to work at the first step.
```

Issues:
1. Unnecessary declaration of next step.

### Good example: ###

```markdown
# I_WILL_ANSWER_THIS_STEP_DIRECTLY
The lucky number is 13.

### NEXT_I_WANT_TO_WORK_AT:
roll the dice again
```
