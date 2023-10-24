# ![Tao-LLM](assets/LLM_tao.24x24.png) TaoGPT: Template-guided Autoregressive Orchestrator for General Problem Tackling

<div style="text-align: center">

### An AI Assistant which incidentally runs on ChatGPT 4

</div>
<div style="text-align: center">


*The Tao gives birth to One. One gives birth to Two. Two gives birth to Three.
Three gives birth to all things. -- Tao Te Ching. (Quote [selected by TaoGPT](examples/gpt-4/taogpt-quote.log.md))*

"Knowing others is wisdom, knowing yourself is Enlightenment." In the dance of problem-solving, be like water—flexible yet persistent, yielding yet powerful. Embrace the Tao of adaptability, yielding to the natural flow of each unique challenge. Respect the intrinsic nature, do not force, do not impose. For the enlightened problem solver, errors are but stepping stones on the path to truth, each misstep an opportunity to backtrack, to learn, to grow. So, like the eternal Tao, the way of problem-solving is not set in stone, but ebbs and flows with the rhythm of wisdom and enlightenment.

-- [Self-pitch by TaoGPT](/examples/gpt-4/taogpt-self-pitch.final.md)

</div>

## Introduction

(*This section [is written by TaoGPT](examples/gpt-4/taogpt-self-describe.log.md).*)

The problem-solving system is a collaborative platform designed to tackle complex problems in a structured and systematic manner. It leverages the unique strengths of three key components: Tao, Orchestrator, and Sage.

Tao is the diligent problem solver in this system. His primary role is to solve problems in a recursive, top-down fashion. He takes one step at a time, ensuring that each step is thoroughly analyzed and solved before moving on to the next. Tao's responsibilities include understanding the problem at hand, breaking it down into manageable steps, and working through each step methodically. He is also responsible for communicating his progress and findings to the Orchestrator and Sage, and for incorporating their feedback into his problem-solving process.

The Orchestrator is the guiding force in this problem-solving system. Its primary role is to provide workflow guidance, ensuring that the problem-solving process is structured and systematic. The Orchestrator's responsibilities include invoking Sage at appropriate times to analyze Tao's problem-solving strategies and solutions. It also manages the interaction between Tao and Sage, ensuring that their collaboration is effective and productive.

Sage is the critic in this problem-solving system. Its primary role is to carefully analyze the problem-solving strategies and solutions proposed by Tao. Sage provides criticism and opinions, helping to refine and improve the problem-solving process. Sage's responsibilities include scrutinizing Tao's problem-solving steps, identifying potential errors or inefficiencies, and providing constructive feedback.

The interaction between Tao, Orchestrator, and Sage is a crucial aspect of this problem-solving system. The Orchestrator manages the interaction between Tao and Sage, invoking Sage at appropriate times to analyze Tao's problem-solving strategies and solutions. Sage scrutinizes Tao's problem-solving steps and provides constructive feedback, which is communicated back to Tao through the Orchestrator, helping Tao to refine his problem-solving process.

This system is designed to facilitate effective problem-solving by breaking down complex problems into manageable steps, encouraging critical analysis, and promoting collaboration.

## Methodology and Key Features

(This is a high-level overview. More details will be presented later.)

A problem solving session typically flows like:

1. User's task is presented to Tao
2. Orchestrator asks Tao to first analyze the task problem for issues and contradictions.
3. Orchestrator asks Tao to come up with one or more approaches to solve the step. (Task problem is the root step.)
4. Tao can reply with one of these strategies: answer directly, decompose into a step-by-step plan, ask user for
   clarifications, or give up due to error found.
5. After receiving all approaches, Orchestrator asks Sage to rank and deduplicate the approaches.
6. Orchestrator select the next best approach and take appropriate actions
   * For asking user, present questions to user and solicit answers.
   * If Tao gives up, backtrack and try the next best approach.
   * For step-by-step plan, start with the first step in the plan and go to #3.
   * Else, find out from reply or ask Tao for the next step and go to #3.
