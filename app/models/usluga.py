from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db

class Usluga(db.Model):
    """Model reprezentujący usługę stomatologiczną w systemie."""
    __tablename__ = 'usluga'
    __table_args__ = {'extend_existing': True}

    
    id = Column(Integer, primary_key=True)
    nazwa = Column(String(100), nullable=False)
    opis = Column(Text)
    cena = Column(Numeric(10, 2), nullable=False)
    czas_trwania = Column(Integer, nullable=False)  # w minutach
    aktywna = Column(Boolean, default=True)
    kategoria = Column(String(50))
    data_utworzenia = Column(DateTime, default=datetime.utcnow)
    data_modyfikacji = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacje
    wizyta_uslugi = db.relationship(
        'WizytaUsluga',
        back_populates='usluga',
        cascade='all, delete-orphan'
    )
    def __init__(self, nazwa, cena, czas_trwania, opis=None, kategoria=None, aktywna=True):
        self.nazwa = nazwa
        self.opis = opis
        self.cena = cena
        self.czas_trwania = czas_trwania
        self.kategoria = kategoria
        self.aktywna = aktywna
    
    def __repr__(self):
        return f'<Usluga {self.nazwa} ({self.cena} PLN, {self.czas_trwania} min)>'
    
    def to_dict(self):
        """Konwertuje obiekt usługi do słownika."""
        return {
            'id': self.id,
            'nazwa': self.nazwa,
            'opis': self.opis,
            'cena': float(self.cena) if self.cena else None,
            'czas_trwania': self.czas_trwania,
            'kategoria': self.kategoria,
            'aktywna': self.aktywna,
            'data_utworzenia': self.data_utworzenia.isoformat() if self.data_utworzenia else None,
            'data_modyfikacji': self.data_modyfikacji.isoformat() if self.data_modyfikacji else None
        }
    