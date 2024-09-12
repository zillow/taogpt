import taogpt.file_support
from taogpt import parsing


def test_gather_file_sections():
    text = """Here is your file.
    
The HTML template for the main page.

```html
<!DOCTYPE html>
<html lang="en">
</html>
```"""
    content_type, content, _, _ = taogpt.file_support.gather_file_contents(text)
    assert content_type == 'html'
    assert content == """<!DOCTYPE html>
<html lang="en">
</html>"""


def test_gather_multi_file_sections():
    text = """Here is your file.
    
```html
<!DOCTYPE html>
<html lang="en">
</html>
```

another

````markdown
  some markdown text
```
  nested block
```
````
"""
    try:
        taogpt.file_support.gather_file_contents(text)
        assert False, "Expecting parse error not raised"
    except parsing.ParseError as e:
        assert 'Need exactly one file content fenced block' in str(e)


def test_collect_files_with_quoted_path():
    file_content = """Multi line
text"""
    full = f"""
# File: `foo.txt`

```text
{file_content}
```

## File: "foo2.txt"

some description about this file

```text
{file_content}
```
"""
    files = taogpt.file_support.collect_files(full)
    assert len(files) == 2
    assert files['foo.txt'].content_type == 'text'
    assert files['foo.txt'].content == file_content
    assert files['foo2.txt'].content_type == 'text'
    assert files['foo2.txt'].content == file_content
    assert 'some description' in files['foo2.txt'].description


def test_collect_files_with_nested_headings():
    file_content = """Multi line
text"""
    full = f"""# Heading 1

## heading 2

## File: foo.txt

```text
{file_content}
```

## File: foo2.txt

### About this file
some description about this file

```text
{file_content}
```
"""
    files = taogpt.file_support.collect_files(full)
    assert len(files) == 2
    assert files['foo.txt'].content_type == 'text'
    assert files['foo.txt'].content == file_content
    assert 'some description' not in files['foo.txt'].description
    assert files['foo2.txt'].content_type == 'text'
    assert files['foo2.txt'].content == file_content
    assert 'some description' in files['foo2.txt'].description