7. If Tao's direct answer indicates final answer:
   1. Add a (retryable) summarization step to let Tao summarize the conversation into a final answer
   2. Ask Sage to verify the final answer.
   3. If Sage thinks the final answer is incorrect,
      1. ask Sage to identify the steps that cause errors.
      2. backtrack directly to the first problematic step and go to #3.
   4. Else done

### Key features

* One set of generic instruction prompt.
* Top-down recursive step-by-step problem solving.
* Flexible problem solving strategy and structure: encourage high-level abstract recursive strategies, but honor
  intuition and do not forbid iterative or out-of-plan steps.
* Fast-tracked backtracking.
* Multiple opportunities to correct errors.

### Technical features

* LLM token usage limiting and optimization to guard against out-of-control token usages.
* Resumable execution (when token limit is reached.)
* Tao can take use of writing Python codes for the purpose of solving the problem (even if the problem's answer does
  not need program codes.) The sandbox environment is known as the Python Genie to Tao.
* File generation support: Tao can generate files as part of the answer and the files are collected
  and saved.
* Multi-LLM support: in order to lower LLM costs, it is possible to configure TaoGPT to use different LLMs for
  different needs during problem solving. For example, one could use gpt-3.5 for Tao while gpt-4 for Sage. Also long
  context LLM can be configured to use when the context length exceeds a certain limit. For example, gpt-4-32k is
  used in place of gpt-4 when the context exceeds 3000 tokens.

### Limitations

* TaoGPT currently works best with GPT-4. While GPT-3.5 is supported, it is found to be not intelligent enough to
  work with the templates and instructions in most cases. Supports for other LLMs can be added in the future.
* Given the lengthy and backtrackable conversations necessary to solve problems, users should be mindful about token
  usages. TaoGPT sets the initial token usage limit to 10,000, check token consumptions at resumable check-points, and
  will ask user to grant more tokens if limit is exceeded.
* Maximum conversation context lengths in most LLMs including GPT-4 are quite low. This hinders TaoGPT's ability to
  work on large problem such as full blown implementation of an application project.

Some of these limitations and costs can be reduced over time as hardward availability, costs and performances improve.

## Examples

(The problem solving logs are markdown format with colored sections. Some Markdown viewers, such as those built in 
the git source control system, may remove `<div>`s used for coloring sections. For best viewing pleasure, it is 
recommend to view the log contents using a proper Markdown browser plugin.)

This a final problem solving chain showing TaoGPT tackling a travel planning task. The steps go through:

1. Analyze the task problem;
2. Ask user some questions for clarification;
3. Propose step-by-step plans;
4. Rank step-by-step plans;
5. Work on the best ranked step-by-step plan to come up with a feasible answer;
6. Optimize the answer;
7. Summary into the final answer;
8. Check the final answer.

Comparing the TaoGPT, GPT-4 with the default system prompt produced
a [generic and vague response](/examples/gpt-4/travel-planning.default.md). The details of execution
log can be found [here](/examples/gpt-4/travel-planning.log.md).

More examples are in the [examples folder](/examples).

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>:</div>

I want to travel to Moscow. Find me a travel route.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>Tao</b>:</div>

***Problem Analysis***

The problem statement does not contain any fundamental errors, invalid assumptions, or contradictions. However, it lacks specific details that would help in providing a more accurate solution. For instance, the starting location is not mentioned. The mode of transportation is also not specified. Are we considering air travel, road, or rail? These details would be crucial in providing a more accurate travel route.

</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>user</b>:</div>

***Tao asked and user replied:***

> Where are you currently located? [This is crucial for determining the starting point of the journey]

Urumuqi

> What is your preferred mode of travel? (Air, rail, road) [Each mode of transport might offer different routes]

I'm afraid of flying.

> Are there any specific places you would like to visit on your way to Moscow? [This will help in tailoring a personalized travel route]

Chongqing

> Do you have any particular time constraints? [This will assist in planning the travel schedule accordingly]

I'm flexible.

> Do you prefer direct routes or are layovers acceptable? [Direct routes might be faster but potentially more expensive]

