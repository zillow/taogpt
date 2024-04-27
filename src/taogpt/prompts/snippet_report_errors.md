If you see any errors or inconsistencies in the step executed so far, response with **specific** errors and prior steps 
responsible in the following format:

````markdown
 # I_FOUND_ERRORS

```json
{
  "<what to verify>": {
    "error": "<something incorrect, subsequent steps not impacted or fixable>", 
    "content": "<content snippet related to the issue",
    "blame": "<step#>: <step description>",
    "affecting": ["<step#>: <step description>", "<step#>: <step description>", ...]
  },
  // ...
}
```
````

where `"<step#>: <step description>"` should (only) be found in the bracket "[at step#<num>: <step_description>]" of 
the steps (without the brackets.)

Report only real errors. Do NOT report small issues/warnings or intermittent errors that have already been fixed.

If a blamed step wrote/updated a file, also blame subsequent steps updating that file.

Do NOT try to fix the errors since Orchestrator wouldn't understand. Instead it will let you try to fix later.
