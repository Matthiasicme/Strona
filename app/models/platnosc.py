from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db

class MetodaPlatnosci(db.Model):
    __tablename__ = 'metoda_platnosci'
    
    id = db.Column(db.Integer, primary_key=True)
    nazwa = db.Column(db.String(50), nullable=False)
    aktywna = db.Column(db.Boolean, default=True)
    
    # Relacje
    platnosci = db.relationship('Platnosc', backref='metoda_platnosci', lazy='dynamic')
    
    def __init__(self, nazwa, aktywna=True):
        self.nazwa = nazwa
        self.aktywna = aktywna
    
    def to_dict(self):
        return {
            'id': self.id,
            'nazwa': self.nazwa,
            'aktywna': self.aktywna
        }
    
    def __repr__(self):
        return f"<MetodaPlatnosci {self.id}: {self.nazwa}>"


class Platnosc(db.Model):
    __tablename__ = 'platnosc'
    
    id = db.Column(db.Integer, primary_key=True)
    kwota = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='OCZEKUJĄCA')
    metoda_platnosci_id = db.Column(db.Integer, db.ForeignKey('metoda_platnosci.id'), nullable=True)
    identyfikator_transakcji = db.Column(db.String(100), nullable=True)  # ID transakcji z serwisu płatności
    url_platnosci = db.Column(db.String(255), nullable=True)  # URL do serwisu płatności
    data_platnosci = db.Column(db.DateTime, nullable=True)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacje
    wizyta = db.relationship('Wizyta', backref='platnosc', uselist=False)
    
    def __init__(self, kwota, **kwargs):
        self.kwota = kwota
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self, include_relations=False):
        result = {
            'id': self.id,
            'kwota': float(self.kwota),
            'status': self.status,
            'metoda_platnosci_id': self.metoda_platnosci_id,
            'identyfikator_transakcji': self.identyfikator_transakcji,
            'url_platnosci': self.url_platnosci,
            'data_platnosci': self.data_platnosci.strftime('%Y-%m-%d %H:%M:%S') if self.data_platnosci else None,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if include_relations and self.metoda_platnosci:
            result['metoda_platnosci'] = self.metoda_platnosci.to_dict()
            
        if include_relations and self.wizyta:
            result['wizyta'] = {
                'id': self.wizyta.id,
                'pacjent_id': self.wizyta.pacjent_id,
                'lekarz_id': self.wizyta.lekarz_id,
                'termin_id': self.wizyta.termin_id,
                'status': self.wizyta.status
            }
        
        return result
    
    def __repr__(self):
        return f"<Platnosc {self.id}: {self.kwota} PLN, Status: {self.status}>"