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

**Important notes**: the Orchestator cannot handle big files, so keep files small and modular and break large files 
into small ones, each focusing on one area.
