{intent} Please verify concerns, determine severity of issues, and identify steps responsible for errors and 
warnings, but avoid nitpicking. 

* For any step, do NOT report issues that should be or already taken care of in subsequent/affected steps. For 
  example, dummy/placeholder/temporary values that are to be taken care of later.
* We should generally respect user's assumptions even if they are inaccurate as assumptions are meant to simplify 
  the problem.
* Subsequent steps depending on the issue should be reported an step as `affected` only if it must be 
  changed or fixed; if a step depends on this step but not on the particular issue, no need to report.

Respond using the following JSON template:

```json
{{
  "<what to verify>": {{
    "error": "<something incorrect with reasoning and recommendation>",
    "content": "<content snippet related to the issue",
    "blame": "step#<ID>: <step description>",
    "should_be_fixed_by": "step#<ID>: <step description>" or null,
    "fixed_in_subsequent_step": true or false,
    "affecting": ["step#<ID>: <step description>", "step#<ID>: <step description>", ...]
  }},
  "<what to verify>": {{
    "warning": "<something can be improved with reasoning and recommendation>",
    "content": "<content snippet related to the issue",
    "should_be_fixed_by": "step#<ID>: <step description>" or null,
    "fixed_in_subsequent_step": true or false,
    "blame": "step#<ID>: <step description>"
  }},
  "<what to verify>": {{"ok": "<this looks good>"}},
  // ...
}}
```

where `"step#<ID>: <step description>"` can be found in the bracket "[at step#<ID>: <step_description>]" of the steps 
(without the brackets.)
