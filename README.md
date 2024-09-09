# TaoGPT: Template-guided Autoregressive Orchestrator for General Problem Tackling

<div style="text-align: center">

### From deep learning to deep thinking
![Tao-LLM](assets/LLM_tao.128x128.png)

</div>
<div style="text-align: center">


*Embrace the way of Tao in problem-solving, where every step is a path to deeper understanding. Like water, the Tao 
problem solver flows around obstacles with flexibility and patience, never rigid but adapting to the shape of the 
challenge. With intuition as a guide and reason as a companion, seek clarity through simplicity, and find solutions 
in stillness. This is the art of solving problems by not contending, by aligning with the natural course of events. 
Here, every problem is an opportunity to practice the virtues of wisdom, simplicity, and serenity.*

-- [Self-pitch by TaoGPT](examples/taogpt_self_pitch.direct.log.md)

</div>

## Introduction

(*This section [is written by TaoGPT](examples/taogpt_self_description.direct.log.md) with illustration by the authors.*)

![TaoGPT High-level design](assets/high_level_design.png)

Recent advancements in artificial intelligence have spotlighted the proficiency of Large Language Models (LLMs) in
tasks that involve human-like textual interactions. These models are adept in applications requiring quick responses
and basic reasoning, aligning with System 1 cognitive functions. However, their performance in complex tasks
demanding in-depth planning and intricate reasoning—related to System 2 cognitive processes—has been less effective.

This work introduces the Template-guided Autoregressive Orchestrator for General Problem Tackling (TaoGPT), a
framework aimed at enhancing the problem-solving capabilities of LLMs for these more demanding tasks. TaoGPT
employs a dual-role functionality, alternating between a problem solver (Tao) and a critical analyzer (Sage), to
harness the intrinsic strengths of LLMs while addressing their limitations in structured task management.

This approach is designed to deepen the engagement of LLMs with complex problems, thereby improving their ability to 
navigate through tasks that require sophisticated planning and reasoning. The incorporation of self-hinting 
techniques and the TRIPS (Targeted Repair, Improvement, and Partial Summarization) methodology further aims to 
refine the accuracy and effectiveness of LLMs in complex problem-solving scenarios.

(The above introduction is written by TaoGPT with minor edits by the author.)

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

Examples of diverse task types can be found in the [examples folder](/examples).

The problem solving logs are markdown format with colored sections. Some Markdown viewers, such as those built in 
the github source control system, may remove `<div>`s used for coloring sections. For best viewing pleasure, it is 
recommended to view the log contents using a proper Markdown browser plugin.

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
