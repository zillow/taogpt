### Bad response examples ###
```markdown
Let'me try to answer this.
I like to be lucky.

13

### NEXT_I_WANT_TO_WORK_AT:

```
Template violations:
* missing heading "I_WILL_ANSWER_THIS_STEP_DIRECTLY".
* missing description of the next step.

```markdown
I need to ask some questions.

## MY_QUESTIONS:
1. What did you eat for dinner?

## MY_QUESTIONS:
1. do you have a dog?
```
Template violations:
* looks like a "ask question" response but missing heading "I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED".
* free text outside of sections.
* multiple questions sections.

### Good response examples ###
```markdown
# I_WILL_ANSWER_THIS_STEP_DIRECTLY
It is the lucky number: 13

### NEXT_I_WANT_TO_WORK_AT:
roll the dice again.
```

```markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN
This will be fun!

1. Initialize v = n [initial setup]
2. Update v = v * (v - 1) and n = n - 1.
3. Repeat until n = 0
```
