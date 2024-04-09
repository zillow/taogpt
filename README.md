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

AI agent can be categorized into three main types of reasoning systems: System 1 reasoner, System 2 reasoner, and the 
Hybrid reasoner. The System 1 reasoner relies on memorized knowledge, common sense, and intuition, often described 
as the "black arts". Notable examples of this system include neural networks and large language models in particular.

On the other end of the spectrum, we have the System 2 reasoner that employs complex reasoning process. Classic 
cases include the medical diagnosis system MYCIN, logic programming language Prolog, and IBM’s DeepBlue chess-playing 
program.

Hybrid reasoning, as the name suggests, is the marriage between the System 1 and System 2 reasoners. In other words, 
it uses search and backtracking guided by intuition. One of the well-known instances of hybrid reasoner is AlphaGo, 
the first AI to beat a human world champion Go player. AlphaGo employs systematic search techniques under the 
guidance of its intuition (developed through learning) to make the best move decisions and judge board situation.

Dynamic duality is a key characteristic of intelligent reasoning in a hybrid system:

* Intuition can produce answers with some (shallow) reasoning steps;
* Intuition generates search branches and ranks them for problems without mechanical branching such as non-board 
  games and most real-world problems;
* Deep search of the System 2 reasoning process extends capability unreachable by intuition;
* Knowledge revealed by searching can be internalized to become intuition through (continuous) learning and memoization;
* Better intuition reduces search cost but never replace searching
* Intuition can decide the halting of a search for problems without mechanical verification such as non-board
  games and most real-world problems.

This philosophy can be depicted in the illustration below. The knowledge that the Earth orbits the Sun is an obvious 
example of transitions between System 1 and 2. Human beings, relying solely on daily intuition, had believed the Sun 
orbited the Earth until Nicolas Copernicus discovered the opposite arrangement, through elaborated reasoning using his 
knowledge and insights of math and astronomy, and confirmed by scientists after him. Today, most human beings have 
the intuitive knowledge that the Earth orbits the Sun, even though few of them can actually perform the same 
elaborated reasoning the pioneering scientists did.

![Duality of System 1 and System 2 reasoners](assets/taogpt-philosophy.png)

TaoGPT strikes to be a hybrid system that embraces and implements the duality of System 1 and System 2 reasoners.

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
6. Optimize the answer;
7. Summary into the final answer;
8. Check the final answer.

Comparing the TaoGPT, GPT-4 with the default system prompt produced
a [generic and vague response](/examples/gpt-4/travel-planning.default.md). The details of execution
log can be found [here](/examples/gpt-4/travel-planning.log.md).

More examples are in the [examples folder](/examples).

<div style="background-color: beige; text-align: center; padding: 5px">


# Final path history

</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>: </div>

I want to travel to Moscow. I just need a detailed route plan.
(I don't need the actual schedule. And you don't have access to the internet.)


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>user</b>: </div>

> What is your starting location for the journey to Moscow?

Urumuqi

> Which mode(s) of transportation do you prefer for this trip?

I'm afraid of flying.

> Are you looking to travel directly to Moscow, or are you planning to make any stops along the way?

I would like to visit Lahsa.

> Do you have any specific travel preferences or constraints, such as budget or time limitations?

I like fewer hassle. I like comfort.



</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>Tao</b>: </div>

I apologize for the oversight. Without access to the internet and specific train schedules, I can provide a more generalized route plan with the understanding that you will need to obtain the exact train numbers, departure times, and transfer details locally at the train stations or through a travel agency. Here is a revised, simplified route plan:

***Urumqi to Lhasa***


1. **Train from Urumqi to Xining**: Board a train from Urumqi to Xining. This leg of the journey will take about a day. Look for a train that offers soft sleeper compartments for comfort.

2. **Train from Xining to Lhasa**: From Xining, take the train to Lhasa on the Qinghai-Tibet Railway. This journey will take roughly a day and offers breathtaking views of the Tibetan Plateau. Again, choose a soft sleeper for the best comfort.

***Lhasa to Moscow***


The journey from Lhasa to Moscow will involve multiple train changes and countries:

1. **Train from Lhasa to Beijing**: Take a train from Lhasa back to Beijing. This trip will take approximately two days. A soft sleeper compartment is recommended.

2. **Train from Beijing to Ulaanbaatar**: From Beijing, board the train to Ulaanbaatar, Mongolia. This journey will take about a day and a half.

3. **Train from Ulaanbaatar to Irkutsk**: After arriving in Ulaanbaatar, find a train to Irkutsk, Russia. This leg will take about a day.

4. **Train from Irkutsk to Moscow**: Finally, from Irkutsk, you will embark on the Trans-Siberian Railway to Moscow. This is the longest leg, taking approximately three to four days. A first-class cabin is suggested for maximum comfort.

Please ensure to check for the most recent train schedules and availability at local train stations or through a travel agency. You will also need to arrange visas for China, Mongolia, and Russia in advance, and consider accommodations for overnight stops or layovers. It's important to book your train tickets as early as possible, especially if you are looking for sleeper compartments, to ensure a comfortable journey.