OK with layovers but prefer fewer.

> Are you traveling alone or with others? [This could affect the feasibility of certain travel options]

Alone.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>Tao</b>:</div>

***HERE_IS_MY_STEP_BY_STEP_PLAN***

```json
{
  "1": {
    "description": "Identify major cities or transit points between Urumqi and Chongqing"
  },
  "2": {
    "description": "Identify feasible travel routes from Urumqi to Chongqing using non-air travel methods, considering the transit points identified in step 1"
  },
  "3": {
    "description": "Identify major cities or transit points between Chongqing and Moscow"
  },
  "4": {
    "description": "Identify feasible travel routes from Chongqing to Moscow using non-air travel methods, considering the transit points identified in step 3"
  },
  "5": {
    "description": "Combine the selected routes from steps 2 and 4 to form a complete travel plan from Urumqi to Moscow via Chongqing"
  },
  "6": {
    "description": "Considering the user's preference for fewer layovers, select the best route from the options identified in step 5"
  },
  "7": {
    "description": "Present the selected route to the user"
  }
}
```

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[4] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: Identify major cities or transit points between Urumqi and Chongqing]

The first step is to identify major cities or transit points between Urumqi and Chongqing. Considering the user's preference for non-air travel, we can consider major cities connected by rail or road.

Some of the major cities between Urumqi and Chongqing are Lanzhou, Xi'an, and Chengdu. These cities are well connected by the Chinese high-speed rail network and can serve as potential transit points.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[5] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: Identify feasible travel routes from Urumqi to Chongqing using non-air travel methods, considering the transit points identified in step 1]

Given the major cities identified in the previous step (Lanzhou, Xi'an, and Chengdu), we can now identify feasible travel routes from Urumqi to Chongqing using non-air travel methods.

1. Urumqi to Lanzhou: The most direct route is by train, which takes approximately 20 hours. There are several trains daily.
2. Lanzhou to Xi'an: Again, the most direct route is by train, which takes approximately 9 hours. There are numerous trains daily.
3. Xi'an to Chengdu: The high-speed train is the most convenient option, taking approximately 4 hours. There are numerous trains daily.
4. Chengdu to Chongqing: The high-speed train is the most convenient option, taking approximately 2 hours. There are numerous trains daily.

These routes provide a feasible travel plan from Urumqi to Chongqing using non-air travel methods, with layovers in Lanzhou, Xi'an, and Chengdu.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[6] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: Identify major cities or transit points between Chongqing and Moscow]

The next step is to identify major cities or transit points between Chongqing and Moscow. Considering the user's preference for non-air travel, we can consider major cities connected by rail or road.

Some of the major cities between Chongqing and Moscow are Ulaanbaatar in Mongolia, Irkutsk and Novosibirsk in Russia. These cities are well connected by the Trans-Siberian Railway and can serve as potential transit points.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[7] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: Identify feasible travel routes from Chongqing to Moscow using non-air travel methods, considering the transit points identified in step 3]

Given the major cities identified in the previous step (Ulaanbaatar, Irkutsk, and Novosibirsk), we can now identify feasible travel routes from Chongqing to Moscow using non-air travel methods.

1. Chongqing to Beijing: The most direct route is by train, which takes approximately 12 hours. There are several trains daily.
2. Beijing to Ulaanbaatar: The Trans-Mongolian Railway is the most convenient option, taking approximately 30 hours. There are weekly trains.
3. Ulaanbaatar to Irkutsk: The Trans-Mongolian Railway continues to be the most convenient option, taking approximately 24 hours. There are weekly trains.
4. Irkutsk to Novosibirsk: The Trans-Siberian Railway is the most convenient option, taking approximately 30 hours. There are daily trains.
5. Novosibirsk to Moscow: The Trans-Siberian Railway continues to be the most convenient option, taking approximately 40 hours. There are daily trains.

