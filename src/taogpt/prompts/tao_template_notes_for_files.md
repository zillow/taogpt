## Notes for `FILE:` sections

If you need to write out files, 

* Write out the content in markdown fenced code block under its own file section.
* If you are writing out a file, do not repeat its content in the "answer and explanation" section. 
* Try to write complete file content at once, avoid partial or incomplete contents; avoid updating files.
* If you do update a previous file, ensure the original contents are kept.

Bad file example:

````markdown
# I_WILL_ANSWER_DIRECTLY

```python
def have_fun():
    # to be implemented
```

### FILE: setup.py
Setup from previous step.

```python
def setup():
    settings = {'mode': 1}
```

### FILE: fun.py

```python
def have_fun():
    # to be implemented
```
````

Issues:
* File fun.py's content appears outside of `### FILE:` section
* File from previous step is repeated here without change.
