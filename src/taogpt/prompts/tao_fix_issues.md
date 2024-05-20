These are prior issues found at step#{step_id} {step}:

{critic_text}

---

Please fix the issues and rewrite the **full** answer adding brief notes of what you fixed. Fix the issues to 
satisfaction with real changes, don't ignore or make phantom changes. If an issue occurs in prior steps but 
affecting this one (an `affected:` issue,) update part of the answer here relating to the original issue while 
keeping other parts intact. If you disagree with the reported issue, explain with additional notes.

```markdown
<full answer>

Repair notes:
* <repeat any previous fix notes>
* <description of issue 1>: Fixed. <your explanation of the fix>
* <description of issue 2>: I disagree. It is not an issue because <your explanation>
* <description of affected issue 3>: I updated the answer by <your explanation>. Everything else is intact.
```

Orchestrator and user would not see the previous edits, so unchanged contents should be repeated verbatim. 

Do not add any phatic expressions.