These routes provide a feasible travel plan from Chongqing to Moscow using non-air travel methods, with layovers in Beijing, Ulaanbaatar, Irkutsk, and Novosibirsk.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[8] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: Combine the selected routes from steps 2 and 4 to form a complete travel plan from Urumqi to Moscow via Chongqing]

Now that we have identified feasible travel routes from Urumqi to Chongqing and from Chongqing to Moscow, we can combine these routes to form a complete travel plan.

Here is the complete travel plan:

1. Urumqi to Lanzhou by train (approximately 20 hours)
2. Layover in Lanzhou
3. Lanzhou to Xi'an by train (approximately 9 hours)
4. Layover in Xi'an
5. Xi'an to Chengdu by train (approximately 4 hours)
6. Layover in Chengdu
7. Chengdu to Chongqing by train (approximately 2 hours)
8. Layover in Chongqing
9. Chongqing to Beijing by train (approximately 12 hours)
10. Layover in Beijing
11. Beijing to Ulaanbaatar by Trans-Mongolian Railway (approximately 30 hours)
12. Layover in Ulaanbaatar
13. Ulaanbaatar to Irkutsk by Trans-Mongolian Railway (approximately 24 hours)
14. Layover in Irkutsk
15. Irkutsk to Novosibirsk by Trans-Siberian Railway (approximately 30 hours)
16. Layover in Novosibirsk
17. Novosibirsk to Moscow by Trans-Siberian Railway (approximately 40 hours)

This travel plan takes into account the user's preference for non-air travel and fewer layovers. It also includes a visit to Chongqing as requested by the user.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[9] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: Considering the user's preference for fewer layovers, select the best route from the options identified in step 5]

