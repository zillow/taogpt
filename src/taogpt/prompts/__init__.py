from __future__ import annotations
import dataclasses as _dc
import pathlib as _path

_template_dir = _path.Path(__file__).parent


@_dc.dataclass
class PromptDb:
    tao_intro: str
    tao_templates: str
    tao_template_direct_step_answer: str
    tao_template_notes_for_files: str
    tao_template_intuitive_answer: str
    orchestrator_ask_init_analysis: str
    orchestrator_rank_choices: str
    orchestrator_at_step: str
    orchestrator_next_step: str
    orchestrator_proceed: str
    orchestrator_proceed_to_step: str
    orchestrator_expand_parse_error: str
    orchestrator_parse_error: str
    orchestrator_prior_approaches: str
    orchestrator_criticisms: str
    orchestrator_error_noted: str
    orchestrator_summarize: str
    orchestrator_summarize_questions: str
    sage_intro: str
    sage_final_check: str
    sage_blame: str

    @staticmethod
    def load_defaults():
        return PromptDb(**PromptDb._reload())

    @staticmethod
    def _reload():
        def _read(path) -> str:
            with open(path, 'r') as f:
                return f.read()

        return dict(
            tao_intro=_read(_template_dir / 'tao.md'),
            tao_templates=_read(_template_dir / 'tao_templates.md'),
            tao_template_direct_step_answer=_read(_template_dir / 'tao_template_direct_step_answer.md'),
            tao_template_notes_for_files=_read(_template_dir / 'tao_template_notes_for_files.md'),
            tao_template_intuitive_answer=_read(_template_dir / 'tao_template_intuitive_answer.md'),
            orchestrator_ask_init_analysis=_read(_template_dir / 'orchestrator_ask_init_analysis.md'),
            orchestrator_rank_choices=_read(_template_dir / 'orchestrator_rank_choices.md'),
            orchestrator_at_step=_read(_template_dir / 'orchestrator_at_step.md'),
            orchestrator_next_step=_read(_template_dir / 'orchestrator_next_step.md'),
            orchestrator_proceed=_read(_template_dir / 'orchestrator_proceed.md'),
            orchestrator_proceed_to_step=_read(_template_dir / 'orchestrator_proceed_to_step.md'),
            orchestrator_expand_parse_error=_read(_template_dir / 'orchestrator_expand_parse_error.md'),
            orchestrator_parse_error=_read(_template_dir / 'orchestrator_parse_error.md'),
            orchestrator_prior_approaches=_read(_template_dir / 'orchestrator_prior_approaches.md'),
            orchestrator_criticisms=_read(_template_dir / 'orchestrator_criticisms.md'),
            orchestrator_error_noted=_read(_template_dir / 'orchestrator_error_noted.md'),
            orchestrator_summarize=_read(_template_dir / 'orchestrator_summarize.md'),
            orchestrator_summarize_questions=_read(_template_dir / 'orchestrator_summarize_questions.md'),
            sage_intro=_read(_template_dir / 'sage.md'),
            sage_final_check=_read(_template_dir / 'sage_final_check.md'),
            sage_blame=_read(_template_dir / 'sage_blame.md'),
        )
