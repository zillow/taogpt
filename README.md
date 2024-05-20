# TaoGPT: Template-guided Autoregressive Orchestrator for General Problem Tackling

<div style="text-align: center">

### From deep learning to deep thinking
![Tao-LLM](assets/LLM_tao.128x128.png)

</div>
<div style="text-align: center">


*In the way of the Tao, the problem solver moves like water—adapting, flowing, overcoming. Guided by the virtues of flexibility, adaptability, and insight, this solver approaches each challenge with the ease of a river carving its path through stone. Flexibility allows bending without breaking, adapting strategies to the contours of each unique problem. Adaptability, inspired by Wu Wei, embraces effortless action, aligning with the natural order to find solutions that emerge without force. Insight, through simplicity, cuts to the core, revealing solutions that are both effective and elegantly simple. This approach does not force solutions but discovers them, reflecting the deep, flowing wisdom of the Tao. Thus, the Tao problem solver navigates the myriad challenges with grace and effectiveness, embodying the ancient yet timeless virtues of the Tao.*

-- [Self-pitch by TaoGPT](/examples/gpt-4-turbo/taogpt_self_pitch.steps.log.md)

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

<div style="background-color: beige; text-align: center; padding: 5px">

# Final path history

</div>

<div class="section_header " style="background-color:lightgreen">
<div class="header">[000] <b>user</b>:  </div>
<div class="content">

I want to travel to Moscow. I just need an itinerary.
(I don't need the actual schedule. And you don't have access to the internet. No need to book tickets for now.)

</div></div>

<div class="section_header " style="background-color:lightgreen">
<div class="header">[001] <b>user</b>:  </div>
<div class="content">

> From which city or country are you starting your journey to Moscow?

Urumuqi.

> Do you have any preferences for the mode of transportation (e.g., plane, train, car)?

I'm afraid of flying.

> Are there any specific dates or time constraints for your travel?

Around July.

> Do you need information on accommodations or just the travel itinerary?

No.

> Would you like to include any stops or is it a direct journey to Moscow?

I would like to visit Lahsa as well.

</div></div>

<div class="section_header " style="background-color:lightgreen">
<div class="header">[002] <b>user</b>:  </div>
<div class="content">

> Are you open to using multiple modes of transportation, such as trains and buses, given your fear of flying?

I prefer comfort and fewest changeover or stopover. I'm not hurry.

> Do you have any preferences or restrictions regarding the duration of the travel from Urumuqi to Moscow?

I have plenty of time.

> Would you like to spend some time exploring Lhasa, or is it just a brief stopover on your way to Moscow?

I will determine later. For now, I only need the travel routes.

> Are there any budget constraints for your travel that I should consider while planning your itinerary?

I have a lot of money.

> Do you need assistance with visa or travel document requirements for the countries you will pass through?

No. I'm a Chinese citizen and I have Russian visa.

</div></div>

<div class="section_header " style="background-color:lightyellow">
<div class="header">[003] <b>Tao</b>:  </div>
<div class="content">

Given the user's preferences and requirements, the following plan outlines the creation of a comfortable, efficient, and enjoyable travel itinerary from Urumqi to Moscow via Lhasa, considering the user's fear of flying and preference for minimal transfers.

1. Research and outline possible ground transportation routes from Urumqi to Lhasa focusing on comfort and minimal transfers
2. Identify and evaluate the best transportation options from Lhasa to Moscow, prioritizing train travel
3. Combine the segments from Urumqi to Lhasa and Lhasa to Moscow to form a complete itinerary
4. Review the overall travel plan for any potential issues or optimizations in terms of travel comfort and efficiency

</div></div>

<div class="section_header " style="background-color:lightyellow">
<div class="header">[004] <b>Tao</b>:  </div>
<div class="content">

The proposed travel route from Urumqi to Lhasa focuses on comfort and minimal transfers, adhering to the user's preferences. The primary mode of transportation identified is the direct train service via the Qinghai-Tibet railway. This train offers soft sleeper classes that provide comfortable bedding and privacy, suitable for the long journey. The cabins are pressurized and equipped with an oxygen supply to handle the high altitude, ensuring a comfortable travel experience. The train route is also scenic, offering views of the Qinghai-Tibet plateau, enhancing the travel experience with its natural beauty and unique landscapes. Alternative transportation options such as luxury buses or private car services were evaluated but the train was chosen for its direct route and amenities. The journey starts at Urumqi South Railway Station and concludes at Lhasa Railway Station, providing a straightforward and enjoyable travel experience with minimal transfers.

