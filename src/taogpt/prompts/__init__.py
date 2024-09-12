from __future__ import annotations
import pathlib as _path

_template_dir = _path.Path(__file__).parent


def _read(path) -> str:
    with open(path, 'r') as f:
        return f.read()


class PromptDb:
    def __init__(self, path=_template_dir, ask_questions=True, ask_genie=True, file_support=True):
        self._ask_questions = ask_questions
        self._ask_genie = ask_genie
        self._file_support = file_support
        self.tao_intro=_read(path / 'tao.md')

        self._tao_templates=_read(path / 'tao_templates.md')
        self.tao_step_by_step_format=_read(path / 'tao_step_by_step_format.md')
        self.snippet_op_files =_read(path / 'snippet_op_files.md')
        self.snippet_op_ask_questions =_read(path / 'snippet_op_ask_questions.md')
        self.snippet_op_ask_genie =_read(path / 'snippet_op_ask_genie.md')

        self.snippet_next_step=_read(path / 'snippet_next_step.md')
        self.sage_rank_choices=_read(path / 'sage_rank_choices.md')
        self.sage_rank_instructions=_read(path / 'sage_rank_instructions.md')
        self.tao_next_step=_read(path / 'tao_next_step.md')
        self.tao_format_next_step=_read(path / 'tao_format_next_step.md')
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
        self.tao_check_merged_file=_read(path / 'tao_check_merged_file.md')
        self.tao_encourage_question=_read(path / 'tao_encourage_question.md')
        self.orchestrator_note_past_criticisms =_read(path / 'orchestrator_note_past_criticisms.md')

        self.tao_template = self._tao_templates.format(
            snippet_op_ask_genie=self.snippet_op_ask_genie if self._ask_genie else '',
            snippet_op_ask_questions=self.snippet_op_ask_questions if self._ask_questions else '',
            snippet_report_errors=self.snippet_report_errors,
            snippet_op_files=self.snippet_op_files if self._file_support else '')

    def reload(self, path: _path.Path=_template_dir) -> PromptDb:
        self.__init__(
            path, ask_questions=self._ask_questions, ask_genie=self._ask_genie, file_support=self._file_support)
        return self

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in vars(self).items() if isinstance(v, str)}

    @staticmethod
    def load_defaults(ask_questions=True, ask_genie=True, file_support=True):
        return PromptDb(ask_questions=ask_questions, ask_genie=ask_genie, file_support=file_support)
