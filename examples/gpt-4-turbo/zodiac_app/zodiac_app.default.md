# GPT-4-turbo default system prompt (2024/05/12)

**remarks**: 

The solution is correct.

**user:**

I need a deployable web application that takes a Gregorian date as input and renders a page showing the user's Chinese zodiac sign.

We don't have any image assets, just use text buttons, but the app should be pleasant to use.

The following package and method is provided to help you:

```python
import lunar_cal
import datetime
# Given a Gregorian year, like 2023, get the Gregorian month and day for the lunar new year day in that year.
month, day = lunar_cal.new_year_day(gregorian_year: int)
```

**assistant:**

To create a deployable web application that calculates the Chinese zodiac sign based on a Gregorian date input, we can use Flask, a lightweight Python web framework. Below, I'll guide you through setting up the application, including the necessary Flask setup, handling the form for date input, and calculating the Chinese zodiac sign.

### Step 1: Setup Your Environment

First, ensure you have Python installed. Then, install Flask and any other necessary packages:

```bash
pip install Flask
```

### Step 2: Create the Flask Application

Create a new directory for your project and inside that directory, create a file named `app.py`. This file will contain your Flask application.

### Step 3: Implement the Application

Here's how you can implement the application in `app.py`:

```python
from flask import Flask, request, render_template
import lunar_cal
import datetime

app = Flask(__name__)

# Chinese Zodiac cycle
zodiac_animals = [
    "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", 
    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"
]

def get_zodiac(year):
    # The zodiac cycle starts with Rat in 1924
    return zodiac_animals[(year - 1924) % 12]

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get date from form
        date_str = request.form['date']
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        year = date_obj.year
        
        # Get the lunar new year's day for the given year
        month, day = lunar_cal.new_year_day(year)
        lunar_new_year = datetime.date(year, month, day)
        
        # Determine the zodiac year
        if date_obj.date() < lunar_new_year:
            # If the date is before lunar new year, it's the previous zodiac year
            zodiac = get_zodiac(year - 1)
        else:
            zodiac = get_zodiac(year)
        
        return render_template('result.html', zodiac=zodiac, date=date_str)
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
```

### Step 4: Create HTML Templates

Create a folder named `templates` in the same directory as your `app.py`. Inside this folder, create two HTML files: `index.html` and `result.html`.

**index.html:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Chinese Zodiac Calculator</title>
</head>
<body>
    <h1>Enter a Date to Find Your Chinese Zodiac Sign</h1>
    <form action="/" method="post">
        <input type="date" name="date" required>
        <button type="submit">Submit</button>
    </form>
</body>
</html>
```

**result.html:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Your Chinese Zodiac Sign</title>
</head>
<body>
    <h1>Your Chinese Zodiac Sign</h1>
    <p>For the date: {{ date }}</p>
    <p>Your Chinese Zodiac Sign is: <strong>{{ zodiac }}</strong></p>
    <a href="/">Try another date</a>
</body>
</html>
```

### Step 5: Run Your Application

Run your Flask application by executing:

```bash
python app.py
```

Visit `http://127.0.0.1:5000/` in your web browser to see your application in action.

This setup provides a basic, functional web application for determining the Chinese zodiac sign from a Gregorian date. You can expand and style it further according to your needs.
