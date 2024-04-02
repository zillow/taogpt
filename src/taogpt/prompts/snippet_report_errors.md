If you see any errors or inconsistencies, response with **specific** errors and prior steps responsible in the
following format:

 `````markdown
 # I_FOUND_ERRORS

```json
{
  "errors" {
      "<issue 1>": ["<at_step_description>", ...],
      "<issue 2>": ["<at_step_description>", ...],
  },
  "warnings": {
      // ...
  }
}
```
`````

where `<at_step_description>` can be found in the bracket "[at step: <at_step_description>]" of the steps.

Do NOT try to fix the errors since Orchestrator wouldn't understand. Instead it will let you try to fix later.
