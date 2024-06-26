from __future__ import annotations

WILL_ASK_QUESTIONS = 'I_NEED_TO_ASK_SOME_QUESTIONS_BEFORE_I_PROCEED'
HERE_IS_MY_STEP_BY_STEP_PLAN = 'HERE_IS_MY_STEP_BY_STEP_PLAN'
MY_THOUGHT = 'MY_THOUGHT'
WILL_ASK_GENIE = 'LET_ME_ASK_THE_PYTHON_GENIE'
REPORT_ERROR = 'I_FOUND_ERRORS'
MY_ANSWER = 'MY_ANSWER'
NEXT_I_WANT_TO_WORK_AT = "NEXT_I_WANT_TO_WORK_AT"
FINAL_ANSWER = 'FINAL_ANSWER'
SUMMARIZE_FINAL_ANSWER = 'Summarize final answer'
UPDATE_FILES = "Update files for"
PRIOR_PROPOSAL = "Proposal"

ROLE_SYSTEM = 'system'
ROLE_TAO = 'Tao'
ROLE_SAGE = 'Sage'
ROLE_ORCHESTRATOR = 'orchestrator'
ROLE_USER = 'user'
ROLE_GENIE = 'python'

USER_ANSWERS = 'USER_ANSWERS'

FREE_TEXT = '_FREE'

role_color_map = {
    'system': 'lightgrey',
    ROLE_USER: 'lightgreen',
    ROLE_TAO: 'lightyellow',
    'assistant': 'lightyellow',
    ROLE_ORCHESTRATOR: 'lightcyan',
    ROLE_SAGE: 'lightcyan',
    ROLE_GENIE: 'lightsteelblue'
}
