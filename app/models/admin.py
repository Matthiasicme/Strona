from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token

class Administrator(db.Model):
    __tablename__ = 'administrator'
    
    id = db.Column(db.Integer, primary_key=True)
    imie = db.Column(db.String(50), nullable=False)
    nazwisko = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    haslo = db.Column(db.String(128), nullable=False)
    rola = db.Column(db.String(50), nullable=False, default='ADMIN')  # ADMIN, SUPER_ADMIN
    aktywny = db.Column(db.Boolean, default=True)
    ostatnie_logowanie = db.Column(db.DateTime, nullable=True)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    data_modyfikacji = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, imie, nazwisko, email, haslo, rola='ADMIN', **kwargs):
        self.imie = imie
        self.nazwisko = nazwisko
        self.email = email
        self.set_password(haslo)
        self.rola = rola
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def set_password(self, haslo):
        self.haslo = generate_password_hash(haslo)
    
    def check_password(self, haslo):
        return check_password_hash(self.haslo, haslo)
    
    def get_tokens(self):
        return {
            'access_token': create_access_token(identity={'id': self.id, 'role': 'admin', 'admin_role': self.rola}),
            'refresh_token': create_refresh_token(identity={'id': self.id, 'role': 'admin', 'admin_role': self.rola})
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
            'rola': self.rola,
            'aktywny': self.aktywny,
            'ostatnie_logowanie': self.ostatnie_logowanie.strftime('%Y-%m-%d %H:%M:%S') if self.ostatnie_logowanie else None,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S'),
            'data_modyfikacji': self.data_modyfikacji.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def __repr__(self):
        return f"<Administrator {self.id}: {self.imie} {self.nazwisko}, Rola: {self.rola}>"


class LogSystemowy(db.Model):
    __tablename__ = 'log_systemowy'
    
    id = db.Column(db.Integer, primary_key=True)
    typ = db.Column(db.String(50), nullable=False)  # INFO, WARNING, ERROR, SECURITY
    akcja = db.Column(db.String(100), nullable=False)
    opis = db.Column(db.Text, nullable=False)
    uzytkownik_id = db.Column(db.Integer, nullable=True)  # ID użytkownika (pacjent, lekarz, admin)
    rola_uzytkownika = db.Column(db.String(50), nullable=True)  # pacjent, lekarz, admin
    ip_adres = db.Column(db.String(50), nullable=True)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, typ, akcja, opis, **kwargs):
        self.typ = typ
        self.akcja = akcja
        self.opis = opis
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'typ': self.typ,
            'akcja': self.akcja,
            'opis': self.opis,
            'uzytkownik_id': self.uzytkownik_id,
            'rola_uzytkownika': self.rola_uzytkownika,
            'ip_adres': self.ip_adres,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def __repr__(self):
        return f"<LogSystemowy {self.id}: {self.typ}, {self.akcja}, {self.data_utworzenia}>"


class Archiwizacja(db.Model):
    __tablename__ = 'archiwizacja'
    
    id = db.Column(db.Integer, primary_key=True)
    nazwa = db.Column(db.String(100), nullable=False)
    opis = db.Column(db.Text, nullable=True)
    typ = db.Column(db.String(50), nullable=False)  # PELNA, PRZYROSTOWA
    status = db.Column(db.String(50), nullable=False)  # OCZEKUJACA, W_TRAKCIE, ZAKONCZONA, BLAD
    lokalizacja = db.Column(db.String(255), nullable=True)
    rozmiar = db.Column(db.Integer, nullable=True)  # w bajtach
    administrator_id = db.Column(db.Integer, db.ForeignKey('administrator.id'), nullable=False)
    data_rozpoczecia = db.Column(db.DateTime, nullable=True)
    data_zakonczenia = db.Column(db.DateTime, nullable=True)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, nazwa, typ, administrator_id, **kwargs):
        self.nazwa = nazwa
        self.typ = typ
        self.administrator_id = administrator_id
        self.status = 'OCZEKUJACA'
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nazwa': self.nazwa,
            'opis': self.opis,
            'typ': self.typ,
            'status': self.status,
            'lokalizacja': self.lokalizacja,
            'rozmiar': self.rozmiar,
            'administrator_id': self.administrator_id,
            'data_rozpoczecia': self.data_rozpoczecia.strftime('%Y-%m-%d %H:%M:%S') if self.data_rozpoczecia else None,
            'data_zakonczenia': self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S') if self.data_zakonczenia else None,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def __repr__(self):
        return f"<Archiwizacja {self.id}: {self.nazwa}, Status: {self.status}>"