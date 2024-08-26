{intent} Report errors and warnings found, but avoid nitpicking, in this format:

At step#<ID>: <step description>: <issue found and reason>. Severity: `error` or `warning`. 
    Already fixed in subsequentstep: yes/no;
    Recommendation: <any suggestion>.
...
At step#<ID>: affected by issue found at step#<previous ID>: <step description>.

where `"step#<ID>: <step description>"` can be found in the bracket "[at step#<ID>: <step_description>]" of the steps 
(without the brackets.)

Directions:
* Worship Occam's razor. Prefer specific solution according to the scope of the task step, neither too generic nor excessively detailed.
* For any step, do NOT report issues that should be, or already been, taken care of by different/subsequent step. For example, dummy/placeholder/temporary values that are to be taken care of later.
* A `HERE_IS_MY_STEP_BY_STEP_PLAN` plan itself does not provide any answer; its sub-steps should.
* We should generally respect user's assumptions even if they are inaccurate as assumptions are meant to simplify the problem.
* Subsequent steps depending on the issue should be reported an step as `affected by` only if it must be changed or fixed; if a step depends on this step but not affected by the particular issue, no need to report.
