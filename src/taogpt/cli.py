from __future__ import annotations

import argparse
import dataclasses
import os
import pickle
import sys
import typing as _t

from taogpt import Config
from taogpt.runner import solve_problem, load_and_resume_problem
from taogpt.utils import set_openai_credentials

# The skeleton is created by the GPT-4
parser = argparse.ArgumentParser(
    prog='taogpt',
    description='command-line tool to ask Tao to solve a task',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)

# hyperparameters
_proto_config = Config()
parser.add_argument('-i', '--initial-expansion', type=int,
                    default=_proto_config.initial_expansion, help='Initial expansion factor')
parser.add_argument('-f', '--first-expansion', type=int,
                    default=_proto_config.first_expansion, help='First expansion factor')
parser.add_argument('-T0', '--first-try-temperature', type=float,
                    default=_proto_config.first_try_temperature, help='First try temperature')
parser.add_argument('-T1', '--alternative-temperature', type=float,
                    default=_proto_config.alternative_temperature, help='Alternative temperature')
parser.add_argument('-m', '--max-search-expansion', type=int,
                    default=_proto_config.max_search_expansion, help='Maximum search expansion')
parser.add_argument('-v', '--votes', type=int,
                    default=_proto_config.votes, help='Number of ranking votes')
parser.add_argument('-c', '--n-final-checks', type=int,
                    default=_proto_config.n_final_checks,
                    action=argparse.BooleanOptionalAction, help='Number of final verifications and repairs')

# behavioral
parser.add_argument('-Q', '--ask-questions', type=bool, default=_proto_config.ask_questions,
                    action=argparse.BooleanOptionalAction,
                    help='Enable proactive clarification questioning')
parser.add_argument('-E', '--ask-genie', type=bool, default=_proto_config.ask_genie,
                    action=argparse.BooleanOptionalAction,
                    help='Enable code execution (in a runtime environment, i.e. Python)')
parser.add_argument('-F', '--file-support', type=bool, default=_proto_config.file_support,
                    action=argparse.BooleanOptionalAction,
                    help='Enable file support')
parser.add_argument('-N', '--optimized-sequential-next-step', type=bool,
                    default=_proto_config.optimized_sequential_next_step,
                    action=argparse.BooleanOptionalAction,
                    help='Directly advance to next step for sequential plan (without needing LLM to decide.)')
parser.add_argument('-S', '--summarize', type=bool, default=_proto_config.summarize,
                    action=argparse.BooleanOptionalAction,
                    help='Do summarize')

# token usage controls
parser.add_argument('-t', '--max-tokens', type=int,
                    default=_proto_config.max_tokens, help='Maximum number of tokens')
parser.add_argument('--max-tokens-for-sage-llm', type=int,
                    default=_proto_config.max_tokens_for_sage_llm, help='Maximum tokens for sage LLM')
parser.add_argument('--max-retries', type=int,
                    default=_proto_config.max_retries, help='Maximum number of retries')
parser.add_argument('--use-sage-llm-for-initial-expansion', type=bool,
                    default=_proto_config.use_sage_llm_for_initial_expansion,
                    action=argparse.BooleanOptionalAction, help='Use sage LLM for initial expansion')

# user interactions
parser.add_argument('--ask-user-questions-in-one-prompt', type=bool,
                    default=_proto_config.ask_user_questions_in_one_prompt,
                    action=argparse.BooleanOptionalAction, help='Ask user questions in one prompt')
parser.add_argument('--ask-user-before-execute-codes', type=bool,
                    default=_proto_config.ask_user_before_execute_codes,
                    action=argparse.BooleanOptionalAction, help='Ask user before execute codes')
parser.add_argument('--pause-after-initial-solving-expansion', type=bool,
                    default=_proto_config.pause_after_initial_solving_expansion,
                    action=argparse.BooleanOptionalAction, help='Pause after initial solving expansion')
parser.add_argument('--pause-on-backtrack', type=bool,
                    default=_proto_config.pause_on_backtrack,
                    action=argparse.BooleanOptionalAction, help='Pause when a backtrack is requested')

# runtime settings
parser.add_argument('-p', '--path', type=str, required=True, help='Directory path for log and outputs')
parser.add_argument('-L', '--llm', type=str, default='gpt-4-turbo',
                    help='Default LLM model name')
parser.add_argument('--sage-llm', type=str, default=None,
                    help='Sage LLM model name')
parser.add_argument('--long-llm', type=str, default=None,
                    help='Default long-context LLM model name')
parser.add_argument('--long-sage-llm', type=str, default=None,
                    help='Long-context sage LLM model name')
parser.add_argument('--long-context-threshold', type=int, default=3000,
                    help='Number of tokens before switching to long-context LLM')

parser.add_argument('-C', '--openai-credential', type=str, default=None,
                    help='Path of .ini or .json file containing key-value pair for `OPENAI_API_KEY`, '
                         '`OPENAI_API_BASE`, etc. (under the `DEFAULT` section for `.ini` file),'
                         'corresponding to the same OpenAI credential environment variables respectively')
parser.add_argument('--debug', type=bool, default=False,
                    action=argparse.BooleanOptionalAction, help='Enable debugging')
parser.add_argument('--load-chain', type=bool, default=False,
                    action=argparse.BooleanOptionalAction,
                    help='The task is the pickle file containing the state of a previous problem solving session.')

# last positional argument as the string of task
parser.add_argument('user_task', type=str, nargs='?', default=None,
                    help='User task in markdown text. '
                         'If the string starts with "@", it is either the path to a text file to be read or a pickle '
                         'file with suffix `.pkl` containing the state of the problem solving session.')

def main() -> int:
    args = parser.parse_args()
    config_fields = {f.name for f in dataclasses.fields(Config)}
    config: Config = Config(**{f: v for f, v in vars(args).items() if f in config_fields})

    llm = args.llm
    sage_llm = args.sage_llm
    long_llm = args.long_llm
    long_sage_llm = args.long_sage_llm
    user_task: str = args.user_task
    long_context_token_threshold = args.long_context_threshold
    debug = args.debug
    log_path = args.path
    log_to_stdout = sys.stdout if args.silence == 0 else None

    if user_task is None or user_task.strip() == '':
        print("WARN: no user task problem is given", file=sys.stderr)
        return 0
    load_previous = args.load_chain
    previous_states: _t.Optional[_t.Dict[str, _t.Any]] = None
    if user_task.startswith('@'):
        if user_task.endswith('.pkl'):
            load_previous = True
        if load_previous:
            with open(user_task[1:], 'rb') as f:
                previous_states = pickle.load(f)
        else:
            with open(user_task[1:], 'r') as f:
                user_task = f.read()
    elif load_previous:
        raise ValueError("--load-chain option is specified but the task argument is not a file")

    if args.openai_credential is not None:
        set_openai_credentials(args.openai_credential)
    key = os.environ.get("OPENAI_API_KEY", None)
    if llm.startswith('gpt-') and (key is None or key == ''):
        raise PermissionError("Must set OPENAI_API_KEY environment variable.")

    os.makedirs(log_path, exist_ok=True)
    if previous_states is None:
        solve_problem(user_task, log_path, config, llm, long_llm, long_sage_llm, sage_llm, long_context_token_threshold,
                      input, log_to_stdout, debug)
    else:
        load_and_resume_problem(previous_states, log_path, config, llm, long_llm, long_sage_llm, sage_llm,
                                long_context_token_threshold, input, log_to_stdout, debug)
    return 0


if __name__ == '__main__':
    main()