</div></div>

<div class="section_header " style="background-color:lightyellow">
<div class="header">[005] <b>Tao</b>:  </div>
<div class="content">

Considering the user's preference for comfort and minimal transfers, the journey from Lhasa to Moscow by train involves multiple segments, as there is no direct train service covering this entire route. The most feasible route involves traveling from Lhasa to Beijing by train, then from Beijing to Moscow.

1. **Lhasa to Beijing**: The user can take a train from Lhasa to Beijing. This segment is served by trains such as the Z22, which offers soft sleeper compartments for comfort over the long journey. This train journey provides beautiful scenic views and a comfortable travel experience with amenities suitable for long-distance travel.

2. **Beijing to Moscow**: From Beijing, the user can board the Trans-Siberian Railway, specifically the train service known as the Trans-Mongolian route (Train K3 from Beijing to Moscow). This train also offers various classes, including soft sleepers for comfort. The journey covers several days and passes through Mongolia, offering a unique travel experience with diverse landscapes and cultural exposure.

This route has been chosen based on the availability of train services that prioritize comfort and provide a relatively seamless travel experience with minimal transfers, aligning with the user's preferences.

</div></div>

<div class="section_header " style="background-color:lightyellow">
<div class="header">[006] <b>Tao</b>:  </div>
<div class="content">

The complete itinerary for the journey from Urumqi to Moscow via Lhasa, focusing on comfort and minimal transfers, is as follows:

***Urumqi to Lhasa***


- **Departure**: Urumqi South Railway Station
- **Arrival**: Lhasa Railway Station
- **Transportation**: Direct train service via the Qinghai-Tibet railway
- **Class**: Soft sleeper for comfort
- **Duration**: Approximately 48 hours
- **Scenery**: Offers views of the Qinghai-Tibet plateau

***Lhasa to Moscow***


- **Departure**: Lhasa Railway Station
- **Arrival**: Moscow Yaroslavsky Railway Station
- **Transportation**: Train from Lhasa to Beijing (Z22), then Trans-Mongolian Railway from Beijing to Moscow (Train K3)
- **Class**: Soft sleeper for comfort
- **Duration**: Lhasa to Beijing approximately 40 hours, Beijing to Moscow approximately 6 days
- **Scenery**: Diverse landscapes including the Gobi Desert and rural Mongolia

This itinerary provides a seamless travel experience with minimal transfers, utilizing the most comfortable class available on trains. The journey not only ensures comfort but also offers a scenic and culturally enriching travel experience.

</div></div>

<div class="section_header " style="background-color:lightyellow">
<div class="header">[007] <b>Tao</b>:  </div>
<div class="content">

Upon reviewing the proposed travel itinerary from Urumqi to Moscow via Lhasa, the plan appears to align well with the user's preferences for comfort and minimal transfers. Here are some considerations and potential optimizations:

1. **Comfort and Duration**: The selected train services (Qinghai-Tibet railway and Trans-Mongolian Railway) are known for their comfort, especially in the soft sleeper classes. However, the total duration of the journey is quite long (approximately 7 days). Given the user's preference for comfort and not being in a hurry, this seems appropriate, but it's important to ensure that the user is prepared for such a long journey.

2. **Scenic Value**: Both segments of the journey offer scenic views which can enhance the travel experience. Ensuring that the user is aware of these aspects might add value to their experience.

3. **Transfers**: The plan involves a transfer in Beijing, which has been minimized to just one transfer for the entire journey from Urumqi to Moscow. This is aligned with the user's preference for minimal transfers. However, ensuring that the transfer in Beijing is smooth and comfortable is crucial, considering the user's fear of flying and general travel anxiety. Providing detailed information about the transfer process in Beijing might be beneficial.

4. **Health Considerations**: The high altitude of the Qinghai-Tibet railway might be a concern for some travelers. Although the trains are equipped with oxygen supply, it might be useful to remind the user to consider any personal health issues related to high altitudes.

5. **Cultural and Language Barriers**: Traveling through different countries, especially in rural areas of Mongolia and Russia, might present language and cultural barriers. Providing the user with basic travel tips, including key phrases in Russian or Mongolian, could be helpful. Additionally, suggesting specific resources or guides for language and cultural etiquette would enhance the user's preparation and comfort.

