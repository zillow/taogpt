from __future__ import annotations
import dataclasses as _dc
import pathlib as _path


@_dc.dataclass
class PromptDb:
    system_step_expansion: str # main system prompt
    tao_templates: str
    tao_template_direct_step_answer: str
    tao_template_intuitive_answer: str
    orchestrator_ask_init_analysis: str
    orchestrator_direct_solve: str
    orchestrator_eval_strategy_choices: str
    orchestrator_next_step: str
    orchestrator_proceed: str
    orchestrator_proceed_to_step: str
    orchestrator_expand_parse_error: str
    orchestrator_parse_error: str
    orchestrator_next_step_parse_error: str
    orchestrator_critics: str
    orchestrator_summarize: str
    orchestrator_summarize_questions: str
    sage: str
    sage_final_check: str
    intuitive_answer: str

    @staticmethod
    def load_defaults():
        path = _path.Path(__file__).parent

        def _read(path):
            with open(path, 'r') as f:
                return f.read()

        return PromptDb(
            system_step_expansion=_read(path / 'tao.md'),
            tao_templates=_read(path / 'tao_templates.md'),
            tao_template_direct_step_answer=_read(path / 'tao_template_direct_step_answer.md'),
            tao_template_intuitive_answer=_read(path / 'tao_template_intuitive_answer.md'),
            orchestrator_ask_init_analysis=_read(path / 'orchestrator_ask_init_analysis.md'),
            orchestrator_direct_solve=_read(path / 'orchestrator_direct_solve.md'),
            orchestrator_eval_strategy_choices=_read(path / 'orchestrator_rank_choices.md'),
            orchestrator_next_step=_read(path / 'orchestrator_next_step.md'),
            orchestrator_proceed=_read(path / 'orchestrator_proceed.md'),
            orchestrator_proceed_to_step=_read(path / 'orchestrator_proceed_to_step.md'),
            orchestrator_expand_parse_error=_read(path / 'orchestrator_expand_parse_error.md'),
            orchestrator_parse_error=_read(path / 'orchestrator_parse_error.md'),
            orchestrator_next_step_parse_error=_read(path / 'orchestrator_next_step_parse_error.md'),
            orchestrator_critics=_read(path / 'orchestrator_critics.md'),
            orchestrator_summarize=_read(path / 'orchestrator_summarize.md'),
            orchestrator_summarize_questions=_read(path / 'orchestrator_summarize_questions.md'),
            sage=_read(path / 'sage.md'),
            sage_final_check=_read(path / 'sage_final_check.md'),
            intuitive_answer=_read(path / 'intuitive_answer.md'),
        )
