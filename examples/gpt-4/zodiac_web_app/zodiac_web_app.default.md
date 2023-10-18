# GPT-4 default system prompt (2023/10/17)

**user**: Write a full and executable Python web application that ask for user's date of birth and render a page showing the
user's Chinese zodiac sign. Do not worry about aesthetics, just use text and textual buttons. I need to a full
project with all server and client side asset files. I know how to deploy and test. Just give me a
deployable project.

**gpt-4**:

Sure, here is a simple Flask application that does what you asked for.

First, let's create the project structure:

```
/myapp
    /static
        /css
            style.css
    /templates
        index.html
        result.html
    app.py
```

Now, let's create the files:

**app.py**

```python
from flask import Flask, render_template, request
from datetime import datetime

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        dob = request.form.get('dob')
        dob = datetime.strptime(dob, '%Y-%m-%d')
        zodiac = get_zodiac(dob.year)
        return render_template('result.html', zodiac=zodiac)
    return render_template('index.html')

def get_zodiac(year):
    zodiacs = ['Monkey', 'Rooster', 'Dog', 'Pig', 'Rat', 'Ox', 'Tiger', 'Rabbit', 'Dragon', 'Snake', 'Horse', 'Sheep']
    return zodiacs[year % 12]

if __name__ == '__main__':
    app.run(debug=True)
```

**/templates/index.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Chinese Zodiac</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <form method="POST">
        <label for="dob">Enter your date of birth:</label>
        <input type="date" id="dob" name="dob" required>
        <input type="submit" value="Submit">
    </form>
</body>
</html>
```

**/templates/result.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Chinese Zodiac</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <h1>Your Chinese Zodiac is: {{ zodiac }}</h1>
</body>
</html>
```

**/static/css/style.css**

```css
body {
    font-family: Arial, sans-serif;
}

form {
    margin-top: 20px;
}

label, input {
    display: block;
    margin-bottom: 10px;
}
```

To run the application, navigate to the project directory and run `python app.py`. The application will be accessible at `http://localhost:5000`.
