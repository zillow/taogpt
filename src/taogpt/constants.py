from __future__ import annotations

WILL_ASK_QUESTIONS = 'I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED'
HERE_IS_MY_STEP_BY_STEP_PLAN = 'HERE_IS_MY_STEP_BY_STEP_PLAN'
MY_THOUGHT = 'MY_THOUGHT'
WILL_ASK_GENIE = 'RUN_CODE_SNIPPET'
REPORT_ERROR = 'I_FOUND_ERRORS'
WRITE_FILE = 'WRITE_FILE'
NEXT_I_WANT_TO_WORK_AT = "NEXT_I_WANT_TO_WORK_AT"
SUMMARIZE_FINAL_ANSWER = 'Summarize final answer'
UPDATE_FILES = "Update files for"
PRIOR_PROPOSAL = "Proposal"

ROLE_SYSTEM = 'system'
ROLE_TAO = 'Tao'
ROLE_SAGE = 'Sage'
ROLE_ORCHESTRATOR = 'orchestrator'
ROLE_USER = 'user'
ROLE_GENIE = 'python'

role_color_map = {
    'system': 'lightgrey',
    ROLE_USER: 'lightgreen',
    ROLE_TAO: 'lightyellow',
    'assistant': 'lightyellow',
    ROLE_ORCHESTRATOR: 'lightcyan',
    ROLE_SAGE: 'lightcyan',
    ROLE_GENIE: 'lightsteelblue'
}
