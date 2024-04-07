# GPT-4-turbo default system prompt (2024/03/11)

**user:**

I need a web application that takes a date as input and renders a page showing the user's Chinese zodiac sign. We
don't have any image assets, just use text buttons, but the app should be pleasant to use.

For simplicity, assume the lunar new years always start on February, 4 every year.

Give me a full Python project with all server and client side asset files. No need to deploy or test it. I will do so.

**assistant:**

Creating a full Python project for a web application involves several components. Below, I'll provide you with a simple Flask application that serves this purpose. Flask is a micro web framework for Python that is easy to use and suitable for small projects like this one.

First, you'll need to install Flask if you haven't already. You can do this using pip:

```bash
pip install Flask
```

Now, let's create the project structure:

```
chinese_zodiac_app/
│
├── app.py
├── templates/
│   ├── index.html
│   └── result.html
└── static/
    └── style.css
```

Here's the content for each file:

`app.py`:

```python
from flask import Flask, render_template, request
from datetime import datetime

app = Flask(__name__)

# Chinese Zodiac signs in order
zodiac_signs = [
    "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat",
    "Monkey", "Rooster", "Dog", "Pig"
]

# Function to calculate Chinese Zodiac sign
def get_zodiac_sign(year):
    # 1900 is the reference year for the Rat sign
    return zodiac_signs[(year - 1900) % 12]

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/result', methods=['POST'])
def result():
    date_str = request.form['birthdate']
    birthdate = datetime.strptime(date_str, '%Y-%m-%d')
    year = birthdate.year
    if birthdate.month < 2 or (birthdate.month == 2 and birthdate.day < 4):
        year -= 1
    sign = get_zodiac_sign(year)
    return render_template('result.html', zodiac_sign=sign, year=year)

if __name__ == '__main__':
    app.run(debug=True)
```

`templates/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Chinese Zodiac Sign Finder</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <h1>Find Your Chinese Zodiac Sign</h1>
        <form action="/result" method="post">
            <label for="birthdate">Enter your birthdate:</label>
            <input type="date" id="birthdate" name="birthdate" required>
            <button type="submit">Submit</button>
        </form>
    </div>
</body>
</html>
```

`templates/result.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Your Chinese Zodiac Sign</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <h1>Your Chinese Zodiac Sign</h1>
        <p>In the year {{ year }}, the Chinese Zodiac sign is <strong>{{ zodiac_sign }}</strong>.</p>
        <a href="/">Try another date</a>
    </div>
</body>
</html>
```

`static/style.css`:

```css
body {
    font-family: Arial, sans-serif;
    background-color: #f4f4f4;
    margin: 0;
    padding: 0;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
}

.container {
    background-color: #fff;
    padding: 20px;
    border-radius: 5px;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    text-align: center;
}

h1 {
    color: #333;
}

button {
    background-color: #007bff;
    color: #fff;
    border: none;
    padding: 10px 20px;
    margin-top: 10px;
    border-radius: 5px;
    cursor: pointer;
}

button:hover {
    background-color: #0056b3;
}

a {
    display: inline-block;
    margin-top: 15px;
    color: #007bff;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}
```

To run the application, navigate to the directory containing `app.py` and execute:

```bash
python app.py
```

This will start a development server, and you can access the application by going to `http://127.0.0.1:5000/` in your web browser.

Please note that this is a very basic example and does not include input validation, error handling, or other best practices for production code. You should enhance the application with these features before deploying it.
