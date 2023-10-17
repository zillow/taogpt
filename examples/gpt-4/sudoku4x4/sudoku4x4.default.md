# GPT-4 default system prompt (2023/10/10)

Let's solve this Sudoku one line at a time.

Here's the given Sudoku for reference:

```text
4 3 _ 1
1 _ 4 3
2 _ 3 _
3 _ _ 2
```

First, let's solve the first row. The missing number in this row is 2.

```text
4 3 2 1
1 _ 4 3
2 _ 3 _
3 _ _ 2
```

Next, let's solve the second row. The missing number in this row is 2.

```text
4 3 2 1
1 2 4 3
2 _ 3 _
3 _ _ 2
```

Now, let's solve the third row. We have numbers 3 and 2 already filled in. The missing numbers are 4 and 1, 4 can be filled in the 2nd column and 1 can be filled in the 4th column.

```text
4 3 2 1
1 2 4 3
2 4 3 1
3 _ _ 2
```

Finally, let's solve the last row. The missing numbers are 4 and 1 which can be filled in the 2nd and 3rd column respectively.

```text
4 3 2 1
1 2 4 3
2 4 3 1
3 4 1 2
```

Therefore, the final filled Sudoku is:

```text
4 3 2 1
1 2 4 3
2 4 3 1
3 4 1 2
```
