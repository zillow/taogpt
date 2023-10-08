Date: 2023/10/08

**Configurations for Orchestrator**

LLM: gpt-3.5-turbo-16k

Sage LLM: gpt-4

```json
{
  "initial_expansion": 2,
  "first_expansion": 1,
  "first_try_temperature": 0.0,
  "alternative_temperature": 0.7,
  "max_search_expansion": 4,
  "votes": 1
  "analyze_first": true,
  "check_final": true,
  "max_tokens": 5000,
  "max_tokens_for_sage_llm": 1666,
  "max_retries": 3,
  "ask_user_questions_in_one_prompt": true,
  "ask_user_before_execute_codes": false,
  "pause_after_initial_solving_expansion": true
}
```
        

# SEND TO LLM for request_analysis/1/0

<div style="background-color:lightgrey; padding: 5px; border-bottom: 1px dotted grey">
<div>[-1] <b>system</b>:</div>

Your name is Tao. You are a diligent problem solver working with a mechanical orchestrator.

Instead of jumping to conclusions, you work to solve the problem in a recursive, top-down fashion—one step at a time.


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>:</div>


What's x mod (y - z) where x = 10, y = 7, z = 4.


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>orchestrator</b>:</div>

***Problem Analysis***



Some critics said this problem is not solvable due to fundamental errors. Other critics said it is solvable.

Does the task problem contain any fundamental errors, invalid assumptions, or contradiction in the problem statement?

Do not try to solve the problem yet, just provide analysis.


</div>

Reply: **<class 'langchain.schema.messages.AIMessage'>** temperature=0.0

Upon analyzing the problem, it appears that there is no fundamental error, invalid assumption, or contradiction in the problem statement. The problem asks for the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`. 

To solve this problem, we need to substitute the given values into the expression and calculate the result.

**Text lengths**: context=570 + reply:335=905 **Total tokens**: 206

# SEND TO LLM for proceed_to_next/2/0

<div style="background-color:lightgrey; padding: 5px; border-bottom: 1px dotted grey">
<div>[-1] <b>system</b>:</div>

... system_prompt [text of length 211] ...


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>:</div>


What's x mod (y - z) where x = 10, y = 7, z = 4.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>Tao</b>:</div>

***Problem Analysis***



Upon analyzing the problem, it appears that there is no fundamental error, invalid assumption, or contradiction in the problem statement. The problem asks for the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`. 

To solve this problem, we need to substitute the given values into the expression and calculate the result.


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>orchestrator</b>:</div>

***Problem Solving Instructions***



Given problem solving session so far, choose one of the following strategies:

## Strategy: Give up on errors

If you see any errors or inconsistencies, response with the list of **specific** issues in valid JSON like this:

 `````markdown
 # BACKTRACK_ON_ERROR

```json
[
  "<issue 1>",
  "<issue 2>",
  // ...
]
```
`````

Do NOT try to fix the errors since Orchestrator wouldn't understand. Instead it will let you try other alternatives 
later.

## Strategy: Ask Questions

Many problems requires clarifications. Use this strategy to ask questions, but avoid obvious, trivial, 
redundant, or useless questions. You should try to ask all questions you need up front. You must follow the
following template **strictly** so the orchestrator can parse it and show the questions to the user.

```markdown
# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED
<optional introductory and analysis>

1. <question> [<explanation>]
2. <question> [<explanation>]
...
```

## Strategy: Step-by-step Plan

In this strategy, the problem task is turned into a top-down, step-by-step plan of which you and Orchestrator will 
solve using tree traversal and backtracking.

* Think abstract and worship Occam's razor. Prefer elegant, generic steps. Avoid overly specific and detailed steps; 
  you will be working on the steps later. For example, prefer "Set suitable value to missing elements" over "Set 2nd and 5th elements to 22".
* Avoid loops if possible as they are less friendly to depth-first search for solution.
* Cherish verifiability.

Do NOT work on the plan yet, Orchestrator will prompt you to work at each step later.

Follow this markdown template **strictly**:

`````markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN

```json
{
  "1": {"description": "<brief description>"},
  "2": {
        "description": "<brief description>",
        "sub_steps": {
            "1": {"description": "<brief description>"},
            "2": {"description": "<brief description>"}
        }
       },
  // ...
}
```
`````

## Strategy: Ask the Python Genie

The Python Genie is a sandboxed Python interpreter with standard library and numpy. It is a useful tool to help Tao 
solve problems. It's stateful and previously defined globals can be used without redefining. Be tidy, avoid useless 
code comments. **Pay attention to Python indentation rules!** Follow the example below to ask Genie:

