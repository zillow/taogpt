If you see any errors or inconsistencies in the step executed so far, response with **specific** errors and prior steps 
responsible in the following format:

````markdown
I_FOUND_ERRORS:

**At step#<ID>: <step description>**: <issue found and reason>. Severity: `error` or `warning`. 
Already fixed in subsequent step: yes/no;
Recommendation: <any suggestion>.

...

**At step#<ID>: affected by issue found at step#<previous ID>**: <step description>.
````

where `"step#<ID>: <step description>"` can be found in the bracket "[at step#<ID>: <step_description>]" of the steps 
(without the brackets.)

Report only real errors while avoid nitpicking.
