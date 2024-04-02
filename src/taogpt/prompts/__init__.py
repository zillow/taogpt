from __future__ import annotations
import dataclasses as _dc
import pathlib as _path

_template_dir = _path.Path(__file__).parent


@_dc.dataclass
class PromptDb:
    tao_intro: str
    tao_templates: str
    snippet_direct_step_answer: str
    snippet_notes_for_files: str
    snippet_intuitive_answer: str
    tao_ask_init_analysis: str
    sage_rank_choices: str
    sage_rank_instructions: str
    orchestrator_at_step: str
    tao_next_step: str
    tao_proceed: str
    tao_proceed_intuitively: str
    tao_proceed_to_step: str
    orchestrator_expand_parse_error: str
    orchestrator_parse_error: str
    tao_prior_approaches: str
    orchestrator_criticisms: str
    tao_summarize: str
    tao_summarize_questions: str
    sage_intro: str
    sage_final_check: str
    sage_blame: str
    tao_fix_issues: str
    snippet_report_errors: str
    sage_merge_criticisms: str
    _tao_expand_first_step: str | None = None
    _tao_expand_any_step: str | None = None

    @property
    def tao_expand_first_step(self) -> str:
        assert self._tao_expand_first_step is not None
        return self._tao_expand_first_step

    @property
    def tao_expand_any_step(self) -> str:
        assert self._tao_expand_any_step is not None
        return self._tao_expand_any_step

    def __post_init__(self):
        self._tao_expand_first_step = self.tao_templates.format(
            snippet_report_errors=self.snippet_report_errors,
            snippet_direct_answer=self.snippet_intuitive_answer,
            snippet_notes_for_files=self.snippet_notes_for_files)
        self._tao_expand_any_step = self.tao_templates.format(
            snippet_report_errors=self.snippet_report_errors,
            snippet_direct_answer=self.snippet_direct_step_answer,
            snippet_notes_for_files=self.snippet_notes_for_files)
        self.tao_next_step = self.tao_next_step.format(snippet_report_errors=self.snippet_report_errors)

    def to_dict(self):
        return _dc.asdict(self)

    @staticmethod
    def load_defaults():
        return PromptDb._reload()

    @staticmethod
    def _reload():
        def _read(path) -> str:
            with open(path, 'r') as f:
                return f.read()

        return PromptDb(
            tao_intro=_read(_template_dir / 'tao.md'),
            tao_templates=_read(_template_dir / 'tao_templates.md'),
            snippet_direct_step_answer=_read(_template_dir / 'snippet_direct_step_answer.md'),
            snippet_notes_for_files=_read(_template_dir / 'snippet_notes_for_files.md'),
            snippet_intuitive_answer=_read(_template_dir / 'snippet_intuitive_answer.md'),
            tao_ask_init_analysis=_read(_template_dir / 'tao_ask_init_analysis.md'),
            sage_rank_choices=_read(_template_dir / 'sage_rank_choices.md'),
            sage_rank_instructions=_read(_template_dir / 'sage_rank_instructions.md'),
            orchestrator_at_step=_read(_template_dir / 'orchestrator_at_step.md'),
            tao_next_step=_read(_template_dir / 'tao_next_step.md'),
            tao_proceed=_read(_template_dir / 'tao_proceed.md'),
            tao_proceed_intuitively=_read(_template_dir / 'tao_proceed_intuitively.md'),
            tao_proceed_to_step=_read(_template_dir / 'tao_proceed_to_step.md'),
            orchestrator_expand_parse_error=_read(_template_dir / 'orchestrator_expand_parse_error.md'),
            orchestrator_parse_error=_read(_template_dir / 'orchestrator_parse_error.md'),
            tao_prior_approaches=_read(_template_dir / 'tao_prior_approaches.md'),
            orchestrator_criticisms=_read(_template_dir / 'orchestrator_criticisms.md'),
            tao_summarize=_read(_template_dir / 'tao_summarize.md'),
            tao_summarize_questions=_read(_template_dir / 'tao_summarize_questions.md'),
            sage_intro=_read(_template_dir / 'sage.md'),
            sage_final_check=_read(_template_dir / 'sage_final_check.md'),
            sage_blame=_read(_template_dir / 'sage_blame.md'),
            tao_fix_issues=_read(_template_dir / 'tao_fix_issues.md'),
            snippet_report_errors=_read(_template_dir / 'snippet_report_errors.md'),
            sage_merge_criticisms=_read(_template_dir / 'sage_merge_criticisms.md'),
        )