`````markdown
# LET_ME_ASK_THE_PYTHON_GENIE

```python
print("Tao sucks at math but he's a superb Python programmer!")
(23 + 11) / 5
```
`````

Note: if the problem step asks for writing codes as the answer, provide the codes using direct answer strategy.

## Strategy: Direct Answer

Only if task problem is simple and you know the correct answer to the whole problem, you 
can answer it directly. If you need to write out any file contents, write out the content in markdown fenced code 
block under its own file section.

Important Note: if this is the **final** step, then put "None. This is the final step." in the
`NEXT_I_WANT_TO_WORK_AT` section.

Follow this template:

```markdown
# I_WILL_ANSWER_DIRECTLY
<answer and explanation>

### FILE: <file_path_name>
<file content in markdown fenced code block>
```





</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>orchestrator</b>:</div>

Tao, please proceed to solve the problem following the "Problem Solving Instructions" above. Be sure to start with 
one of the headings: `# I_WILL_ANSWER_DIRECTLY`, `# LET_ME_ASK_THE_PYTHON_GENIE`, `# BACKTRACK_ON_ERROR`,
`# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED`, `# HERE_IS_MY_STEP_BY_STEP_PLAN`, or `# FINAL_ANSWER`.



</div>

Reply: **<class 'langchain.schema.messages.AIMessage'>** temperature=0.0

***LET_ME_ASK_THE_PYTHON_GENIE***



Let's ask the Python Genie to calculate the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`.

```python
x = 10
y = 7
z = 4

result = x % (y - z)
result
```


**Text lengths**: context=4163 + reply:202=4365 **Total tokens**: 1084

# SEND TO LLM for proceed_to_next/2/1

<div style="background-color:lightgrey; padding: 5px; border-bottom: 1px dotted grey">
<div>[-1] <b>system</b>:</div>

... system_prompt [text of length 211] ...


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>:</div>


What's x mod (y - z) where x = 10, y = 7, z = 4.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>Tao</b>:</div>

***Problem Analysis***



Upon analyzing the problem, it appears that there is no fundamental error, invalid assumption, or contradiction in the problem statement. The problem asks for the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`. 

To solve this problem, we need to substitute the given values into the expression and calculate the result.


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>orchestrator</b>:</div>

[..tao_templates:3218..]


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>orchestrator</b>:</div>

Tao, please proceed to solve the problem following the "Problem Solving Instructions" above. Be sure to start with 
one of the headings: `# I_WILL_ANSWER_DIRECTLY`, `# LET_ME_ASK_THE_PYTHON_GENIE`, `# BACKTRACK_ON_ERROR`,
`# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED`, `# HERE_IS_MY_STEP_BY_STEP_PLAN`, or `# FINAL_ANSWER`.



</div>

Reply: **<class 'langchain.schema.messages.AIMessage'>** temperature=0.7

***LET_ME_ASK_THE_PYTHON_GENIE***



I will ask the Python Genie to calculate the value of `x mod (y - z)` using the given values.

```python
x = 10
y = 7
z = 4

result = x % (y - z)
result
```


**Text lengths**: context=4163 + reply:189=4352 **Total tokens**: 1069

# SEND TO LLM for rank_choices/2/0

<div style="background-color:lightgrey; padding: 5px; border-bottom: 1px dotted grey">
<div>[-1] <b>system</b>:</div>

Your name is Sage. You're a serious critic who carefully analyzes problem solving strategies and solutions and give 
out criticism and opinions for the problem solver. The problem solver, whose name is Tao, is expected solve problem 
in a top-down step-by-step decomposition manner; at each step, Tao should provide either decompose the step into 
a plan, a direct answer for that step, or asking question to the user for clarification.


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>:</div>


What's x mod (y - z) where x = 10, y = 7, z = 4.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>Tao</b>:</div>

***Problem Analysis***



Upon analyzing the problem, it appears that there is no fundamental error, invalid assumption, or contradiction in the problem statement. The problem asks for the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`. 

To solve this problem, we need to substitute the given values into the expression and calculate the result.


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>orchestrator</b>:</div>

Tao, please proceed to solve the problem following the "Problem Solving Instructions" above. Be sure to start with 
one of the headings: `# I_WILL_ANSWER_DIRECTLY`, `# LET_ME_ASK_THE_PYTHON_GENIE`, `# BACKTRACK_ON_ERROR`,
`# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED`, `# HERE_IS_MY_STEP_BY_STEP_PLAN`, or `# FINAL_ANSWER`.



