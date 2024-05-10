from flask import Flask, render_template, request
import lunar_cal
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    user_date = request.form['date']
    try:
        user_date_obj = datetime.strptime(user_date, '%Y-%m-%d')
        user_year = user_date_obj.year
        user_month = user_date_obj.month
        user_day = user_date_obj.day

        # Get the lunar new year's month and day for the given year
        lunar_new_year_month, lunar_new_year_day = lunar_cal.new_year_day(user_year)

        # Determine the lunar year
        if user_month < lunar_new_year_month or (user_month == lunar_new_year_month and user_day < lunar_new_year_day):
            lunar_year = user_year - 1
        else:
            lunar_year = user_year

        # Calculate the Chinese zodiac sign based on the lunar year
        zodiac_index = (lunar_year - 4) % 12
        zodiac_signs = [
            "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
            "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"
        ]
        zodiac_sign = zodiac_signs[zodiac_index]

        return render_template('result.html', zodiac_sign=zodiac_sign)
    except ValueError:
        return render_template('index.html', error="Please enter a valid date in the format YYYY-MM-DD.")
    except Exception as e:
        return render_template('index.html', error="An unexpected error occurred. Please try again.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)