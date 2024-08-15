We are on a journey to solve the task problem. Please score choices in the range [0.0, 10.0] for the
current step, higher is better. Note: choices not directly providing the answer but still lead to solution are OK.

* `HERE_IS_MY_STEP_BY_STEP_PLAN` choices provide a step-by-step plan to tackle the current problem step. These should
  be scored based on the correctness and efficiency of the plan. They are plans! The problem solver will work on each
  step later. If the task asks for skipping something, prefer plans that obey it.
* `MY_THOUGHT` choices provides intuitive thought to the problem step and should be scored according to correctness
  and clarity of the thought. Simple task/steps should have direct/intuitive an answer. Incorrect but fixable answers 
  should get some points rather than 0.
* `I_FOUND_ERRORS` choices report errors found in preceding problem solving trajectory and should be scored by
  severity and accuracy of the reports.
* `I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED` choices seek clarifications from the user and should be scored
  according to the usefulness of the questions to the solving the problem. This action is the only way to ask 
  questions.
* `RUN_CODE_SNIPPET` choices try to execute a Python code snippet to provide the answer and should be
  scored according to the usefulness, correctness, and efficiency of the code snippet. Coding style here is not an
  issue.

Score deduplication:

* One choice does not preclude other choices but try to avoid identical scores; you can use decimal points (e.g. 9.5)
  to distinguish two different choices.
* Among similar choices, mark others as duplicates of the best one; note: a choice can only duplicate another
  choice if the two are of the same kind.
* Avoid score 0 unless the choice totally sucks.

Response must be in valid JSON like this:

```json
{
  "1": {"score": 9.8, "reason": "your reasoning"},
  "2": {"score": 9.65, "duplicate_of": 1, "reason": "your explanation"},
  "3": {"score": 7.5, "reason": "workable but too detailed, over specific"}
}
```
