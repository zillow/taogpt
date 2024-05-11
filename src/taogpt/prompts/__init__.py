from __future__ import annotations
import pathlib as _path

_template_dir = _path.Path(__file__).parent


def _read(path) -> str:
    with open(path, 'r') as f:
        return f.read()


class PromptDb:
    def __init__(self, path=_template_dir):
        self.tao_intro=_read(path / 'tao.md')
        self.tao_templates=_read(path / 'tao_templates.md')
        self.snippet_intuitive_answer =_read(path / 'snippet_intuitive_answer.md')
        self.snippet_direct_step_answer=_read(path / 'snippet_direct_step_answer.md')
        self.snippet_next_step=_read(path / 'snippet_next_step.md')
        self.snippet_notes_for_files=_read(path / 'snippet_notes_for_files.md')
        self.sage_rank_choices=_read(path / 'sage_rank_choices.md')
        self.sage_rank_instructions=_read(path / 'sage_rank_instructions.md')
        self.tao_next_step=_read(path / 'tao_next_step.md')
        self.tao_proceed=_read(path / 'tao_proceed.md')
        self.tao_proceed_intuitively=_read(path / 'tao_proceed_intuitively.md')
        self.tao_proceed_to_step=_read(path / 'tao_proceed_to_step.md')
        self.orchestrator_parse_error=_read(path / 'orchestrator_parse_error.md')
        self.tao_prior_approaches=_read(path / 'tao_prior_approaches.md')
        self.tao_summarize=_read(path / 'tao_summarize.md')
        self.tao_summarize_partial=_read(path / 'tao_summarize_partial.md')
        self.tao_summarize_questions=_read(path / 'tao_summarize_questions.md')
        self.sage_intro=_read(path / 'sage.md')
        self.sage_check_answer=_read(path / 'sage_check_answer.md')
        self.tao_fix_issues=_read(path / 'tao_fix_issues.md')
        self.snippet_report_errors=_read(path / 'snippet_report_errors.md')
        self.sage_merge_criticisms=_read(path / 'sage_merge_criticisms.md')
        self.tao_ensure_updated_file_integrity=_read(path / 'tao_ensure_updated_file_integrity.md')
        self.tao_encourage_question=_read(path / 'tao_encourage_question.md')
        self.orchestrator_note_past_criticisms =_read(path / 'orchestrator_note_past_criticisms.md')

        # substituted
        self._tao_expand_init_step = self.tao_templates.format(
            snippet_report_errors=self.snippet_report_errors,
            snippet_direct_answer=self.snippet_intuitive_answer,
            snippet_notes_for_files=self.snippet_notes_for_files)
        self._tao_expand_any_step = self.tao_templates.format(
            snippet_report_errors=self.snippet_report_errors,
            snippet_direct_answer=self.snippet_direct_step_answer,
            snippet_notes_for_files=self.snippet_notes_for_files)

    def reload(self, path: _path.Path=_template_dir) -> PromptDb:
        self.__init__(path)
        return self

    @property
    def tao_expand_init_step(self) -> str:
        assert self._tao_expand_init_step is not None
        return self._tao_expand_init_step

    @property
    def tao_expand_any_step(self) -> str:
        assert self._tao_expand_any_step is not None
        return self._tao_expand_any_step

    def to_dict(self) -> dict[str, str]:
        return vars(self)

    @staticmethod
    def load_defaults():
        return PromptDb()
