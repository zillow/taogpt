import argparse
import dataclasses
import os
import pathlib as _p
import sys
import typing as _t

from langchain.chat_models import ChatOpenAI

from taogpt.orchestrator import *
from taogpt.prompts import PromptDb
from taogpt.utils import *

# The skeleton is created by the GPT-4
parser = argparse.ArgumentParser(
    prog='taogpt',
    description='command-line tool to ask Tao to solve a task'
)

# hyperparameters
parser.add_argument('-i', '--initial-expansion', type=int, default=1, help='Initial expansion factor')
parser.add_argument('-f', '--first-expansion', type=int, default=1, help='First expansion factor')
parser.add_argument('-T0', '--first-try-temperature', type=float, default=0.0, help='First try temperature')
parser.add_argument('-T1', '--alternative-temperature', type=float, default=0.7, help='Alternative temperature')
parser.add_argument('-m', '--max-search-expansion', type=int, default=4, help='Maximum search expansion')
parser.add_argument('-v', '--votes', type=int, default=1, help='Number of votes')

# behavioral
parser.add_argument('-a', '--analyze-first', type=bool, default=True, help='Analyze first')
parser.add_argument('-c', '--check-final', type=bool, default=True, help='Check final')

# token usage controls
parser.add_argument('-t', '--max-tokens', type=int, default=10000, help='Maximum number of tokens')
parser.add_argument('--max-tokens-for-sage-llm', type=int, default=None, help='Maximum tokens for sage LLM')
parser.add_argument('-r', '--max-retries', type=int, default=3, help='Maximum number of retries')
parser.add_argument('-s', '--use-sage-llm-for-initial-expansion', type=bool, default=True,
                    help='Use sage LLM for initial expansion')

# user interactions
parser.add_argument('-Q', '--ask-user-questions-in-one-prompt', type=bool, default=False,
                    help='Ask user questions in one prompt')
parser.add_argument('-E', '--ask-user-before-execute-codes', type=bool, default=True,
                    help='Ask user before execute codes')
parser.add_argument('-P', '--pause-after-initial-solving-expansion', type=bool, default=True,
                    help='Pause after initial solving expansion')

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

parser.add_argument('-F', '--task-file', type=str, default=None,
                    help='Markdown file path of the user\'s task problem')
parser.add_argument('-D', '--debug', type=bool, default=False, help='Enable debugging')

# last positional argument as the string of task
parser.add_argument('user_task', type=str, nargs='?', default=None, help='User task string')

def cli_main() -> int:
    args = parser.parse_args()
    config_fields = {f.name for f in dataclasses.fields(Config)}
    config: Config = Config(**{f: v for f, v in vars(args).items() if f in config_fields})

    llm = args.llm
    sage_llm = args.sage_llm
    long_llm = args.long_llm
    long_sage_llm = args.long_sage_llm
    task_file = args.task_file
    user_task: str = args.user_task
    debug = args.debug

    if task_file is not None:
        assert user_task is None or user_task.strip() == ''
        with open(task_file, 'r') as f:
            user_task = '\n'.join(f.readlines())
    if user_task is None or user_task.strip() == '':
        print("WARN: no user task problem is given", file=sys.stderr)
        return 0

    def _fix_model_name(model_name, required=False):
        if model_name is None:
            assert required is not None
            return model_name
        assert model_name in {'gpt-4', 'gpt-3.5', 'gpt-3.5-turbo'}
        if model_name == 'gpt-3.5':
            model_name = 'gpt-3.5-turbo'
        return model_name

    llm = _fix_model_name(llm, required=True)
    sage_llm = _fix_model_name(sage_llm)
    long_llm = _fix_model_name(long_llm)
    long_sage_llm = _fix_model_name(long_sage_llm)
    if long_llm is None and llm == 'gpt-4':
        long_llm = 'gpt-4-32k' if llm in {'gpt-4', 'gpt-4-32k'} else 'gpt-3.5-turbo-16k'
    if long_sage_llm is None and sage_llm == 'gpt-4':
        long_sage_llm = 'gpt-4-32k' if sage_llm in {'gpt-4', 'gpt-4-32k'} else 'gpt-3.5-turbo-16k'

    key = os.environ.get("OPENAI_API_KEY", None)
    if key is None or key == '':
        raise PermissionError("Must set OPENAI_API_KEY environment variable.")

    prompts = PromptDb.load_defaults()
    logger = MarkdownLogger(_p.Path(args.path) / 'taogpt_log.md', log_debug=debug)

    long_ctx_llm = ChatOpenAI(model_name=long_llm) if long_llm is not None and long_llm != llm else None
    primary_model = LangChainLLM(ChatOpenAI(model_name=llm), logger=logger,
                                 long_context_llm=long_ctx_llm,
                                 long_context_token_threshold=args.long_context_threshold)
    sage_model: _t.Optional[LangChainLLM] = None
    if sage_llm is not None and sage_llm != llm:
        long_ctx_llm = ChatOpenAI(model_name=long_sage_llm) \
            if long_sage_llm is not None and long_sage_llm != sage_llm else None
        sage_model = LangChainLLM(ChatOpenAI(model_name=sage_llm), logger=logger,
                                  long_context_llm=long_ctx_llm,
                                  long_context_token_threshold=args.long_context_threshold)

    executor = Orchestrator(
        config=config,
        llm=primary_model,
        prompts=prompts,
        markdown_logger=logger,
        sage_llm=sage_model,
    )

    pause: _t.Optional[Pause] = None
    try:
        executor.start(user_task)
    except Pause as e:
        pause = e
    while pause is not None:
        resume: _t.Optional[str] = None
        while resume is None or re.match(r"\d+|no", resume) is None:
            resume = input(f"{str(pause)}\nReply amount of tokens to add and continue, 'no' to cancel: ")\
                .strip().lower()
        if resume == 'no':
            break
        pause = None
        try:
            executor.resume(additional_tokens=int(resume), unblock_initial_expansion=True,
                            additional_sage_tokens=int(resume) // 3)
        except Pause as e:
            pause = e

    logger = MarkdownLogger(_p.Path(args.path) / f'taogpt_results.final.md')
    executor.log_configs(logger)
    logger.log_conversation(executor.show_conversation_thread(with_header=True))
    logger.log(f"**total tokens**: {executor.llm.total_tokens}")
    return 0


if __name__ == '__main__':
    cli_main()
