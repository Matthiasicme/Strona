from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db
from .termin import Termin
from .usluga import Usluga


class Wizyta(db.Model):
    __tablename__ = 'wizyta'
    
    id = db.Column(db.Integer, primary_key=True)
    pacjent_id = db.Column(db.Integer, db.ForeignKey('pacjent.id'), nullable=False)
    lekarz_id = db.Column(db.Integer, db.ForeignKey('lekarz.id'), nullable=False)
    termin_id = db.Column(db.Integer, db.ForeignKey('termin.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='ZAPLANOWANA')
    platnosc_id = db.Column(db.Integer, db.ForeignKey('platnosc.id'), nullable=True)
    opis = db.Column(db.Text, nullable=True)
    notatka_wewnetrzna = db.Column(db.Text, nullable=True)
    kod_potwierdzenia = db.Column(db.String(10), nullable=True)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    data_modyfikacji = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacje do innych modeli
    # Usunięto jawną relację do Platnosc, ponieważ jest już zdefiniowana przez backref w modelu Platnosc
    podsumowanie = db.relationship('Podsumowanie', backref='wizyta', uselist=False, cascade='all, delete-orphan')
    uslugi = db.relationship('WizytaUsluga', back_populates='wizyta', lazy='dynamic', cascade='all, delete-orphan')
    
    # Relacje
    pacjent_rel = db.relationship('Pacjent', back_populates='wizyty', foreign_keys=[pacjent_id])
    lekarz_rel = db.relationship('Lekarz', back_populates='wizyty', foreign_keys=[lekarz_id])
    termin = db.relationship('Termin', back_populates='wizyta')
    
    # Właściwości dla zachowania wstecznej zgodności
    @property
    def pacjent(self):
        return self.pacjent_rel
        
    @pacjent.setter
    def pacjent(self, value):
        self.pacjent_rel = value
    
    @property
    def lekarz(self):
        return self.lekarz_rel
        
    @lekarz.setter
    def lekarz(self, value):
        self.lekarz_rel = value
    
    # Właściwości pomocnicze
    @property
    def data_wizyty(self):
        """Zwraca datę wizyty z terminu."""
        return self.termin.data if self.termin else None
    
    @property
    def godzina_rozpoczecia(self):
        """Zwraca godzinę rozpoczęcia wizyty."""
        return self.termin.godzina_od if self.termin else None
    
    @property
    def godzina_zakonczenia(self):
        """Zwraca godzinę zakończenia wizyty."""
        return self.termin.godzina_do if self.termin else None
    
    def __init__(self, pacjent_id, lekarz_id, termin_id, **kwargs):
        self.pacjent_id = pacjent_id
        self.lekarz_id = lekarz_id
        self.termin_id = termin_id
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self, include_relations=False):
        """Konwertuje obiekt wizyty do słownika."""
        result = {
            'id': self.id,
            'pacjent_id': self.pacjent_id,
            'lekarz_id': self.lekarz_id,
            'termin_id': self.termin_id,
            'status': self.status,
            'platnosc_id': self.platnosc_id,
            'opis': self.opis,
            'data_utworzenia': self.data_utworzenia.isoformat() if self.data_utworzenia else None,
            'data_modyfikacji': self.data_modyfikacji.isoformat() if self.data_modyfikacji else None,
            'data_wizyty': self.data_wizyty.isoformat() if self.data_wizyty else None,
            'godzina_rozpoczecia': self.godzina_rozpoczecia.isoformat() if self.godzina_rozpoczecia else None,
            'godzina_zakonczenia': self.godzina_zakonczenia.isoformat() if self.godzina_zakonczenia else None
        }
        
        if include_relations:
            # Dodajemy informacje o terminie
            result['termin'] = self.termin.to_dict() if self.termin else None
            
            # Dodajemy informacje o lekarzu
            if self.lekarz:
                result['lekarz'] = {
                    'id': self.lekarz.id,
                    'imie': self.lekarz.imie,
                    'nazwisko': self.lekarz.nazwisko,
                    'specjalizacja': self.lekarz.specjalizacja
                }
            
            # Dodajemy informacje o pacjencie
            if self.pacjent:
                result['pacjent'] = {
                    'id': self.pacjent.id,
                    'imie': self.pacjent.imie,
                    'nazwisko': self.pacjent.nazwisko
                }
            
            # Dodajemy informacje o płatności
            if self.platnosc:
                result['platnosc'] = {
                    'id': self.platnosc.id,
                    'kwota': float(self.platnosc.kwota),
                    'status': self.platnosc.status
                }
            
            # Dodajemy informacje o usługach
            result['uslugi'] = [
                {
                    'id': wu.usluga.id,
                    'nazwa': wu.usluga.nazwa,
                    'cena': float(wu.usluga.cena),
                    'ilosc': wu.ilosc
                } for wu in self.uslugi
            ]
        
        return result
    
    def __repr__(self):
        return f'<Wizyta {self.id} - {self.status}>'
    
    @classmethod
    def get_nadchodzace(cls, pacjent_id=None, lekarz_id=None, limit=10):
        """Pobiera nadchodzące wizyty."""
        from datetime import datetime, date
        
        query = cls.query.join(Termin).filter(
            Termin.data >= date.today(),
            cls.status.in_(['ZAPLANOWANA', 'POTWIERDZONA'])
        ).order_by(Termin.data.asc(), Termin.godzina_od.asc())
        
        if pacjent_id:
            query = query.filter_by(pacjent_id=pacjent_id)
        if lekarz_id:
            query = query.filter_by(lekarz_id=lekarz_id)
            
        return query.limit(limit).all()
    
    def czy_mozna_anulowac(self):
        """Sprawdza czy wizytę można anulować."""
        from datetime import datetime, timedelta
        
        if self.status not in ['ZAPLANOWANA', 'POTWIERDZONA']:
            return False
            
        # Sprawdź czy do wizyty zostało więcej niż 24 godziny
        czas_do_wizyty = datetime.combine(self.termin.data, self.termin.godzina_od) - datetime.now()
        return czas_do_wizyty > timedelta(hours=24)


class WizytaUsluga(db.Model):
    __tablename__ = 'wizyta_usluga'
    
    wizyta_id = db.Column(db.Integer, db.ForeignKey('wizyta.id'), primary_key=True)
    usluga_id = db.Column(db.Integer, db.ForeignKey('usluga.id'), primary_key=True)
    ilosc = db.Column(db.Integer, nullable=False, default=1)
    
    # Relacje
    wizyta = db.relationship('Wizyta', back_populates='uslugi', foreign_keys=[wizyta_id])
    usluga = db.relationship('Usluga', foreign_keys=[usluga_id])
    
    def __init__(self, wizyta_id=None, usluga_id=None, ilosc=1, wizyta=None, usluga=None):
        if wizyta_id is not None:
            self.wizyta_id = wizyta_id
        if usluga_id is not None:
            self.usluga_id = usluga_id
        if wizyta is not None:
            self.wizyta = wizyta
        if usluga is not None:
            self.usluga = usluga
        self.ilosc = ilosc