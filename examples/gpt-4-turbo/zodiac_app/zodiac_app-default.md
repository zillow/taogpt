# GPT-4-turbo default system prompt (2024/05/09)

**remarks**: 

The codes forget to call `lunar_cal.new_year_day()` to get the proper Chinese new year cut-off day in a given year.

**user:**

I need a deployable web application Python package that takes a Gregorian date as input and renders a page showing the
user's Chinese zodiac sign. We don't have any image assets, just use text buttons, but the app should be pleasant to
use.

The following package and method is provided to help you:

```python
import lunar_cal
# get the month and day of the lunar new year day in the given Gregorian year.
month, day = lunar_cal.new_year_day(date)
```

I just need all server and client side asset files.
No need to describe setup, installation, or test; I will do those myself.

**assistant:**
To create a deployable web application that takes a Gregorian date as input and renders a page showing the user's Chinese zodiac sign, we can use Flask, a lightweight Python web framework. Below, I'll provide the necessary Python script, HTML templates, and a basic CSS file to style the application. This setup assumes you have Flask installed and `lunar_cal` module available as described.

### 1. Python Script (app.py)

This script sets up the Flask application, handles form processing, and calculates the Chinese zodiac sign.

```python
from flask import Flask, render_template, request
import lunar_cal

app = Flask(__name__)

# Chinese Zodiac cycle as a list
zodiac_animals = [
    "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", 
    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"
]

def get_zodiac(year):
    # The zodiac cycle starts with Rat, which corresponds to 1900
    return zodiac_animals[(year - 1900) % 12]

@app.route('/', methods=['GET', 'POST'])
def index():
    zodiac_sign = None
    if request.method == 'POST':
        date = request.form.get('date')
        if date:
            year = int(date.split('-')[0])
            zodiac_sign = get_zodiac(year)
    return render_template('index.html', zodiac_sign=zodiac_sign)

if __name__ == '__main__':
    app.run(debug=True)
```

### 2. HTML Template (templates/index.html)

This HTML file is used by Flask to render the web page.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Chinese Zodiac Sign Finder</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <h1>Find Your Chinese Zodiac Sign</h1>
        <form method="post">
            <label for="date">Enter your birthdate (YYYY-MM-DD):</label>
            <input type="date" id="date" name="date" required>
            <button type="submit">Submit</button>
        </form>
        {% if zodiac_sign %}
            <h2>Your Chinese Zodiac Sign is: {{ zodiac_sign }}</h2>
        {% endif %}
    </div>
</body>
</html>
```

### 3. CSS File (static/style.css)

This CSS file provides basic styling for the application.

```css
body {
    font-family: Arial, sans-serif;
    background-color: #f4f4f9;
    margin: 0;
    padding: 20px;
}

.container {
    width: 80%;
    margin: auto;
    background-color: #fff;
    padding: 20px;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
    text-align: center;
}

input[type="date"], button {
    padding: 10px;
    margin-top: 10px;
}

button {
    cursor: pointer;
    background-color: #007BFF;
    color: white;
    border: none;
    border-radius: 5px;
}

button:hover {
    background-color: #0056b3;
}
```

### File Structure

Ensure your file structure looks like this:

```
/your-app-folder
    /static
        - style.css
    /templates
        - index.html
    - app.py
```

This setup provides a simple, functional web application for determining a user's Chinese zodiac sign based on their birth year. The application uses Flask to handle routing and form processing, and basic HTML/CSS for the frontend.
