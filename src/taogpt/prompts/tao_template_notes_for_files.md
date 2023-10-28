## Notes for file contents

The Orchestrator cannot tell if a piece of content is a file unless it's in the `### FILE:` sections
and inside a fenced Markdown block. If the task requires writing files, do not write file contents such as code
snippets outside of the `### FILE:` section. Whileit is OK to update previous files, try to write full and correct 
contents in one shot. Do not repeat a previous written file unless you need to update the files.

Bad file example:

````markdown
# I_WILL_ANSWER_DIRECTLY

```text
new file
```

### FILE: file1.txt
File from previous step.

```text
same content
```

### FILE: file2.txt

```text
new file
```
````

Issues of the above example:

* File file2.txt's content appears outside of `### FILE:` section
* Repeating file from previous step without change.
