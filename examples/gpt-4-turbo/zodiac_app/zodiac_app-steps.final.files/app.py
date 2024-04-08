from flask import Flask, request, render_template
from datetime import datetime

app = Flask(__name__)

# Chinese Zodiac signs in a cycle
zodiac_signs = [
    "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"
]

def get_zodiac_sign(year):
    # The zodiac sign is based on the remainder of the year divided by 12
    return zodiac_signs[(year - 4) % 12]

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/get-zodiac', methods=['POST'])
def get_zodiac():
    # Extract the date from the form
    date_str = request.form['date']
    # Convert the date string to a datetime object
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD.", 400

    # Check if the date is before or after February 4th
    new_year_date = datetime(date.year, 2, 4)
    if date < new_year_date:
        # If the date is before February 4th, use the previous year to determine the zodiac
        zodiac_year = date.year - 1
    else:
        zodiac_year = date.year

    # Get the zodiac sign for the calculated year
    zodiac_sign = get_zodiac_sign(zodiac_year)
    return render_template('result.html', zodiac_sign=zodiac_sign)

if __name__ == '__main__':
    app.run(debug=True)