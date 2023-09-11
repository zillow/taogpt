### Bad example 1: ###

```markdown
I will answer this step directly.
The lucky number is 13.

next, I will proceed to work at roll the dice again.
```

Issues:
1. Missing heading `# I_WILL_ANSWER_DIRECTLY`.
2. Declare next step outside of `### NEXT_I_WANT_TO_WORK_AT:` section.

### Bad example 2: ###

```markdown
# I_WILL_ANSWER_DIRECTLY
The final answer is 13.

FILE: my_module/setting.json
{"number_of_widgets": 3}

### NEXT_I_WANT_TO_WORK_AT:
None. This is the final answer to the problem.
```

Issues:
1. For a final answer, must put "None. This is the final step." in the `NEXT_I_WANT_TO_WORK_AT` section.
2. File content heading must be level-three markdown section, i.e. `### FILE: my_module/setting.json`
3. File content must be in a markdown fenced code block.

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
# I_WILL_ANSWER_DIRECTLY
The lucky number is 13.

### NEXT_I_WANT_TO_WORK_AT:
roll the dice again
```
