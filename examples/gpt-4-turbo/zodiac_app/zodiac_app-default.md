# GPT-4-turbo default system prompt (2024/04/20)

**remarks**: 
1. the UI takes only the year as input and not a full date.
2. the app invokes the given helper `lunar_cal.new_year_day(date)` but fails to take use of the return values to 
   determine the final zodiac sign.
3. it creates the dummy implementation `lunar_cal.py`; arguably, this is not needed since it is given as existing 
   helper in the task statement.

**user:**

I need a web application that takes a Gregorian date as input and renders a page showing the user's Chinese
zodiac sign. We don't have any image assets, just use text buttons, but the app should be pleasant to use.

The following package and method is provided to help you:

```python
import lunar_cal
# get the month and day of the lunar new year day in the given Gregorian year.
month, day = lunar_cal.new_year_day(date)
```

Give me a full deployable Python project with all server and client side asset files.

No need to test, install or deploy the app, I will do those.

**assistant:**

To create a web application that takes a Gregorian date as input and shows the user's Chinese zodiac sign, we can use Flask, a lightweight Python web framework. Below, I'll provide you with a simple project structure and the necessary code files.

### Project Structure

```
chinese_zodiac_app/
│
├── app/
│   ├── templates/
│   │   ├── index.html
│   │   └── result.html
│   ├── __init__.py
│   └── views.py
│
├── lunar_cal.py
└── run.py
```

### Step-by-Step Guide

1. **Setup Environment**:
    - Make sure you have Python installed.
    - Install Flask: `pip install Flask`

2. **Create Files**:

    - **lunar_cal.py**: This is a placeholder for the lunar calendar package you mentioned.
      ```python
      def new_year_day(year):
          # Placeholder function, replace with actual implementation
          # Example: returns month and day of the lunar new year in the given Gregorian year
          return (2, 12)  # Example: February 12
      ```

    - **run.py**: This is the entry point of your Flask application.
      ```python
      from app import app
 
      if __name__ == "__main__":
          app.run(debug=True)
      ```

    - **app/__init__.py**: Initialize your Flask app here.
      ```python
      from flask import Flask
 
      app = Flask(__name__)
 
      from app import views
      ```

    - **app/views.py**: Define your routes and logic here.
      ```python
      from flask import render_template, request, redirect, url_for
      from app import app
      import lunar_cal
 
      zodiac_animals = [
          "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat",
          "Monkey", "Rooster", "Dog", "Pig"
      ]
 
      def get_zodiac(year):
          start_year = 1900  # Rat year
          return zodiac_animals[(year - start_year) % 12]
 
      @app.route('/', methods=['GET', 'POST'])
      def index():
          if request.method == 'POST':
              year = int(request.form['year'])
              return redirect(url_for('result', year=year))
          return render_template('index.html')
 
      @app.route('/result/<int:year>')
      def result(year):
          month, day = lunar_cal.new_year_day(year)
          zodiac = get_zodiac(year)
          return render_template('result.html', year=year, zodiac=zodiac, month=month, day=day)
      ```

    - **app/templates/index.html**: HTML form to input the year.
      ```html
      <!DOCTYPE html>
      <html>
      <head>
          <title>Chinese Zodiac Sign Finder</title>
      </head>
      <body>
          <h1>Enter a Year to Find Your Chinese Zodiac Sign</h1>
          <form action="/" method="post">
              <input type="number" name="year" required>
              <button type="submit">Submit</button>
          </form>
      </body>
      </html>
      ```

    - **app/templates/result.html**: Display the result.
      ```html
      <!DOCTYPE html>
      <html>
      <head>
          <title>Your Chinese Zodiac Sign</title>
      </head>
      <body>
          <h1>Your Chinese Zodiac Sign for {{ year }}</h1>
          <p>Your zodiac sign is: <strong>{{ zodiac }}</strong></p>
          <p>Lunar New Year's Day: {{ month }}/{{ day }}</p>
          <a href="/">Try another year</a>
      </body>
      </html>
      ```

3. **Run the Application**:
    - Navigate to the project directory and run `python run.py`.
    - Open a web browser and go to `http://127.0.0.1:5000/` to use the application.

This setup provides a basic Flask application that can calculate and display the Chinese zodiac sign based on the year input by the user. Adjust the `lunar_cal.py` with the actual implementation as needed.
