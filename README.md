# TaoGPT: Template-guided Autoregressive Orchestrator for General Problem Tackling

<div style="text-align: center">

### From deep learning to deep thinking
![Tao-LLM](assets/LLM_tao.128x128.png)

</div>
<div style="text-align: center">


*In the essence of the Tao, where simplicity reigns and complexity falls away, there lies a path for the solver of 
problems. He who grasps the Tao seeks not to add but to subtract, to reduce each challenge to its core. With each 
step taken, the path unfolds; with each error found, wisdom grows. The master problem solver, like water, adapts, flowing around obstacles, finding the way with ease. In the art of the Tao, the solution is not forced but emerges naturally, as if it was always there, waiting to be uncovered by those who understand that to solve is to follow the Tao, effortlessly.*

-- [Self-pitch by TaoGPT](/examples/gpt-4-turbo/taogpt_self_pitch-steps.log.md)

</div>

## Introduction

(*This section [is written by TaoGPT](examples/gpt-4-turbo/taogpt_self_description-direct.log.md) with illustration by the authors.*)

![TaoGPT High-level design](assets/high_level_design.png)

Tao is an integral component of a sophisticated problem-solving system, designed to tackle issues in a structured and methodical manner. As a diligent problem solver, Tao is implemented by a large language model, which can either operate independently or in conjunction with another model. Tao's primary responsibility is to dissect problems recursively, working from the top down to ensure that each aspect of the issue is addressed thoroughly. This approach allows for a comprehensive understanding of the problem, enabling Tao to develop well-rounded and effective solutions.

The Orchestrator is the backbone of the system, a mechanical program that directs the workflow and ensures that each component operates within its designated role. It does not engage in problem-solving itself but is essential for maintaining the structure of the process. The Orchestrator initiates the problem-solving sequence by invoking Tao and subsequently calls upon Sage when a solution needs to be evaluated. This ensures that the process is not only systematic but also adheres to a high standard of quality control.

Sage serves as the system's analytical critic, providing a layer of scrutiny to the solutions proposed by Tao. Sage's role is to meticulously examine the strategies and solutions, offering constructive criticism and expert opinions. This critical analysis is vital for refining the problem-solving process, as it helps to identify any potential flaws or areas for improvement. Sage's feedback is then integrated into Tao's problem-solving approach, allowing for iterative enhancements. This collaborative dynamic between Tao and Sage, facilitated by the Orchestrator, ensures that the solutions are not only creative but also robust and reliable. The types of problems Tao might solve can range from technical issues to complex analytical tasks, and Sage's feedback is crucial in ensuring that the solutions are practical and applicable to real-world scenarios.

## Philosophy