</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>Tao</b>: </div>

Based on your starting location in Urumqi and your preference to avoid flying, as well as your desire to visit Lhasa and preference for comfort and minimal hassle, here is a detailed route plan for your journey to Moscow:

**Urumqi to Lhasa:**
1. **Urumqi to Xining**: Begin your journey by taking a train from Urumqi to Xining. This leg of the journey will take approximately one day. Since you prefer comfort, it is recommended to book a soft sleeper compartment for this trip. You will need to check the local train station or contact a travel agency for the exact train options and schedules.

2. **Xining to Lhasa**: From Xining, you will transfer to the train bound for Lhasa on the Qinghai-Tibet Railway. This journey will also take roughly one day. The soft sleeper compartment is advisable for this leg as well, providing both comfort and an opportunity to enjoy the scenic views of the Tibetan Plateau.

**Lhasa to Moscow:**
1. **Lhasa to Beijing**: After your visit to Lhasa, you will need to take a train back to Beijing. This trip will take approximately two days. A soft sleeper compartment is recommended for a comfortable journey. Please note that you may need to transfer in Xining again.

2. **Beijing to Ulaanbaatar**: From Beijing, you will take a train to Ulaanbaatar in Mongolia. This journey will take about one and a half days. Booking a soft sleeper will ensure a comfortable trip.

3. **Ulaanbaatar to Irkutsk**: Upon arrival in Ulaanbaatar, you will find a train to Irkutsk, Russia. This leg will take about one day. As with previous legs, a soft sleeper is suggested for comfort.

4. **Irkutsk to Moscow**: The final leg of your journey will be aboard the Trans-Siberian Railway from Irkutsk to Moscow. This is the longest part of the trip, taking approximately three to four days. Opting for a first-class cabin will provide the highest level of comfort for this extended journey.

**Additional Considerations:**
- **Visas**: You will need to secure visas for China, Mongolia, and Russia well in advance of your trip. This process can be complex and time-consuming, so it's important to start early. Contact the respective embassies or consulates for guidance on the application process.

- **Train Tickets**: Without internet access, you will need to purchase your train tickets directly at the train stations or through a travel agency. It's crucial to book these as early as possible, especially if you are looking for sleeper compartments, which are in high demand.

- **Accommodations**: For overnight stops or layovers, you may want to book hotels near the train stations for convenience. Since you do not have internet access, you can arrange your accommodations through a travel agency or by contacting hotels directly via phone.

- **Travel Advisories and Entry Requirements**: Check for any travel advisories and entry requirements for each country you will be visiting. This information can be obtained from embassies, consulates, or travel agencies.

- **Local Assistance**: Since you do not have internet access, it is advisable to seek assistance from local travel agencies or train station information desks throughout your journey. They can provide up-to-date schedules, ticket availability, and help with accommodations.

Please ensure that you have all the necessary documentation, including passports and visas, and that you are aware of the local COVID-19 regulations and travel restrictions that may be in place during your journey. Safe travels!
</div>

---

In [the detailed long log](examples/gpt-4-turbo/travel_advice-questions_direct.log), we can see that TaoGPT found 
multiple issues in the passes and fixed the issues (without backtracking since they are non-fatal for this task.)

<div style="color: white; background-color: gray">

**REPAIRING response to start working on the problem/3#1 for:**

* error: The route details provided are generic and lack specific information such as train numbers, departure times, and where to change trains, which are essential for planning a trip without internet access.


</div>

<div style="background-color:lightgrey; padding: 5px; border-bottom: 1px dotted grey">
<div>[-1] <b>system</b>: (tokens: 43)</div>

[..tao_intro:44..]


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[0] <b>user</b>: (tokens: 43)</div>

[at step#0: step 0]

I want to travel to Moscow. I just need a detailed route plan.
(I don't need the actual schedule. And you don't have access to the internet.)


</div>

<div style="background-color:lightgreen; padding: 5px; border-bottom: 1px dotted grey">
<div>[1] <b>user</b>: (tokens: 117)</div>

***Tao asked and user replied:***


[at step#1: ask questions before response to start working on the problem]

[... text omitted ...]

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[2] <b>Tao</b>: (tokens: 505)</div>

***MY_THOUGHT***


[at step#3: response to start working on the problem]

[... text omitted ...]

</div>

<div style="background-color:lightyellow; padding: 5px; border-bottom: 1px dotted grey">
<div>[3] <b>Tao</b>: (tokens: 497)</div>

[at step#4: Summarize final answer]

[... text omitted ...]

</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[4] <b>orchestrator</b>: (tokens: 67)</div>

[..snippet_notes_for_files:67..]


</div>

<div style="background-color:lightcyan; padding: 5px; border-bottom: 1px dotted grey">
<div>[5] <b>orchestrator</b>: (tokens: 54)</div>

These are prior issues found:

* error: The route details provided are generic and lack specific information such as train numbers, departure times, and where to change trains, which are essential for planning a trip without internet access.

---
Please fix the issues and rewrite the answer.

</div>

[... reply text omitted, see the log file ...]

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

Please consider citing our work if you reference to our work or use the data or code in this repo.

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
