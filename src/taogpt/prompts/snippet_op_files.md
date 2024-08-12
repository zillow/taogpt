## Write file

If the task want a file as the deliverable. However, contents **NOT** for deliverable, e.g. for 
illustration/explanation, should be outputs in direct answer/thought. 

Template and example:

````markdown
# WRITE_FILE
<explain the purpose of this file update>

### FILE: <file_path_name>

```python
// content from previous

def foo():
    x += 1 

// rest of the content
```

<declare the next step to work at; see the notes below.>
````

Note:
* Write one file at a time.
* Must have a file path name relative to current directory following the Unix convention; directories will be created.
* When updating a file, OK to omit existing contents but must add notes about it.
* The `FILE:` section can only be used by `WRITE_FILE` actions, not other types.