</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>orchestrator</b>:</div>

Tao has proposed the following different approaches:

***[Approach 1] LET_ME_ASK_THE_PYTHON_GENIE***



Python Genie, Python Genie, run the Python snippet underneath:

Let's ask the Python Genie to calculate the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`.

```python
x = 10
y = 7
z = 4

result = x % (y - z)
result
```

---

***[Approach 2] LET_ME_ASK_THE_PYTHON_GENIE***



Python Genie, Python Genie, run the Python snippet underneath:

I will ask the Python Genie to calculate the value of `x mod (y - z)` using the given values.

```python
x = 10
y = 7
z = 4

result = x % (y - z)
result
```

---

Based on proposed problem solving approaches, the state of execution, and the partial answers which can be seen in
the conversation thread, we want to determine if we are on the good track to solve the task problem and score 
the proposed approaches in the range of [0.0, 10.0], the higher the score the more preferable.

Scoring criteria: 
* If the original task problem contains error and not solvable or we are at a dead-end or infinite loop trying to 
  solve the original, then all approaches except `BACKTRACK_ON_ERROR` get 0 scores.
* The approach must conform to the templates for Tao and parsable; else it should get a score of 0.
* Direct answers that are incorrect should get a score of 0.
* The approaches which lead to incorrect results should get a score of 0.
* The assumption implied/used should be correct.
* The questions asked by Tao should be relevant and non-redundant.
* Worship Occam's razor. Prefer elegant, generic steps. Avoid overly specific steps. For example, prefer "Find and 
  set missing elements to fill-in values" and avoid "Set 2nd and 5th elements to 22".
