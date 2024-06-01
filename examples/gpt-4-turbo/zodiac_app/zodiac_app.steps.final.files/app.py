from flask import Flask, request, render_template
import lunar_cal
import datetime

app = Flask(__name__)

def get_zodiac_sign(year):
    # Zodiac signs cycle
    zodiac_signs = [
        "Monkey", "Rooster", "Dog", "Pig", "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat"
    ]
    # Calculate zodiac sign based on the year
    return zodiac_signs[(year - 4) % 12]

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            # Extract date from form
            day = int(request.form['day'])
            month = int(request.form['month'])
            year = int(request.form['year'])
            
            # Calculate the lunar new year for the given year
            lunar_new_year_month, lunar_new_year_day = lunar_cal.new_year_day(year)
            
            # Create date objects for comparison
            input_date = datetime.date(year, month, day)
            lunar_new_year_date = datetime.date(year, lunar_new_year_month, lunar_new_year_day)
            
            # Determine the zodiac year
            if input_date < lunar_new_year_date:
                # If the date is before lunar new year, it belongs to the previous zodiac year
                zodiac_year = year - 1
            else:
                zodiac_year = year
            
            # Get the zodiac sign
            zodiac_sign = get_zodiac_sign(zodiac_year)
            
            return render_template('result.html', zodiac_sign=zodiac_sign, date=input_date)
        except ValueError:
            return render_template('result.html', error="Invalid date. Please enter a valid date.")
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)