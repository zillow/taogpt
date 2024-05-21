from flask import Flask, render_template, request, flash
import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Needed for flash messages

# Zodiac animals in the cycle order
zodiac_animals = [
    'Monkey', 'Rooster', 'Dog', 'Pig', 'Rat', 'Ox',
    'Tiger', 'Rabbit', 'Dragon', 'Snake', 'Horse', 'Goat'
]

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            # Extract and validate the date from the form
            date_input = request.form['date']
            date_obj = datetime.datetime.strptime(date_input, '%Y-%m-%d')
            year = date_obj.year
            
            # Safely attempt to import and use lunar_cal
            try:
                import lunar_cal
                lunar_new_year_month, lunar_new_year_day = lunar_cal.new_year_day(year)
                lunar_new_year_date = datetime.datetime(year, lunar_new_year_month, lunar_new_year_day)
            except ImportError:
                flash("lunar_cal module is not available.")
                return render_template('home.html')
            except Exception as e:
                flash(f"An error occurred with lunar_cal: {str(e)}")
                return render_template('home.html')
            
            # Determine the lunar year
            if date_obj < lunar_new_year_date:
                lunar_year = year - 1
            else:
                lunar_year = year
            
            # Calculate the zodiac sign
            zodiac_index = lunar_year % 12
            zodiac_sign = zodiac_animals[zodiac_index]
            
            return render_template('home.html', zodiac_sign=zodiac_sign)
        except ValueError as e:
            flash(f"Error: {str(e)} - Please enter a valid date.")
            return render_template('home.html')
        except Exception as e:
            flash(f"An unexpected error occurred: {str(e)}")
            return render_template('home.html')
    else:
        return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)