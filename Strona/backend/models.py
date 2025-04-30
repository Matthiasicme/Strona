from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    pesel = db.Column(db.String(11), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    visit_time = db.Column(db.Time, nullable=False)

