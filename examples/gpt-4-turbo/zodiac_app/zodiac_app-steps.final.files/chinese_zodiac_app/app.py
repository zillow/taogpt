from flask import Flask, render_template, request, redirect, url_for
import lunar_cal
from datetime import datetime

app = Flask(__name__)

zodiac_animals = [
    "Monkey", "Rooster", "Dog", "Pig", "Rat", "Ox",
    "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat"
]

def get_zodiac_sign(year, month, day):
    lunar_new_year_month, lunar_new_year_day = lunar_cal.new_year_day(year)
    if (month < lunar_new_year_month) or (month == lunar_new_year_month and day < lunar_new_year_day):
        year -= 1
    return zodiac_animals[year % 12]

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        date_str = request.form['date']
        try:
            valid_date = datetime.strptime(date_str, '%Y-%m-%d')
            return redirect(url_for('result', date=date_str))
        except ValueError:
            return render_template('index.html', error="Invalid date. Please enter a valid date.")
    return render_template('index.html')

@app.route('/result')
def result():
    date_str = request.args.get('date', None)
    year, month, day = map(int, date_str.split('-'))
    zodiac_sign = get_zodiac_sign(year, month, day)
    return render_template('result.html', date=date_str, zodiac_sign=zodiac_sign)

if __name__ == '__main__':
    app.run(debug=True)