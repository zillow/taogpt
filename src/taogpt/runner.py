import pathlib as _p
import re
import typing as _t
from io import TextIOBase as _TextIOBase
import pickle as _pickle

from taogpt import Pause, MarkdownLogger, PromptDb, Config, GeneratedFile
from taogpt.llm_model import (
    LangChainLLM,
    fix_model_name,
    get_long_model,
    ChatOpenAIWithGenInfo as _ChatOpenAI
)
from taogpt.orchestrator import Orchestrator
from io import TextIOBase as _TextIO


def solve_problem(user_task: str, log_path: str, config: Config,
                  llm: str, long_llm: str, long_sage_llm: str, sage_llm: str,
                  long_context_token_threshold: int,
                  user_input_fn: _t.Callable[[str], str], console_out: _TextIO|None,
                  debug=False):
    executor = create_orchestrator(config, log_path, llm, long_llm, sage_llm, long_sage_llm,
                                   long_context_token_threshold, console_out, debug=debug)
    executor.set_input_fn(user_input_fn)
    pause: Pause|None = None
    try:
        executor.start(user_task)
    except Pause as e:
        pause = e
    _continue_solving(executor, log_path, console_out, pause)


def load_and_resume_problem(
        states: dict[str, _t.Any],
        log_path: str,
        config: Config,
        llm: str,
        long_llm: str=None,
        long_sage_llm: str=None,
        sage_llm: str=None,
        long_context_token_threshold: int=3000,
        user_input_fn: _t.Callable[[str], str]=input,
        console_out: _TextIO=None,
        debug=False):
    executor = create_orchestrator(config, log_path, llm, long_llm, sage_llm, long_sage_llm,
                                   long_context_token_threshold, console_out, debug=debug)
    executor.set_input_fn(user_input_fn)
    executor._chain = states['chain']
    for step in executor.chain:
        print(step)
    pause: Pause|None = None
    log_final_chain(executor, log_path, console_out=console_out)
    try:
        executor.resume(0)
    except Pause as e:
        pause = e
    _continue_solving(executor, log_path, console_out, pause)


def _continue_solving(executor, log_path, console_out, pause):
    while pause is not None:
        log_final_chain(executor, log_path, console_out=console_out)
        resume: str|None = None
        while resume is None or re.match(r"\d+|no", resume) is None:
            resume = input(f"{str(pause)}\nReply amount of tokens to add (0 is OK) and continue, 'no' to cancel: ") \
                .strip().lower()
        if resume == 'no':
            break
        pause = None
        try:
            executor.resume(additional_tokens=int(resume), additional_sage_tokens=int(resume) // 3)
        except Pause as e:
            pause = e
    log_final_chain(executor, log_path, console_out=console_out)


def log_final_chain(executor, log_path,
                    file_name='taogpt_results.final.md',
                    pickle_file='taogpt_states.pkl',
                    console_out: _TextIOBase=None):
    logger = MarkdownLogger(_p.Path(log_path) / file_name, console_out=console_out)
    executor.log_configs(logger)
    logger.log_conversation(executor.show_conversation_thread(with_header=True))
    logger.log(f"**total tokens**: {executor.llm.total_tokens}")
    for path, file in GeneratedFile.collect_files(executor.chain).items():
        path = re.sub(r"[\"\'`]", "", path)
        full_path = _p.Path(log_path) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(file.content)
    with open(_p.Path(log_path) / pickle_file, 'wb') as f:
        _pickle.dump(dict(config=executor.config,
                          llm=executor.llm.model_id,
                          sage_llm=executor.sage_llm.model_id if executor.sage_llm is not None else None,
                          chain=executor.chain), f)


def create_orchestrator(
        config: Config,
        log_path: str,
        llm: str,
        long_llm: str=None,
        sage_llm: str=None,
        long_sage_llm: str=None,
        long_context_token_threshold: int=3000,
        log_to_stdout: _TextIO=None,
        debug=False):
    llm = fix_model_name(llm, required=True)
    sage_llm = fix_model_name(sage_llm, default_to=llm)
    long_llm = fix_model_name(get_long_model(long_llm), default_to=llm)
    long_sage_llm = fix_model_name(get_long_model(long_sage_llm), default_to=sage_llm)
    prompts = PromptDb.load_defaults()
    logger = MarkdownLogger(_p.Path(log_path) / 'taogpt_log.md', log_debug=debug, console_out=log_to_stdout)
    long_ctx_llm = _ChatOpenAI(model_name=long_llm) if long_llm is not None and long_llm != llm else None
    primary_model = LangChainLLM(_ChatOpenAI(model_name=llm), logger=logger,
                                 long_context_llm=long_ctx_llm,
                                 long_context_token_threshold=long_context_token_threshold)
    sage_model: LangChainLLM|None = None
    if sage_llm is not None and sage_llm != llm:
        long_ctx_llm = _ChatOpenAI(model_name=long_sage_llm) \
            if long_sage_llm is not None and long_sage_llm != sage_llm else None
        sage_model = LangChainLLM(_ChatOpenAI(model_name=sage_llm), logger=logger,
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
