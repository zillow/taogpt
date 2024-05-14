These are prior issues found at step#{step_id} {step}:

{critic_text}

---

Please fix the issues and rewrite the **full** answer adding brief notes of what you fixed. Fix the issues to 
satisfaction, don't ignore or complain -- try your best instead. If an issue occurs in prior steps but affecting this 
one (an `affected:` issue,) update part of the answer here relating to the original issue while keeping other parts 
intact. If you disagree with the critic, explain with additional notes.

```markdown
<full answer>

Repair notes:
* <previous fix notes>
* <reported issue 1>: Fixed. <your explanation of the fix>
* <reported issue 2>: I disagree. It is not an issue because <your explanation>
* <affected issue 3>: I updated the answer by <your explanation>. Everything else is intact.
```

Orchestrator and user would not see the previous edits, so unchanged contents should be repeated verbatim. 

Do not add any phatic expressions.
