Next step direction must be in a JSON fenced block with format:

```json
{{
    "done with {step}": true or false, // we are at this `HERE_IS_MY_STEP_BY_STEP_PLAN`, is everything in this plan done?
    "plan_of_next_step": "step#<ID>: <description>", // if current plan is NOT done, set this to the current plan; if next step is from the higher level, set it that plan; if "all done". set to the root level plan.
    "next_step": "<step description>", // next step or "all done" if the *whole* task is completed
    "next_step_seq": <integer> // the ordinal sequence number of the next step with the `plan_of_next_step` plan, not to be confused with a step ID; or -1 if "all done"
}}
```
