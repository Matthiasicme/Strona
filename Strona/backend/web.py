import flask
from models import db, Patient
from datetime import datetime, time
from flask import flash, redirect, url_for


app = flask.Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///patients.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'twoj_tajny_klucz'

db.init_app(app)

# Utwórz bazę danych jeśli jeszcze nie istnieje
with app.app_context():
    db.create_all()



@app.route('/')
def home():
    return flask.render_template('index.html')

@app.route('/appointments')
def appointments():
    patients = Patient.query.all()
    events = []
    for patient in patients:
        event = {
            'title': f"Wizyta: {patient.first_name} {patient.last_name}",
            'start': f"{patient.visit_date}T{patient.visit_time}"
        }
        events.append(event)
    return flask.jsonify(events)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if flask.request.method == 'POST':
        try:
            # Pobranie daty i czasu z formularza
            visit_date_str = flask.request.form['visit_date']
            visit_time_str = flask.request.form['visit_time']

            # Parsowanie daty i czasu
            visit_date = datetime.strptime(visit_date_str, "%Y-%m-%d").date()
            visit_time = datetime.strptime(visit_time_str, "%H:%M").time()

            # Sprawdzenie czy data nie jest weekendem (5=sobota, 6=niedziela)
            if visit_date.weekday() >= 5:
                flash("Przepraszamy, nie prowadzimy zapisów na weekendy (soboty i niedziele).", "error")
                return flask.redirect('/register')

            # Sprawdzenie czy czas to pełna lub półpełna godzina
            if visit_time.minute not in [0, 30]:
                flash("Możesz zapisać się tylko na pełną godzinę lub pół godziny (np. 14:00 lub 14:30).", "error")
                return flask.redirect('/register')

            # Sprawdzenie zakresu godzin (8:00-20:00)
            if visit_time.hour < 8 or visit_time.hour > 20 or (visit_time.hour == 20 and visit_time.minute > 0):
                flash("Godziny zapisów są dostępne tylko między 8:00 a 20:00.", "error")
                return flask.redirect('/register')

            # Jeśli wszystkie walidacje przeszły, zapisz pacjenta
            new_patient = Patient(
                first_name=flask.request.form['first_name'],
                last_name=flask.request.form['last_name'],
                pesel=flask.request.form['pesel'],
                phone=flask.request.form['phone'],
                email=flask.request.form['email'],
                visit_date=visit_date,
                visit_time=visit_time
            )
            db.session.add(new_patient)
            db.session.commit()
            flash("Wizyta została pomyślnie zarejestrowana!", "success")
            return flask.redirect('/success')

        except ValueError as e:
            flash(f"Nieprawidłowy format daty lub czasu: {str(e)}", "error")
            return flask.redirect('/register')

    return flask.render_template('register.html')

@app.route('/success')
def success():
    return flask.render_template('success.html')

if __name__ == '__main__':
    app.run(debug=True)
