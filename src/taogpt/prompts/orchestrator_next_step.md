Which step you want to work on next? You can choose one of two options below.

1) Finish the task with the final answer:

    If there's nothing more to do, declare you're done and provide the final answer and summary using the following 
    template:
    
    ```markdown
    I'm done.
    
    ## FINAL_ANSWER
    <summarize your final answer>
    ```

2) Finish the task by giving up:

    If you hit the dead-end, you can give up solving the problem and Orchestrator will help you try different alternatives:
    
    ```markdown
    I'm done.
    
    ## UNSOLVABLE_I_GIVE_UP
    <Some explanation>
    ```

3) Choose the next step to work on:

    You can choose the next step to work on using the following template. You do not proceed to work on that step yet; 
    orchestrator will guide you later. You're encouraged to choose from the steps planned earlier but you can also 
    take a detour from the earlier plan.
    
    ```markdown
    I want to work on: <step description>
    
    <strategy for the next step>
    ```
    
    Follow the strategy-selection instruction above for the details of the next step. Example:
    
    ```markdown
    I want to work on: get_a_random_even_number
    
    # HERE_IS_MY_STEP_BY_STEP_PLAN
    1. roll the dice
    2. multiply the number by 2
    ```