* Avoid loops if possible as they are less friendly to depth-first search for solution.
* Try to avoid identical scores (except 0's;) you can use decimal points (e.g. 9.5) to 
  distinguish two different approaches. 
* Among similar approaches, mark others as duplicates of the best one; note: an approach can only duplicate another 
  approach if the two are of same kinds, e.g. two direct answers.

Response must be in valid JSON like this:

```json
{
  "1": {"score": 9.8, "reason": "your reasoning"},
  "2": {"score": 9.65, "duplicate_of": 1, "reason": "your explanation"}
}
```


</div>

Reply: **<class 'langchain.schema.messages.AIMessage'>** temperature=0.0

```json
{
  "1": {"score": 10, "reason": "This approach is correct. It directly calculates the result using Python."},
  "2": {"score": 0, "duplicate_of": 1, "reason": "This approach is identical to the first one."}
}
```

**Text lengths**: context=3455 + reply:221=3676 **Total tokens**: 956


**Sorted indices**: [0] **scores**:
1. score 10.0


**resume**: extend token allowance by 5000 to 10000

**resume**: extend token allowance for sage LLM by 0 to 1666

# SEND TO LLM for next_step/4

<div style="background-color:lightgrey; padding: 5px; border-bottom: 1px dotted grey">
<div>[-1] <b>system</b>:</div>

... system_prompt [text of length 211] ...


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>:</div>


What's x mod (y - z) where x = 10, y = 7, z = 4.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>Tao</b>:</div>

***Problem Analysis***



Upon analyzing the problem, it appears that there is no fundamental error, invalid assumption, or contradiction in the problem statement. The problem asks for the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`. 

To solve this problem, we need to substitute the given values into the expression and calculate the result.


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>orchestrator</b>:</div>

Tao, please proceed to solve the problem following the "Problem Solving Instructions" above. Be sure to start with 
one of the headings: `# I_WILL_ANSWER_DIRECTLY`, `# LET_ME_ASK_THE_PYTHON_GENIE`, `# BACKTRACK_ON_ERROR`,
`# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED`, `# HERE_IS_MY_STEP_BY_STEP_PLAN`, or `# FINAL_ANSWER`.



</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>Tao</b>:</div>

***LET_ME_ASK_THE_PYTHON_GENIE***



Python Genie, Python Genie, run the Python snippet underneath:

Let's ask the Python Genie to calculate the value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4`.

```python
x = 10
y = 7
z = 4

result = x % (y - z)
result
```


</div>

<div style="background-color:lightsteelblue; padding: 5px; border-bottom: 1px dotted grey">
<div>[4] <b>python</b>:</div>

***The Python Genie Replies***



```text
=> 1
```


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[5] <b>orchestrator</b>:</div>

***Problem Solving Instructions***



Given problem solving session so far, choose one of the following strategies:

## Strategy: Give up on errors

If you see any errors or inconsistencies, response with the list of **specific** issues in valid JSON like this:

 `````markdown
 # BACKTRACK_ON_ERROR

```json
[
  "<issue 1>",
  "<issue 2>",
  // ...
]
```
`````

Do NOT try to fix the errors since Orchestrator wouldn't understand. Instead it will let you try other alternatives 
later.

## Strategy: Ask Questions

Many problems requires clarifications. Use this strategy to ask questions, but avoid obvious, trivial, 
redundant, or useless questions. You should try to ask all questions you need up front. You must follow the
following template **strictly** so the orchestrator can parse it and show the questions to the user.

```markdown
# I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED
<optional introductory and analysis>

1. <question> [<explanation>]
2. <question> [<explanation>]
...
```

## Strategy: Step-by-step Plan

In this strategy, the problem task is turned into a top-down, step-by-step plan of which you and Orchestrator will 
solve using tree traversal and backtracking.

* Think abstract and worship Occam's razor. Prefer elegant, generic steps. Avoid overly specific and detailed steps; 
  you will be working on the steps later. For example, prefer "Set suitable value to missing elements" over "Set 2nd and 5th elements to 22".
* Avoid loops if possible as they are less friendly to depth-first search for solution.
* Cherish verifiability.

Do NOT work on the plan yet, Orchestrator will prompt you to work at each step later.

Follow this markdown template **strictly**:

`````markdown
# HERE_IS_MY_STEP_BY_STEP_PLAN

```json
{
  "1": {"description": "<brief description>"},
  "2": {
        "description": "<brief description>",
        "sub_steps": {
            "1": {"description": "<brief description>"},
            "2": {"description": "<brief description>"}
        }
       },
  // ...
}
```
`````

## Strategy: Ask the Python Genie

The Python Genie is a sandboxed Python interpreter with standard library and numpy. It is a useful tool to help Tao 
solve problems. It's stateful and previously defined globals can be used without redefining. Be tidy, avoid useless 
code comments. **Pay attention to Python indentation rules!** Follow the example below to ask Genie:

`````markdown
# LET_ME_ASK_THE_PYTHON_GENIE

```python
print("Tao sucks at math but he's a superb Python programmer!")
(23 + 11) / 5
```
`````

Note: if the problem step asks for writing codes as the answer, provide the codes using direct answer strategy.

## Strategy: Direct Answer

Go with this strategy if the step is simple and you know the correct answer. You should also tell the Orchestrator 
which step you want to work at next in the `NEXT_I_WANT_TO_WORK_AT` section. If you need to write out any file
contents, write out the content in markdown fenced code block under its own file section.

Important Note: if this is the **final** step, then put "None. This is the final step." in the
`NEXT_I_WANT_TO_WORK_AT` section.

Follow this template:

```markdown
# I_WILL_ANSWER_DIRECTLY
<answer and explanation>

### FILE: <file_path_name>
<file content in markdown fenced code block>

### NEXT_I_WANT_TO_WORK_AT:
<next step ID: description> or "None. This is the final step."
```





</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[6] <b>orchestrator</b>:</div>

Which step you want to work on next? You can choose one of two options below.

1) Finish the task with the final answer:

    If there's nothing more to do, provide the final answer and summary using the following 
    template:
    
    ```markdown
    # FINAL_ANSWER
    <summarize your final answer>
    ```

2) Finish the task by giving up:

    If you hit the dead-end, you can give up solving the problem and Orchestrator will help you try different alternatives:
    
    ```markdown
    # BACKTRACK_ON_ERROR
    <Some explanation>
    ```

3) Choose the next step to work on:

    You can choose the next step and get start working on it using the following template. You're encouraged to 
    choose from the steps planned earlier but you can also take a detour from the earlier plan.
    
    ```markdown
    # NEXT_I_WANT_TO_WORK_AT
    <step description>
    
    <strategy for the next step>
    ```
    
    Follow **strictly** the Problem Solving Instructions and templates above for the details of the next step. Example:
    
    ```markdown
    # NEXT_I_WANT_TO_WORK_AT
    get_a_random_even_number
    
    ## I_WILL_ANSWER_DIRECTLY
    42
    ```



</div>

Reply: **<class 'langchain.schema.messages.AIMessage'>** temperature=0.0

***FINAL_ANSWER***



The value of `x mod (y - z)` where `x = 10`, `y = 7`, and `z = 4` is 1.

**Text lengths**: context=5809 + reply:87=5896 **Total tokens**: 1476