In his seminal work, Nobel laureate Daniel Kahneman 
delineates [two distinct modes of thought](https://en.wikipedia.org/wiki/Thinking,_Fast_and_Slow): System 1 and System 2 
thinking. System 1 is characterized by fast, automatic, and subconscious processes, such as intuition and common 
sense. It is akin to the intuitive grasp of a situation or the effortless recall of memorized knowledge. In the 
realm of artificial intelligence, neural networks and large language models exemplify this type of thinking, as they 
draw upon learned patterns and data to make inferences, mimicking aspects of human intuition.

Conversely, System 2 thinking involves slow, deliberate, and conscious effort, often requiring logical and 
methodical reasoning. This mode of thought is exemplified by AI systems such as the medical diagnosis system MYCIN, 
the logic programming language Prolog, and IBM’s DeepBlue chess-playing program, all of which utilize complex 
algorithms to solve problems.

The integration of these two modes can lead to a powerful hybrid reasoning system. AlphaGo, the AI that famously 
defeated a human world champion in the game of Go, is a prime example of such a system. 
It [combines](https://en.wikipedia.org/wiki/AlphaGo#Algorithm) Monte Carlo Tree Search (MCTS) for systematic 
exploration and a neural network (the value network) trained to evaluate positions and predict outcomes, effectively 
blending intuitive pattern recognition with strategic planning.

Another instance of a hybrid system is [SOFAI](https://bdtechtalks.com/2022/01/24/ai-thinking-fast-and-slow/), which 
also leverages the strengths of both intuitive and analytical reasoning to tackle complex tasks.

This interplay between the two systems can be described as a "dynamic duality," where:

- Intuition can swiftly generate potential solutions with a limited number of reasoning steps.
- Intuition guides the prioritization of search branches, particularly in scenarios that lack clear-cut options, 
  such as many real-world problems.
- System 2's deep reasoning expands the realm of what can be achieved beyond the reach of intuition alone.
- Insights gained from systematic exploration can be assimilated, enriching intuition through continuous 
  learning/fine-tuning and memoization.
- While refined intuition can streamline the search process and (greatly) reduce cost of searching, it does not 
  eliminate the need for systematic exploration.
- Intuition can also decide when to cease searching, especially in situations where there is no straightforward 
  method to verify a solution.

The transition between System 1 and System 2 thinking can be illustrated through historical scientific understanding.
Initially, humans intuitively believed that the Sun orbited the Earth, a view that persisted until the 16th century. 
It was then that Nicolaus Copernicus (along with astronomers after him,) through meticulous reasoning and the 
application of mathematical and astronomical knowledge/insights, proposed the heliocentric model. Today, the 
knowledge that the Earth orbits the Sun is intuitively understood by most people, even though few can replicate the 
complex reasoning of the early astronomers.

![Duality of System 1 and System 2 reasoners](assets/taogpt-philosophy.png)

TaoGPT is a hybrid system built on top of large language models and thus are more general than specialized 
hybrid systems such as AlphaGo.

## Key Features and Methodology

(This is a high-level overview. More details will be presented later.)

### Key features

* One set of generic instruction prompt.
* Top-down recursive step-by-step problem solving. guided by simple templates.
* Flexible problem solving strategy and structure: encourage high-level abstract recursive strategies, but honor
  intuition and do not forbid iterative or out-of-plan steps.
* Fast-tracked repairing known as Targeted Repair or Improvement to Proposed Solution (TRIPS)
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

### Problem solving process

A problem solving session typically flows like:

1. User's task is presented to Tao
2. Orchestrator asks Tao to first analyze the task problem for issues and contradictions.
3. Orchestrator asks Tao to deliberate, one or more times, to solve the step. (Task problem is the root step.)
4. Tao replies using one of these strategies: answer directly, decompose into a step-by-step plan, interact with the 
   user or environment (e.g. asking clarification questions, executing python codes, etc.,) or give up due to error 
   found.
   1. Tao's response should be in the JSON template required by the Orchestrator. If the response is not in the 
      expected format, the Orchestrator informs Tao of the error and repeat the 
      deliberation for a confiurable number of times.
5. After receiving all deliberated approaches, Orchestrator asks Sage to rank and deduplicate the approaches.
   * Response error identification and correction is similar to step 4.1
6. Orchestrator select the next best approach and take appropriate actions
    * For asking user, present questions to user and solicit answers.
    * If Tao gives up, backtrack and try the next best approach.
    * For step-by-step plan, start with the first step in the plan and go to #3.
    * Else, find out from reply or ask Tao for the next step and go to #3.
7. If Tao's direct answer indicates final answer:
    1. Add a (retryable) summarization step to let Tao summarize the conversation into a final answer
    2. Ask Sage to verify the final answer.
       * Response error identification and correction is similar to step 4.1
    3. If Sage thinks the final answer is incorrect,
        1. ask Sage to identify the steps that cause errors.
        2. either repair the errors locally or backtrack directly to the first problematic step and go to #3.
    4. Else done

### Applications and Limitations

* This is a research work demonstrating the feasibility of the approach. Practical applicability is currently limited.
* TaoGPT is targeted for **general** problems rather than limiting to specific application domains, but prompts can 
  be tailored for specific domains. It provides file storage supports for programming task supports.
* TaoGPT is intended for more "complex" problems that require multi-level planning and searching, but it is up to 
  the LLM to decide whether to provide direct intuitive answer or embark on lengthy reasoning steps for any given task.
* LLM hallucination still presents challenges for the system. For example, TaoGPT often fails to solve a given 
  Sudoku 4x4 task because the LLM incorrectly believes a good solution has errors or vice versa.
* TaoGPT currently works best with GPT-4 and GPT-4-turbo. While GPT-3.5 is supported, it is found to be not intelligent 
  enough to work with the templates and instructions in most cases. Supports for other LLMs may be used via 
  OpenAI-compatible REST API adapters.
* Given the lengthy and backtrackable conversations necessary to solve problems, users should be mindful about token
  usages. TaoGPT sets the initial token usage limit to 10,000, check token consumptions at resumable check-points, and
  will ask user to grant more tokens if limit is exceeded.
* Maximum conversation context lengths in most LLMs including GPT-4 are quite low. This hinders TaoGPT's ability to
  work on large problem such as full blown implementation of an application project.

Some of these limitations and costs can be reduced over time as hardware availability, costs and performances improve.

## Examples

(The problem solving logs are markdown format with colored sections. Some Markdown viewers, such as those built in 
the git source control system, may remove `<div>`s used for coloring sections. For best viewing pleasure, it is 
recommended to view the log contents using a proper Markdown browser plugin.)

This a final problem solving chain showing TaoGPT tackling a travel planning task. The steps go through:

1. Analyze the task problem;
2. Ask user some questions for clarification;
3. Propose step-by-step plans;
4. Rank step-by-step plans;
5. Work on the best ranked step-by-step plan to come up with a feasible answer;
6. Summary into the final answer;
7. Check the final answer.

Comparing the TaoGPT, GPT-4 with the default system prompt produced
a [generic and vague response](/examples/gpt-4/travel-planning.default.md). The details of execution
log can be found [here](/examples/gpt-4/travel-planning.log.md).

More examples are in the [examples folder](/examples).


# Final path history

</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>: </div>

I want to travel to Moscow. I just need a route plan and I will do the booking later.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>Tao</b>: </div>

The problem statement does not contain any fundamental errors, invalid assumptions, or contradictions. The task is to create a route plan for a trip to Moscow, which is a feasible and straightforward request.

The successful completion of this task would be evaluated based on the following criteria:

1. The route plan should start from the requester's current location.
2. The route plan should end in Moscow.
3. The route plan should include all necessary transit points (airports, train stations, etc.).
4. The route plan should consider the most efficient and practical routes.
5. The route plan should provide alternatives, if possible, to accommodate any changes or preferences.
6. The route plan should not include the booking details as per the requester's preference.


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>user</b>: </div>

> Where is your current location?

Urumuqi.

> What is your preferred mode of transportation (air, rail, road)?

'm afraid of flying.

> Do you have any specific transit points or stops you would like to make along the way?

I like to visit Lahsa.

> Do you have any preferences for the route (scenic, fastest, cheapest, etc.)?

I like comfort and prefer fewer stopovers.



</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>Tao</b>: </div>


1. Identify the major transportation hubs (train stations, bus stations) in Urumuqi, Lahsa, and Moscow
2. Find the most direct and comfortable routes from Urumuqi to Lahsa
3. Find the most direct and comfortable routes from Lahsa to Moscow
4. Combine the best routes from Urumuqi to Lahsa and Lahsa to Moscow to create a complete route plan


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[4] <b>Tao</b>: </div>

The major transportation hubs in Urumuqi, Lahsa, and Moscow are as follows:

Urumuqi:
- Urumqi South Railway Station
- Urumqi Railway Station

Lahsa:
- Lhasa Railway Station

Moscow:
- Moscow Kazansky Railway Station
- Moscow Yaroslavsky Railway Station
- Moscow Kursky Railway Station

These stations have connections to major cities and regions, and they offer various types of trains, from high-speed to regular, to suit different travel preferences.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[5] <b>Tao</b>: </div>

The most direct and comfortable route from Urumuqi to Lahsa is by train. The train journey from Urumuqi to Lahsa takes approximately 24 hours. The train departs from Urumqi South Railway Station and arrives at Lhasa Railway Station. The train offers soft sleeper class, which is the most comfortable option. It includes four berths in each compartment with a door, providing a quiet and private space. The train also has a dining car where you can buy meals and drinks.

Please note that the travel time for each leg of the journey is an approximation and may vary depending on the specific train schedules. It is advised to check the actual train schedules when planning the trip.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[6] <b>Tao</b>: </div>

Based on the information gathered, here is your complete route plan:

1. Start from Urumuqi. Take a train from Urumuqi South Railway Station to Lhasa Railway Station. The journey takes approximately 24 hours. The train offers soft sleeper class for a comfortable journey.

2. From Lahsa, take a train to Beijing. The journey takes approximately 40 hours. The train offers soft sleeper class for a comfortable journey.

3. From Beijing, take a train to Moscow. The journey takes approximately 6 days. The train offers first-class sleeper for a comfortable journey.

Please note that the travel time for each leg of the journey is an approximation and may vary depending on the specific train schedules. It is advised to check the actual train schedules when planning the trip.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[7] <b>Tao</b>: </div>

Here is your complete route plan:

1. Start from Urumuqi South Railway Station and take a train to Lahsa. The journey will take approximately 24 hours. You will be travelling in a soft sleeper class for a comfortable journey.

2. After exploring Lahsa, head to Lhasa Railway Station and take a train to Beijing. This journey will take approximately 40 hours. Again, you will be travelling in a soft sleeper class for a comfortable journey.

3. From Beijing, take a train to Moscow. This journey will take approximately 6 days. You will be travelling in a first-class sleeper for a comfortable journey.

Please note that the actual travel time may vary depending on the specific train schedules.

As for the visa requirements, you will need to apply for a Chinese visa for your stops in Lahsa and Beijing. For your final destination, Moscow, you will need a Russian visa. Please check the specific requirements and application process for each visa at the respective embassies or consulates in your country. Safe travels!


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[8] <b>Tao</b>: </div>

Based on your preferences, I have created a route plan for your trip from Urumuqi to Moscow with a stopover in Lahsa. Here is the complete plan:

1. **Urumuqi to Lahsa**: Start from Urumuqi South Railway Station and take a train to Lahsa. The journey will take approximately 24 hours. You will be travelling in a soft sleeper class for a comfortable journey. The train offers four berths in each compartment with a door, providing a quiet and private space. The train also has a dining car where you can buy meals and drinks.

2. **Lahsa to Beijing**: After exploring Lahsa, head to Lhasa Railway Station and take a train to Beijing. This journey will take approximately 40 hours. Again, you will be travelling in a soft sleeper class for a comfortable journey.

3. **Beijing to Moscow**: From Beijing, take a train to Moscow. This journey will take approximately 6 days. You will be travelling in a first-class sleeper for a comfortable journey. The train offers two berths in each compartment with a door, providing a quiet and private space. The train also has a dining car where you can buy meals and drinks.

Please note that the actual travel time may vary depending on the specific train schedules. Also, remember to check the visa requirements for each country you will be passing through. Safe travels!


</div>

---

In [the detailed long log](examples/gpt-4/travel_advice-questions_steps.log.md), we can see that TaoGPT found 
multiple issues in the passes and fixed the issues (without backtracking since they are non-fatal for this task.)

### Comparing to GPT-4-turbo answer using system default prompt

(See [this example](examples/gpt-4-turbo/travel_advice.default.md))

**user:**

I want to travel to Moscow. I just need a detailed route plan.
(I don't need the actual schedule. And you don't have access to the internet.)

**assistant:**

Creating a detailed route plan to Moscow without access to the internet for real-time information is challenging, but I can provide you with a general outline of how you might plan your trip. The specifics, such as transportation schedules and availability, will need to be confirmed with the relevant providers or through research on your part.

**Step 1: Determine Your Starting Location**
The route to Moscow will vary greatly depending on your starting point. For this example, let's assume you are starting from New York City, USA.

**Step 2: Travel to the Airport**
- From within New York City, you can take a taxi, rideshare, or public transportation to John F. Kennedy International Airport (JFK), which is a major international airport with flights to Moscow.

**Step 3: Book a Flight to Moscow**
- You will need to book a flight from JFK to one of Moscow's international airports. The main airport is Sheremetyevo International Airport (SVO), but there are also flights to Domodedovo International Airport (DME) and Vnukovo International Airport (VKO).
- Direct flights are available, but depending on the airline and time of year, you may have to book a connecting flight.

**Step 4: Arrive in Moscow**
- Upon arrival in Moscow, you will go through customs and immigration. Make sure you have all the necessary visas and documentation required for entry into Russia.

**Step 5: Travel from the Airport to Your Accommodation**
- From the airport, you can take a taxi, airport express train, or bus to get to your accommodation in Moscow. The Aeroexpress train is a popular option for travel from SVO to the city center.

**Step 6: Getting Around Moscow**
- Moscow has an extensive and efficient metro system that can take you to most tourist destinations.
- You can also use buses, trams, taxis, or rideshare services to get around the city.

**Step 7: Sightseeing in Moscow**
- Plan your sightseeing itinerary. Some must-see attractions include the Kremlin, Red Square, St. Basil's Cathedral, the Bolshoi Theatre, and the Tretyakov Gallery.

**Step 8: Departure**
- When your visit is over, you will need to reverse your route to return to the airport and fly back to your starting location.

**Additional Tips:**
- Always check the visa requirements for Russia well in advance of your trip.
- Consider travel insurance for your journey.
- Learn some basic Russian phrases, as English is not widely spoken outside of tourist areas and hotels.
- Keep an eye on travel advisories and local news for any changes that might affect your travel plans.

Remember, this is a very general guide and you will need to fill in the details based on your specific circumstances and preferences. It's important to check the latest information on flights, local transportation, and entry requirements before you travel.

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
$ export OPENAI_API_KEY="...your OpenAI key..."
$ export OPENAI_API_BASE="https://api.openai.com/v1" # or you OPENAI_API_BASE URL
$ mkdir /tmp/taogpt_outputs # directory where output files go to.
$ taogpt -p /tmp/taogpt_outputs "What's the 51st fibonacci number?"
```

The command-line tool will print out (abbreviated) log in the console. A file logging the problem solving
progress and a file with the final step chain are written to the output directory; they are Markdown files viewable
by any Markdown viewer. Users are recommended to view the Markdown log files for better experiences. The directory also
contain any Tao-generated files organized by directory paths.

```shell
$ cat ~/my_openai.ini
[DEFAULT]
OPENAI_API_KEY=...your OpenAI key...
OPENAI_API_BASE=https://api.openai.com/v1

$ mkdir /tmp/taogpt_outputs # directory where output files go to.
$ taogpt -C ~/my_openai.ini -p /tmp/taogpt_outputs "I plan to relocate to San Francisco Bay Area next month. Where should I settle?"
```

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

The Responsible Artificial Intelligence Source Code License, Version 11

# Acknowledgements

This work is supported by the Data Science and Machine Learning Group at [Zillow Rentals](https://www.zillow.com/homes/for_rent/).

# Citation

Please cite our work if you reference to our work or use the data or code in this repo.

```
@software{taogpt,
  title = {TaoGPT},
  author = {Quock, Winston},
  url = {https://github.com/zillow/taogpt},
  version = {0.1.0},
  year = {2024},
  month = {04},
}
```
