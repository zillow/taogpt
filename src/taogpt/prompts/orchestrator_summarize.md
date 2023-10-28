Tao, the above is your final problem solving trajectory. Present a final answer to the user. The user would not read 
the problem solving session, so make sure to include **full and complete** details requested by the task problem.

Start with heading `# FINAL_ANSWER`.

If the task involves writing out files, make sure to fill in any missing files or contents. But to save spaces, 
don't repeat unchanged file contents. You should write out files in the `### FILE:` sections. Do not repeat any file 
contents outside of the file sections.

## Response Template and Example

In the example summary below, Orchestrator details the problem solving steps and lists this file written:

`````markdown
... steps during problem solving ...

---

### FILE: existing_file.py
```python
def do_something():
    ...
```
`````

And Tao summarizes to:

````markdown
# FINAL_ANSWER

```python
def do_something(p1, p2):
    ...
```

### FILE: new_file.py 
```python
def do_something_else():
    ...
```
````

* Good: writing out new file missing from the problem solving session in `### FILE:` sections.
* Bad: repeating unchanged content of existing file.
* Bad: file content outside of `### FILE:` section.
* Bad: no full answer given.
