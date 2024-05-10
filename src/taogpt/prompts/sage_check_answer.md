{intent} Please verify concerns, determine severity of issues, and identify steps responsible for errors and 
warnings, but avoid nitpicking. Do NOT report intermittent errors that are fixed subsequently. We should generally 
respect user's assumptions even if they are inaccurate as assumptions are meant to simplify the problem. Respond using the following JSON template:

```json
{{
  "<what to verify>": {{
    "error": "<something incorrect with reasoning and recommendation>",
    "content": "<content snippet related to the issue",
    "blame": "step#<ID>: <step description>",
    "affecting": ["step#<ID>: <step description>", "step#<ID>: <step description>", ...]
  }},
  "<what to verify>": {{
    "warning": "<something can be improved with reasoning and recommendation>",
    "content": "<content snippet related to the issue",
    "blame": "step#<ID>: <step description>"
  }},
  "<what to verify>": {{"ok": "<this looks good>"}},
  // ...
}}
```

where `"step#<ID>: <step description>"` can be found in the bracket "[at step#<ID>: <step_description>]" of the steps 
(without the brackets.)

If a blamed step wrote/updated a file, also blame subsequent steps updating that file.
