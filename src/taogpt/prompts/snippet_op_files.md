To create/update a file as deliverables for the task, add a file section:

`````markdown
MY_THOUGHT:
<explain the purpose of this file update>

## File: <file_path_name>

<content as a Markdown fenced block>
`````

Or go with the `WRITE_FILE` action.

## Create or update file

This is the prefer way to create/update content/package/project files as deliverables for the task.

Follow this template:

````
WRITE_FILE:
<explain the purpose of this file update>

## File: <file_path_name>

<content as a Markdown fenced block>
````

**Important note**: the Orchestator cannot handle big files, so keep files small and modular. Break large files into 
small ones, each focusing on one area, e.g. instead of creating one `script.js`, create `init.js`, `handle_event.js`,
`bunsiness_logic.js` etc.. In the worst case that a file has to be large, partition it into multiple part files 
named with `.partN` suffixes, e.g. `large_doc.md`, `large_doc.md.part1`, `large_doc.md.part2`, etc.
