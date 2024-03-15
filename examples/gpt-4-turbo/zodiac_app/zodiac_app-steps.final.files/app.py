from flask import Flask, render_template, request

app = Flask(__name__)

# Chinese Zodiac calculation logic
def calculate_zodiac(year):
    zodiac_animals = [
        "Monkey", "Rooster", "Dog", "Pig", "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat"
    ]
    return zodiac_animals[(year - 4) % 12]

@app.route('/', methods=['GET', 'POST'])
def index():
    zodiac_sign = None
    if request.method == 'POST':
        dob = request.form['dob']
        year = int(dob.split('-')[0])  # Extract the year from the date
        zodiac_sign = calculate_zodiac(year)
    return render_template('index.html', zodiac_sign=zodiac_sign)

if __name__ == '__main__':
    app.run(debug=True)