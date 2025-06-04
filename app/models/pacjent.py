from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token
from flask_login import UserMixin
from uuid import uuid4

class Pacjent(UserMixin, db.Model):
    __tablename__ = 'pacjent'
    
    id = db.Column(db.Integer, primary_key=True)
    imie = db.Column(db.String(50), nullable=False)
    nazwisko = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    haslo = db.Column(db.String(128), nullable=False)
    telefon = db.Column(db.String(20), nullable=False)
    data_urodzenia = db.Column(db.Date, nullable=True)
    adres = db.Column(db.String(200), nullable=True)
    kod_pocztowy = db.Column(db.String(10), nullable=True)
    miasto = db.Column(db.String(100), nullable=True)
    kraj = db.Column(db.String(100), nullable=True)
    pesel = db.Column(db.String(11), nullable=True)
    aktywny = db.Column(db.Boolean, default=True)
    email_zweryfikowany = db.Column(db.Boolean, default=False)
    kod_weryfikacyjny = db.Column(db.String(36), nullable=True)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    data_modyfikacji = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacje
    wizyty = db.relationship('Wizyta', back_populates='pacjent_rel', lazy='dynamic')
    diagramy = db.relationship('DiagramDentystyczny', backref='pacjent', lazy='dynamic')
    
    def __init__(self, imie, nazwisko, email, haslo, telefon, **kwargs):
        self.imie = imie
        self.nazwisko = nazwisko
        self.email = email
        self.set_password(haslo)
        self.telefon = telefon
        self.kod_weryfikacyjny = str(uuid4())
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def set_password(self, haslo):
        self.haslo = generate_password_hash(haslo)
    
    def check_password(self, haslo):
        return check_password_hash(self.haslo, haslo)
    
    def get_tokens(self):
        return {
            'access_token': create_access_token(identity={'id': self.id, 'role': 'pacjent'}),
            'refresh_token': create_refresh_token(identity={'id': self.id, 'role': 'pacjent'})
        }
    
    def get_full_name(self):
        return f"{self.imie} {self.nazwisko}"
    
    def is_active(self):
        return self.aktywny and self.email_zweryfikowany
        
    def get_id(self):
        return str(self.id)
    
    def to_dict(self):
        return {
            'id': self.id,
            'imie': self.imie,
            'nazwisko': self.nazwisko,
            'email': self.email,
            'telefon': self.telefon,
            'data_urodzenia': self.data_urodzenia.strftime('%Y-%m-%d') if self.data_urodzenia else None,
            'adres': self.adres,
            'kod_pocztowy': self.kod_pocztowy,
            'miasto': self.miasto,
            'kraj': self.kraj,
            'pesel': self.pesel,
            'aktywny': self.aktywny,
            'email_zweryfikowany': self.email_zweryfikowany,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S'),
            'data_modyfikacji': self.data_modyfikacji.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def __repr__(self):
        return f"<Pacjent {self.id}: {self.imie} {self.nazwisko}>"