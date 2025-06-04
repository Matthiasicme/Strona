from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token

class Lekarz(db.Model):
    __tablename__ = 'lekarz'
    
    id = db.Column(db.Integer, primary_key=True)
    imie = db.Column(db.String(50), nullable=False)
    nazwisko = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    haslo = db.Column(db.String(128), nullable=False)
    telefon = db.Column(db.String(20), nullable=False)
    specjalizacja = db.Column(db.String(100), nullable=False)
    opis = db.Column(db.Text, nullable=True)
    numer_pwz = db.Column(db.String(20), nullable=True)  # Numer Prawa Wykonywania Zawodu
    zdjecie_url = db.Column(db.String(255), nullable=True)
    aktywny = db.Column(db.Boolean, default=True)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    data_modyfikacji = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacje
    terminy = db.relationship('Termin', back_populates='lekarz', lazy='dynamic')
    wizyty = db.relationship('Wizyta', back_populates='lekarz_rel', lazy='dynamic')
    
    def __init__(self, imie, nazwisko, email, haslo, telefon, specjalizacja, **kwargs):
        self.imie = imie
        self.nazwisko = nazwisko
        self.email = email
        self.set_password(haslo)
        self.telefon = telefon
        self.specjalizacja = specjalizacja
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def set_password(self, haslo):
        self.haslo = generate_password_hash(haslo)
    
    def check_password(self, haslo):
        return check_password_hash(self.haslo, haslo)
    
    def get_tokens(self):
        return {
            'access_token': create_access_token(identity={'id': self.id, 'role': 'lekarz'}),
            'refresh_token': create_refresh_token(identity={'id': self.id, 'role': 'lekarz'})
        }
    
    def get_full_name(self):
        return f"{self.imie} {self.nazwisko}"
    
    def is_active(self):
        return self.aktywny
    
    def to_dict(self):
        return {
            'id': self.id,
            'imie': self.imie,
            'nazwisko': self.nazwisko,
            'email': self.email,
            'telefon': self.telefon,
            'specjalizacja': self.specjalizacja,
            'opis': self.opis,
            'numer_pwz': self.numer_pwz,
            'zdjecie_url': self.zdjecie_url,
            'aktywny': self.aktywny,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S'),
            'data_modyfikacji': self.data_modyfikacji.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def __repr__(self):
        return f"<Lekarz {self.id}: {self.imie} {self.nazwisko}, {self.specjalizacja}>"