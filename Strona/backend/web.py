import flask
from models import db, Patient
from datetime import datetime, time


app = flask.Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/matth/Desktop/Strona/database/patients.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
        new_patient = Patient(
            first_name=flask.request.form['first_name'],
            last_name=flask.request.form['last_name'],
            pesel=flask.request.form['pesel'],
            phone=flask.request.form['phone'],
            email=flask.request.form['email'],
            visit_date = datetime.strptime(flask.request.form['visit_date'], "%Y-%m-%d").date(),
            visit_time = datetime.strptime(flask.request.form['visit_time'], "%H:%M").time()
        )
        db.session.add(new_patient)
        db.session.commit()
        return flask.redirect('/success')
    return flask.render_template('register.html')

@app.route('/success')
def success():
    return flask.render_template('success.html')

if __name__ == '__main__':
    app.run(debug=True)
