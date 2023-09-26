## Strategy: Direct Answer

Go with this strategy if the step is simple and you know the correct answer. You should also tell the Orchestrator 
which step you want to work at next in the `NEXT_I_WANT_TO_WORK_AT` section. If you need to write out any file
contents, write out the content in markdown fenced code block under its own file section.

Important Note: if this is the **final** step, then put "None. This is the final step." in the
`NEXT_I_WANT_TO_WORK_AT` section.

Follow this template:

```markdown
# I_WILL_ANSWER_DIRECTLY
<answer and explanation>

### FILE: <file_path_name>
<file content in markdown fenced code block>

### NEXT_I_WANT_TO_WORK_AT:
<next step>
```


Important Note: if this is the **final** step, then put "None. This is the final step." in the 
`NEXT_I_WANT_TO_WORK_AT` section.

Response template:

```markdown
# I_WILL_ANSWER_DIRECTLY
<answer and explanation>

### NEXT_I_WANT_TO_WORK_AT:
<next step>
```
