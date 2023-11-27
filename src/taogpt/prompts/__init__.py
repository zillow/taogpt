from __future__ import annotations
import dataclasses as _dc
import pathlib as _path

_template_dir = _path.Path(__file__).parent


def _read(path) -> str:
    with open(path, 'r') as f:
        return f.read()


@_dc.dataclass
class PromptDb:
    tao_intro: str = _read(_template_dir / 'tao.md')
    tao_templates: str = _read(_template_dir / 'tao_templates.md')
    tao_template_direct_step_answer: str = _read(_template_dir / 'tao_template_direct_step_answer.md')
    tao_template_notes_for_files: str = _read(_template_dir / 'tao_template_notes_for_files.md')
    tao_template_intuitive_answer: str = _read(_template_dir / 'tao_template_intuitive_answer.md')
    orchestrator_ask_init_analysis: str = _read(_template_dir / 'orchestrator_ask_init_analysis.md')
    orchestrator_rank_choices: str = _read(_template_dir / 'orchestrator_rank_choices.md')
    orchestrator_at_step: str = _read(_template_dir / 'orchestrator_at_step.md')
    orchestrator_next_step: str = _read(_template_dir / 'orchestrator_next_step.md')
    orchestrator_proceed: str = _read(_template_dir / 'orchestrator_proceed.md')
    orchestrator_proceed_to_step: str = _read(_template_dir / 'orchestrator_proceed_to_step.md')
    orchestrator_expand_parse_error: str = _read(_template_dir / 'orchestrator_expand_parse_error.md')
    orchestrator_parse_error: str = _read(_template_dir / 'orchestrator_parse_error.md')
    orchestrator_prior_approaches: str = _read(_template_dir / 'orchestrator_prior_approaches.md')
    orchestrator_criticisms: str = _read(_template_dir / 'orchestrator_criticisms.md')
    orchestrator_error_noted: str = _read(_template_dir / 'orchestrator_error_noted.md')
    orchestrator_summarize: str = _read(_template_dir / 'orchestrator_summarize.md')
    orchestrator_summarize_questions: str = _read(_template_dir / 'orchestrator_summarize_questions.md')
    sage_intro: str = _read(_template_dir / 'sage.md')
    sage_final_check: str = _read(_template_dir / 'sage_final_check.md')
    sage_blame: str = _read(_template_dir / 'sage_blame.md')

    @staticmethod
    def load_defaults():
        return PromptDb()
