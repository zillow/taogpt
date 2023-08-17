dummy_dead_end_check_response = [
    """[I'm happy! {step_id}]
true
""",
]


dummy_expand_steps = [
    """
1. translate Tao Te Ching {step_id}
2. count number of words {step_id}
""",
    """# I_WILL_ANSWER_DIRECTLY
## MY_ANSWER:
13

## SCRATCHPAD:
v = 'answer is 13 at {step_id}'
""",
]


dummy_ranking_response = [
    """
1. score: 7.0 [I don't like this {step_id}]
2. score: 9.0 [I like this {step_id}]
"""
]


dummy_next_step_response = [
    "I want to work on: cool project {step_id}",
    "I want to work on: cool project {step_id}",
    "I want to work on: cool project {step_id}",
    "I'm done"
]


_overrides = dict()


def add_override_dummy(reason, content):
    global _overrides
    _overrides[reason] = content


def get_dummy(reason, nth: int) -> str:
    global _overrides
    if reason == 'check_dead_end':
        dummies = dummy_dead_end_check_response
    elif reason == 'expand_choices':
        dummies = dummy_expand_steps
    elif reason == 'rank_choices':
        dummies = dummy_ranking_response
    elif reason == 'next_step':
        dummies = dummy_next_step_response
    else:
        return 'DUMMY'
    overridden = _overrides.get(reason, None)
    if overridden is not None:
        return overridden
    return dummies[nth] if nth < len(dummies) else dummies[-1]
