Format the above step-by-step plan in a JSON fenced block:

```json
{{
  "1": {{
    "description": "<high-level description without details>", 
    "recursive": true or false, // is this sub-step recursive of the parent
    "difficulty": 1 to 10, // level of difficulty; 10 is most difficult
    "sub_steps": {{
        // ... nested sub-tasks ...
    }}
  }},
  "2": {{ ... }},
  // ...
  "branching_among_steps": true or false, // does this plan contain any conditional branching or early stopping/breaking AMONG its peer steps?
  "looping_among_steps": true or false // does this plan contain any loop AMONG its peer steps?
}}
```
