from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db

class Email(db.Model):
    __tablename__ = 'email'
    
    id = db.Column(db.Integer, primary_key=True)
    wizyta_id = db.Column(db.Integer, db.ForeignKey('wizyta.id'), nullable=False)
    temat = db.Column(db.String(255), nullable=False)
    tresc = db.Column(db.Text, nullable=False)
    data_wyslania = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='OCZEKUJĄCY')
    
    def __init__(self, wizyta_id, temat, tresc, **kwargs):
        self.wizyta_id = wizyta_id
        self.temat = temat
        self.tresc = tresc
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'wizyta_id': self.wizyta_id,
            'temat': self.temat,
            'tresc': self.tresc,
            'data_wyslania': self.data_wyslania.strftime('%Y-%m-%d %H:%M:%S') if self.data_wyslania else None,
            'status': self.status
        }
    
    def __repr__(self):
        return f"<Email {self.id}: Wizyta {self.wizyta_id}, Status {self.status}>"


class SMS(db.Model):
    __tablename__ = 'sms'
    
    id = db.Column(db.Integer, primary_key=True)
    wizyta_id = db.Column(db.Integer, db.ForeignKey('wizyta.id'), nullable=False)
    tresc = db.Column(db.String(160), nullable=False)
    data_wyslania = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='OCZEKUJĄCY')
    
    def __init__(self, wizyta_id, tresc, **kwargs):
        self.wizyta_id = wizyta_id
        self.tresc = tresc
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'wizyta_id': self.wizyta_id,
            'tresc': self.tresc,
            'data_wyslania': self.data_wyslania.strftime('%Y-%m-%d %H:%M:%S') if self.data_wyslania else None,
            'status': self.status
        }
    
    def __repr__(self):
        return f"<SMS {self.id}: Wizyta {self.wizyta_id}, Status {self.status}>"


class PowiadomienieKonfiguracja(db.Model):
    __tablename__ = 'powiadomienie_konfiguracja'
    
    id = db.Column(db.Integer, primary_key=True)
    typ = db.Column(db.String(50), nullable=False)  # "PRZYPOMNIENIE", "POTWIERDZENIE", "ANULOWANIE", "PLATNOSC"
    czas_przed_wizyta = db.Column(db.Integer, nullable=True)  # Czas w godzinach przed wizytą
    szablon_email = db.Column(db.Text, nullable=True)
    szablon_sms = db.Column(db.String(160), nullable=True)
    aktywny = db.Column(db.Boolean, default=True)
    
    def __init__(self, typ, **kwargs):
        self.typ = typ
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'typ': self.typ,
            'czas_przed_wizyta': self.czas_przed_wizyta,
            'szablon_email': self.szablon_email,
            'szablon_sms': self.szablon_sms,
            'aktywny': self.aktywny
        }
    
    def __repr__(self):
        return f"<PowiadomienieKonfiguracja {self.id}: Typ {self.typ}>"