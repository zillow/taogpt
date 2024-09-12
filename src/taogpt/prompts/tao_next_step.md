We last worked at step {last_step} of step-by-step plan {at_plan}. What do you want to work on next? Choose one 
and only one of the following actions:

(Step identifier format: "step#<ID>: <step description>")

## Choose the next step to work on

Provide the following details:

* Next step to work at: "<step description>" or "all done" if the *whole* task is completed. Briefly describe the 
  reason to choose this step.
* The "step#<ID>: <step description>" of step-by-step plan which the next step belongs to.
* The the ordinal sequence number of the next step within the plan, not to be confused with a step ID; or -1 if next 
  step is "all done". If the next step is not in the original plan, add a note about this.
* Is the next step being repeated in a loop?
* Difficulty level of the next step from 1 to 10 (hardest).
* Is the current parent step plan {at_plan} done or not?

where "step#<ID>: <step description>" can be found in the bracket "[at step#<ID>: <step_description>]" of the steps
(without the brackets.)

## Report errors

{snippet_report_errors}