Given the travel plan from Urumqi to Moscow via Chongqing, we have a total of 7 layovers (Lanzhou, Xi'an, Chengdu, Beijing, Ulaanbaatar, Irkutsk, and Novosibirsk).

However, considering the user's preference for fewer layovers, we can try to reduce this number. One way to do this is to eliminate some of the layovers in China, as the high-speed rail network in the country is extensive and can accommodate long-distance travel without the need for multiple stops.

Here is the revised travel plan with fewer layovers:

1. Urumqi to Chongqing by train (direct, with a duration of approximately 36 hours)
2. Layover in Chongqing
3. Chongqing to Beijing by train (direct, with a duration of approximately 12 hours)
4. Layover in Beijing
5. Beijing to Ulaanbaatar by Trans-Mongolian Railway (approximately 30 hours)
6. Layover in Ulaanbaatar
7. Ulaanbaatar to Irkutsk by Trans-Mongolian Railway (approximately 24 hours)
8. Layover in Irkutsk
9. Irkutsk to Moscow by Trans-Siberian Railway (direct, with a duration of approximately 70 hours)

This revised plan reduces the number of layovers from 7 to 5, which aligns better with the user's preference.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[10] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: Present the selected route to the user]

The selected route for your travel from Urumqi to Moscow via Chongqing, considering your preferences for non-air travel and fewer layovers, is as follows:

1. Urumqi to Chongqing by train (direct, with a duration of approximately 36 hours)
2. Layover in Chongqing
3. Chongqing to Beijing by train (direct, with a duration of approximately 12 hours)
4. Layover in Beijing
5. Beijing to Ulaanbaatar by Trans-Mongolian Railway (approximately 30 hours)
6. Layover in Ulaanbaatar
7. Ulaanbaatar to Irkutsk by Trans-Mongolian Railway (approximately 24 hours)
8. Layover in Irkutsk
9. Irkutsk to Moscow by Trans-Siberian Railway (direct, with a duration of approximately 70 hours)

Please note that the duration of the train rides is approximated and might vary slightly. Also, as you will be crossing several time zones on your journey, it is advisable to adjust your schedule accordingly to avoid jet lag.

Safe travels!

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[11] <b>Tao</b>:</div>

***I_WILL_ANSWER_DIRECTLY***

[at step: 7: Present the selected route to the user.]

Based on your preferences for non-air travel and fewer layovers, here is your travel route from Urumqi to Moscow via Chongqing:

1. Urumqi to Chongqing by train (direct, with a duration of approximately 36 hours)
2. Layover in Chongqing
3. Chongqing to Beijing by train (direct, with a duration of approximately 12 hours)
4. Layover in Beijing
5. Beijing to Ulaanbaatar by Trans-Mongolian Railway (approximately 30 hours)
6. Layover in Ulaanbaatar
7. Ulaanbaatar to Irkutsk by Trans-Mongolian Railway (approximately 24 hours)
8. Layover in Irkutsk
9. Irkutsk to Moscow by Trans-Siberian Railway (direct, with a duration of approximately 70 hours)

Please note that the duration of the train rides is approximated and might vary slightly. Also, as you will be crossing several time zones on your journey, it is advisable to adjust your schedule accordingly to avoid jet lag.

Safe travels!

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[12] <b>Tao</b>:</div>

***Tao's Final Answer***

[at step: 7: Present the selected route to the user.]

Based on your preferences for non-air travel and fewer layovers, here is your final travel route from Urumqi to Moscow via Chongqing:

1. Urumqi to Chongqing by train (direct, with a duration of approximately 36 hours)
2. Layover in Chongqing
3. Chongqing to Beijing by train (direct, with a duration of approximately 12 hours)
4. Layover in Beijing
5. Beijing to Ulaanbaatar by Trans-Mongolian Railway (approximately 30 hours)
6. Layover in Ulaanbaatar
7. Ulaanbaatar to Irkutsk by Trans-Mongolian Railway (approximately 24 hours)
8. Layover in Irkutsk
9. Irkutsk to Moscow by Trans-Siberian Railway (direct, with a duration of approximately 70 hours)

Please note that the duration of the train rides is approximated and might vary slightly. Also, as you will be crossing several time zones on your journey, it is advisable to adjust your schedule accordingly to avoid jet lag.

Safe travels!

</div>

### Comparing to GPT-4 answer using system default prompt

Default prompt: "You're a helpful assistant."

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">

**user**:

I want to travel to Moscow. Find me a travel route.

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">

**gpt-4**:

I'm sorry for the confusion, but I actually can't help with travel routes or booking travel as my current capabilities are limited to mathematical calculations. I recommend using travel websites or applications which can assist in finding the most suitable route and means of travel to Moscow from your current location. They can provide real-time data, cost estimates, different transportation alternatives, and more.

</div>

# Installation

### Install via pip

From local git check-out to path `taogpt`:

```shell
pip install path/to/taogpt/
```

**Sandboxing Python environment**: Tao can execute Python codes as a tool to solve problem. By default, the user will
be prompted before a code snippet is executed. It is highly recommended that TaoGPT be installed in a virtual
machine (docker) for ultimate security.

# Usages

## Command-line interface

To show help:

```shell
taogpt --help
```

Example command-line invocation with a simple arithmetic problem:

```shell
mkdir /tmp/taogpt_outputs # directory where output files go to.
taogpt -p /tmp/taogpt_outputs -llm gpt-3.5 --sage-llm=gpt-4 "What's x mod (y - z) where x = 10, y = 7, z = 4."
```

The command-line tool will print out (abbreviated) log in the console. A file logging the problem solving
progress and a file with the final step chain are written to the output directory; they are Markdown files viewable
by any Markdown viewer. Users are recommended to view the Markdown log files for better experiences. The directory also
contain any Tao-generated files organized by directory paths.

## Web UI interface

*TBA*

## Inspirations

Formal citations will be provided with pending publications. Here are some prior arts inspiring TaoGPT:

* Chain of Thought
* ReACT
* Tree of Thoughts
* Graph of Thoughts
* ToolLLM

# Publications

*Pending*

# License

Apache License 2.0

# Citation

Please consider citing our work if you use the data or code in this repo.

```
@software{taogpt,
  title = {TaoGPT},
  author = {Quock, Winston},
  url = {https://github.com/TBD/TaoGPT},
  version = {pre-release},
  year = {2023},
  month = {10},
}
```
