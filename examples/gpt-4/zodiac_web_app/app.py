from flask import Flask, render_template, request
from datetime import datetime

app = Flask(__name__)

ZODIAC_SIGNS = ['Rat', 'Ox', 'Tiger', 'Rabbit', 'Dragon', 'Snake', 'Horse', 'Goat', 'Monkey', 'Rooster', 'Dog', 'Pig']

def get_zodiac_sign(dob):
    year = dob.year
    index = (year - 1900) % 12
    return ZODIAC_SIGNS[index]

@app.route('/', methods=['GET', 'POST'])
def home():
    sign = None
    if request.method == 'POST':
        dob = request.form.get('dob')
        dob = datetime.strptime(dob, '%Y-%m-%d')
        sign = get_zodiac_sign(dob)
    return render_template('index.html', sign=sign)

if __name__ == "__main__":
    app.run()