If (and only if) the task requires writing files, add a Markdown `### FILE:` section for each file and put the content
in a block. Example with problems:

````markdown
### FILE:
<short description of this file>

```python
# ... (previous parts of this file)

def foo():
    # ... (previous logic of the method)
    x += 1 
# ... (previous parts of this file)
```
````
Problems:
* Missing file name path.
* Missing contents from previous version.

Note: 
* There is no need to create directories; if a file name has a parent directory, it will be created by the Orchestrator.
* Orchestrator has no way to move or delete files. Orchestrator will always collect the **last written** content 
of a file, therefore it is very important to copy the full content when updating a file, else we would lose some
content.
