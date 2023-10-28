Tao, which step you want to work on next? Choose one of the following strategies:

## Strategy: Choose the next step to work on

 ```markdown
 # NEXT_I_WANT_TO_WORK_AT
<next step ID: description> or "None. This is the final step."
 ```

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
