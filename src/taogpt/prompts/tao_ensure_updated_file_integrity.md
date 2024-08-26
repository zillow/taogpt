You've written and updated this file.

First, find out: is update#2 a partial update? are there any contents from update#1 missing from update#2? are the
content missing due to update#2 only showing partial file content or indeed meant to be removed by update#2?

Next, merge and consolidate update#1 and update#2, and present the final, complete content of this file.

**Don't be lazy. Must keep all contents from both updates; otherwise, the file would be left corrupted.**

Follow this format:
```markdown
## Update analysis
<... analysis of the differences between the two updates as explain above ...>

## File: <original file path>

<description of this file>
<the reasons for update#1 and update#2>

<... merged content in Markdown fenced block (with the same file type declaration as the original) ...>
```
---
Bad merge example:
```python
def method1():
    print("do something 1 from update@1")

def method2():
    print("do something 2 from update#1")

# do something 3 goes here
# do something 4 goes here

def method_X():
    print("do X from update#2")
```
Issue: contents (e.g. `method3` and `method4`) from update#1 are replaced with substituted comments; should include 
the full contents instead.
---