6. **Emergency Preparedness**: Given the length and nature of the journey, ensuring that the user is prepared for emergencies, including travel insurance and knowledge of embassy locations en route, would be prudent.

Overall, the travel plan seems well-suited to the user's needs, focusing on comfort and minimal hassle. These additional considerations are aimed at enhancing the user's travel experience and preparing them for the journey ahead.

Repair notes:
* **warning**: Fixed. I have added suggestions for specific resources or guides for language and cultural etiquette to better prepare the user for the cultural and language barriers they might encounter.

</div></div>

<div class="section_header " style="background-color:lightyellow">
<div class="header">[008] <b>Tao</b>:  </div>
<div class="content">

***HERE_IS_MY_STEP_BY_STEP_PLAN***

[at step#16: Final travel itinerary presentation]

Here is your complete travel itinerary from Urumqi to Moscow via Lhasa, tailored to your preferences for comfort and minimal transfers:

***Urumqi to Lhasa***

- **Departure**: Urumqi South Railway Station
- **Arrival**: Lhasa Railway Station
- **Transportation**: Direct train via the Qinghai-Tibet railway
- **Class**: Soft sleeper for comfort
- **Duration**: Approximately 48 hours
- **Scenery**: Enjoy the stunning views of the Qinghai-Tibet plateau

***Lhasa to Moscow***

- **Departure**: Lhasa Railway Station
- **Arrival**: Moscow Yaroslavsky Railway Station
- **Transportation**: Train from Lhasa to Beijing (Z22), then Trans-Mongolian Railway from Beijing to Moscow (Train K3)
- **Class**: Soft sleeper for comfort
- **Duration**: Lhasa to Beijing approximately 40 hours, Beijing to Moscow approximately 6 days
- **Scenery**: Experience diverse landscapes including the Gobi Desert and rural Mongolia

***Key Considerations***

- **Comfort and Duration**: The journey is long but comfortable, suitable for your preference to not rush and enjoy the journey.
- **Transfers**: Minimal transfers, with only one major transfer in Beijing, ensuring a smooth travel experience.
- **Health and Safety**: Be prepared for high altitudes on the Qinghai-Tibet railway with onboard oxygen supply. Consider travel insurance and familiarize yourself with emergency contacts.
- **Cultural Preparedness**: Given the diverse cultures and languages you will encounter, especially in Mongolia and Russia, consider carrying a travel guide or language phrasebook to enhance your interaction and experience.

This itinerary provides a seamless and comfortable journey, allowing you to enjoy the scenic beauty and cultural richness of the regions you will travel through. Safe travels!

</div></div>

**total tokens**: 57186

---

In [the detailed long log](examples/gpt-4/travel_advice-questions_steps.log.md), TaoGPT walked through the problem 
solving process, identified and fixed issues (without backtracking since they are non-fatal for this task.)

### Comparing to GPT-4-turbo answer using system default prompt

[GPT with default system prompt](examples/gpt-4-turbo/travel_advice.default.md) usually provides either a touring 
plan in the city rather than how to get there or an air travel plan from an arbitrary city.

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

# can use command-line to pass in short task problem.
$ taogpt -p /tmp/taogpt_outputs "What's the 51st fibonacci number?"

# open the log file /tmp/taogpt_outputs/taogpt_log.md in your Markdown viewer
```

The command-line tool will print out (abbreviated) log in the console. A file logging the problem solving
progress and a file with the final step chain are written to the output directory; they are Markdown files viewable
by any Markdown viewer. Users are recommended to view the Markdown log files for better experiences. The directory also
contain any Tao-generated files organized by directory paths.

```shell
# assuming you store your OpenAI credential in ~/my_openai.ini file like this:
$ cat ~/my_openai.ini
[DEFAULT]
OPENAI_API_KEY=...your OpenAI key...
OPENAI_API_BASE=https://api.openai.com/v1

# create a Markdown file for the (long) task problem:
$ echo "I plan to relocate to San Francisco Bay Area next month. Where should I settle?" > /tmp/example.md

$ mkdir /tmp/taogpt_outputs # directory where output files go to.
$ taogpt -C ~/my_openai.ini -p /tmp/taogpt_outputs @/tmp/example.md
# open the log file /tmp/taogpt_outputs/taogpt_log.md in your Markdown viewer
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
  title = {TaoGPT: Template-guided Autoregressive Orchestrator for General Problem Tackling},
  author = {Quock, Winston},
  url = {https://github.com/zillow/taogpt},
  year = {2024},
  month = {04},
}
```
