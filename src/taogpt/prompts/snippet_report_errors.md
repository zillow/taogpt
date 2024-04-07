If you see any errors or inconsistencies in the step executed so far, response with **specific** errors and prior steps 
responsible in the following format:

 `````markdown
 # I_FOUND_ERRORS

```json
{
  "errors" {
      "<issue 1>": "<step#>: <step description>",
      "<issue 2>": "<step#>: <step description>"
  },
  "warnings": {
      // ...
  }
}
```
`````

where `"<step#>: <step description>"` should (only) be found in the bracket "[at step#<num>: <step_description>]" of 
the steps (without the brackets.)

If a blamed step wrote/updated a file, also blame subsequent steps updating that file.

Do NOT report intermittent errors that have already been fixed.

Do NOT try to fix the errors since Orchestrator wouldn't understand. Instead it will let you try to fix later.
