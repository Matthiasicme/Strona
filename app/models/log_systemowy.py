from datetime import datetime
from app import db

class LogSystemowy(db.Model):
    __tablename__ = 'log_systemowy'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    typ = db.Column(db.String(20), nullable=False)  # INFO, WARNING, ERROR, etc.
    akcja = db.Column(db.String(100), nullable=False)  # Action name (e.g., 'LOGIN', 'REGISTRATION')
    opis = db.Column(db.Text, nullable=True)  # Detailed description
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    uzytkownik_id = db.Column(db.Integer, nullable=True)  # ID of the user who performed the action
    rola_uzytkownika = db.Column(db.String(50), nullable=True)  # Role: 'pacjent', 'lekarz', 'admin'
    ip_adres = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6 address
    
    def __init__(self, typ, akcja, opis=None, uzytkownik_id=None, rola_uzytkownika=None, ip_adres=None):
        self.typ = typ
        self.akcja = akcja
        self.opis = opis
        self.uzytkownik_id = uzytkownik_id
        self.rola_uzytkownika = rola_uzytkownika
        self.ip_adres = ip_adres
    
    def to_dict(self):
        return {
            'id': self.id,
            'typ': self.typ,
            'akcja': self.akcja,
            'opis': self.opis,
            'data_utworzenia': self.data_utworzenia.isoformat(),
            'uzytkownik_id': self.uzytkownik_id,
            'rola_uzytkownika': self.rola_uzytkownika,
            'ip_adres': self.ip_adres
        }
    
    def __repr__(self):
        return f'<LogSystemowy {self.id}: {self.akcja} - {self.opis}>'
