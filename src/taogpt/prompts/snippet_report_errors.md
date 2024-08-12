If you see any errors or inconsistencies in the step executed so far, response with **specific** errors and prior steps 
responsible in the following format:

````markdown
 # I_FOUND_ERRORS

```json
{
  "<what to verify>": {
    "error": "<something incorrect, subsequent steps not impacted or fixable>", 
    "blame": "step#<ID>: <step description>",
    "affecting": ["step#<ID>: <step description>", "step#<ID>: <step description>", ...]
  },
  // ...
}
```
````

where `"step#<ID>: <step description>"` should (only) be found in "[at step#<ID>: <step_description>]" snippet of 
the steps (without the brackets.)

Report only real errors. Do NOT report small issues/warnings or intermittent errors that have already been fixed.

If a blamed step wrote/updated a file, also blame subsequent steps updating that file.

Do NOT try to fix the errors since Orchestrator wouldn't understand. Instead it will let you try to fix later.
