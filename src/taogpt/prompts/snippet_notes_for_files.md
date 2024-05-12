If the task want a file as the deliverable, add a Markdown `### FILE:` section for each file and put the content
in a block. Example:

````markdown
### FILE: path/to/file
<short description of this file>

```python
// content from previous

def foo():
    x += 1 

// rest of the content
```
````

Note:
* Must have a file path name.
* When updating a file, OK to omit existing contents with notes.
* There is no need to create directories; if a file name has a parent directory, it will be created by the Orchestrator.
* Orchestrator has no way to move or delete files.
