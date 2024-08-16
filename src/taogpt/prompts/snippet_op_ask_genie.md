## Run code snippet

Run a code snippet in a sandboxed Python interpreter with standard library and numpy. It is a useful tool to help Tao
solve problems. It's stateful and previously defined globals can be used without redefining.

Following the template and the example below:

`````markdown
RUN_CODE_SNIPPET:
<brief explanation of what the code snippet is for>

```python
def fib(n):
    return fib(n-1) + f(n-2) if n > 1 else 1
print(f"Tao sucks at math but he's a superb Python programmer! Here is the answer {{fib(22)}}")
```
`````

1. Must paying attention to Python indentation.
2. Avoid trivial comments.
