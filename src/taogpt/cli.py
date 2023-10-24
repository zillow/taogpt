import argparse
import dataclasses
import os
import sys

from taogpt import Config
from taogpt.runner import solve_problem
from taogpt.utils import set_openai_credentials_from_json

# The skeleton is created by the GPT-4
parser = argparse.ArgumentParser(
    prog='taogpt',
    description='command-line tool to ask Tao to solve a task',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)

# hyperparameters
parser.add_argument('-i', '--initial-expansion', type=int, default=1, help='Initial expansion factor')
parser.add_argument('-f', '--first-expansion', type=int, default=1, help='First expansion factor')
parser.add_argument('-T0', '--first-try-temperature', type=float, default=0.0, help='First try temperature')
parser.add_argument('-T1', '--alternative-temperature', type=float, default=0.7, help='Alternative temperature')
parser.add_argument('-m', '--max-search-expansion', type=int, default=4, help='Maximum search expansion')
parser.add_argument('-v', '--votes', type=int, default=1, help='Number of votes')

# behavioral
parser.add_argument('-a', '--analyze-first', type=bool, default=True,
                    action=argparse.BooleanOptionalAction, help='Analyze first')
parser.add_argument('-c', '--check-final', type=bool, default=True,
                    action=argparse.BooleanOptionalAction, help='Check final')

# token usage controls
parser.add_argument('-t', '--max-tokens', type=int, default=10000, help='Maximum number of tokens')
parser.add_argument('--max-tokens-for-sage-llm', type=int, default=None, help='Maximum tokens for sage LLM')
parser.add_argument('-r', '--max-retries', type=int, default=3, help='Maximum number of retries')
parser.add_argument('-s', '--use-sage-llm-for-initial-expansion', type=bool, default=True,
                    action=argparse.BooleanOptionalAction, help='Use sage LLM for initial expansion')

# user interactions
parser.add_argument('-F', '--file-generation-support', type=bool, default=False,
                    action=argparse.BooleanOptionalAction, help='Additional support for file generation')
parser.add_argument('-S', '--silence', type=int, default=0,
                    help='Level of console printouts: 0: print conversation; 1: do not print conversation.')
parser.add_argument('-Q', '--ask-user-questions-in-one-prompt', type=bool, default=False,
                    action=argparse.BooleanOptionalAction, help='Ask user questions in one prompt')
parser.add_argument('-E', '--ask-user-before-execute-codes', type=bool, default=True,
                    action=argparse.BooleanOptionalAction, help='Ask user before execute codes')
parser.add_argument('-P', '--pause-after-initial-solving-expansion', type=bool, default=True,
                    action=argparse.BooleanOptionalAction, help='Pause after initial solving expansion')
parser.add_argument('-R', '--pause-after-final-answer-rejected', type=bool, default=True,
                    action=argparse.BooleanOptionalAction, help='Pause after any final answer rejected by Sage')

# separate settings
parser.add_argument('-p', '--path', type=str, required=True, help='Directory path for outputs')
parser.add_argument('-llm', '--llm', type=str, choices=['gpt-4', 'gpt-3.5'], default='gpt-4',
                    help='Default LLM model name')
parser.add_argument('--sage-llm', type=str, choices=['gpt-4', 'gpt-3.5'], default=None,
                    help='Sage LLM model name')
parser.add_argument('--long-llm', type=str, choices=['gpt-4-32k', 'gpt-3.5-16k'], default=None,
                    help='Default long-context LLM model name')
parser.add_argument('--long-sage-llm', type=str, choices=['gpt-4-32k', 'gpt-3.5-16k'], default=None,
                    help='Long-context sage LLM model name')
parser.add_argument('--long-context-threshold', type=int, default=3000,
                    help='Number of tokens before switching to long-context LLM')

parser.add_argument('-C', '--openai-credential-json', type=str, default=None,
                    help='File path of JSON hash containing `key` and `url` '
                         'corresponding to "OPENAI_API_KEY" and "OPENAI_API_BASE" respectively')
parser.add_argument('-D', '--debug', type=bool, default=False,
                    action=argparse.BooleanOptionalAction, help='Enable debugging')

# last positional argument as the string of task
parser.add_argument('user_task', type=str, nargs='?', default=None,
                    help='User task in markdown text. '
                         'If the string starts with "@", it is the path to a text file to be read.')

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
    if user_task.startswith('@'):
        with open(user_task[1:], 'r') as f:
            user_task = '\n'.join(f.readlines())

    if args.openai_credential_json is not None:
        set_openai_credentials_from_json(args.openai_credential_json)
    key = os.environ.get("OPENAI_API_KEY", None)
    if llm.startswith('gpt-') and (key is None or key == ''):
        raise PermissionError("Must set OPENAI_API_KEY environment variable.")

    os.makedirs(log_path, exist_ok=True)
    solve_problem(user_task, log_path, config, llm, long_llm, long_sage_llm, sage_llm, long_context_token_threshold,
                  input, log_to_stdout, debug)
    return 0


if __name__ == '__main__':
    main()
