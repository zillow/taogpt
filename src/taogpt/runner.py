import pathlib as _p
import re
import typing as _t
from io import TextIOBase as _TextIOBase

from langchain.chat_models import ChatOpenAI

from taogpt import Pause, MarkdownLogger, PromptDb, Config
from taogpt.llm_model import LangChainLLM
from taogpt.orchestrator import Orchestrator
from io import TextIOBase as _TextIO


def solve_problem(user_task: str, log_path: str, config: Config,
                  llm: str, long_llm: str, long_sage_llm: str, sage_llm: str,
                  long_context_token_threshold: int,
                  user_input_fn: _t.Callable[[str], str], console_out: _TextIO,
                  debug=False):
    executor = create_orchestrator(config, log_path, llm, long_llm, sage_llm, long_sage_llm,
                                   long_context_token_threshold, console_out, debug=debug)
    executor.set_input_fn(user_input_fn)
    pause: _t.Optional[Pause] = None
    try:
        executor.start(user_task)
    except Pause as e:
        pause = e
    while pause is not None:
        resume: _t.Optional[str] = None
        while resume is None or re.match(r"\d+|no", resume) is None:
            resume = input(f"{str(pause)}\nReply amount of tokens to add and continue, 'no' to cancel: ") \
                .strip().lower()
        if resume == 'no':
            break
        pause = None
        try:
            executor.resume(additional_tokens=int(resume), unblock_initial_expansion=True,
                            additional_sage_tokens=int(resume) // 3)
        except Pause as e:
            pause = e
    log_final_chain(executor, log_path, console_out=console_out)


def log_final_chain(executor, log_path, file_name='taogpt_results.final.md', console_out: _TextIOBase=None):
    logger = MarkdownLogger(_p.Path(log_path) / file_name, console_out=console_out)
    executor.log_configs(logger)
    logger.log_conversation(executor.show_conversation_thread(with_header=True))
    logger.log(f"**total tokens**: {executor.llm.total_tokens}")


def create_orchestrator(config: Config, log_path: str,
                        llm: str, long_llm: str, sage_llm: str, long_sage_llm: str,
                        long_context_token_threshold: int,
                        log_to_stdout: _TextIO, debug=False):
    llm = _fix_model_name(llm, required=True)
    sage_llm = _fix_model_name(sage_llm)
    long_llm = _fix_model_name(long_llm)
    long_sage_llm = _fix_model_name(long_sage_llm)
    if long_llm is None and llm == 'gpt-4':
        long_llm = 'gpt-4-32k' if llm in {'gpt-4', 'gpt-4-32k'} else 'gpt-3.5-turbo-16k'
    if long_sage_llm is None and sage_llm == 'gpt-4':
        long_sage_llm = 'gpt-4-32k' if sage_llm in {'gpt-4', 'gpt-4-32k'} else 'gpt-3.5-turbo-16k'
    prompts = PromptDb.load_defaults()
    logger = MarkdownLogger(_p.Path(log_path) / 'taogpt_log.md', log_debug=debug, console_out=log_to_stdout)
    long_ctx_llm = ChatOpenAI(model_name=long_llm) if long_llm is not None and long_llm != llm else None
    primary_model = LangChainLLM(ChatOpenAI(model_name=llm), logger=logger,
                                 long_context_llm=long_ctx_llm,
                                 long_context_token_threshold=long_context_token_threshold)
    sage_model: _t.Optional[LangChainLLM] = None
    if sage_llm is not None and sage_llm != llm:
        long_ctx_llm = ChatOpenAI(model_name=long_sage_llm) \
            if long_sage_llm is not None and long_sage_llm != sage_llm else None
        sage_model = LangChainLLM(ChatOpenAI(model_name=sage_llm), logger=logger,
                                  long_context_llm=long_ctx_llm,
                                  long_context_token_threshold=long_context_token_threshold)
    executor = Orchestrator(
        config=config,
        llm=primary_model,
        prompts=prompts,
        markdown_logger=logger,
        sage_llm=sage_model,
    )
    return executor


def _fix_model_name(model_name, required=False):
    if model_name is None:
        assert required is not None
        return model_name
    assert model_name in {'gpt-4', 'gpt-3.5', 'gpt-3.5-turbo'}
    if model_name == 'gpt-3.5':
        model_name = 'gpt-3.5-turbo'
    return model_name
