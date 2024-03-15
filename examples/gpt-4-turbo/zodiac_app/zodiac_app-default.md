# GPT-4-turbo default system prompt (2024/03/11)

**user:**

I need a web application that asks for any date of birth and renders a page showing the user's Chinese zodiac sign. Do
not worry about aesthetics, just use text and textual buttons.

I want the app to be as easily deployable as possible.

**assistant:**

Creating a simple web application that asks for the user's date of birth and returns their Chinese zodiac sign can be achieved using a variety of programming languages and frameworks. For ease of deployment, I'll outline a basic application using Flask, a lightweight Python web framework, which can be easily deployed on platforms like Heroku.

Here's a simple step-by-step guide to create the application:

### Step 1: Set Up the Environment

Make sure you have Python and pip installed. Then install Flask:

```bash
pip install Flask
```

### Step 2: Create the Flask Application

Create a file named `app.py` with the following content:

```python
from flask import Flask, request, render_template_string

app = Flask(__name__)

# HTML template for the input form and the result
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Chinese Zodiac Sign</title>
</head>
<body>
  <h1>Enter your date of birth</h1>
  <form method="post">
    <input type="date" name="dob" required>
    <input type="submit" value="Submit">
  </form>
  {% if zodiac_sign %}
  <h2>Your Chinese Zodiac Sign is: {{ zodiac_sign }}</h2>
  {% endif %}
</body>
</html>
"""

def get_zodiac_sign(year):
    zodiac_animals = ["Monkey", "Rooster", "Dog", "Pig", "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat"]
    return zodiac_animals[year % 12]

@app.route('/', methods=['GET', 'POST'])
def index():
    zodiac_sign = None
    if request.method == 'POST':
        dob = request.form['dob']
        year = int(dob.split('-')[0])
        zodiac_sign = get_zodiac_sign(year)
    return render_template_string(HTML_TEMPLATE, zodiac_sign=zodiac_sign)

if __name__ == '__main__':
    app.run(debug=True)
```

### Step 3: Run the Application

Execute the following command to run the application:

```bash
python app.py
```

After running the command, you can access the web application by navigating to `http://127.0.0.1:5000
