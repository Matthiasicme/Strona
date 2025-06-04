from datetime import time, datetime
from app import db

class Termin(db.Model):
    """Model reprezentujący dostępne terminy wizyty."""
    __tablename__ = 'termin'
    __table_args__ = {'extend_existing': True}

    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    godzina_od = db.Column(db.Time, nullable=False)
    godzina_do = db.Column(db.Time, nullable=False)
    dostepny = db.Column(db.Boolean, default=True)
    lekarz_id = db.Column(db.Integer, db.ForeignKey('lekarz.id'), nullable=False)
    
    # Relacje
    lekarz = db.relationship('Lekarz', back_populates='terminy')
    wizyta = db.relationship('Wizyta', back_populates='termin', uselist=False)
    
    def __init__(self, data, godzina_od, godzina_do, lekarz_id, dostepny=True):
        self.data = data
        self.godzina_od = godzina_od
        self.godzina_do = godzina_do
        self.lekarz_id = lekarz_id
        self.dostepny = dostepny
    
    def __repr__(self):
        return f'<Termin {self.data} {self.godzina_od}-{self.godzina_do} (Lekarz: {self.lekarz_id})>'
    
    def to_dict(self):
        """Konwertuje obiekt terminu do słownika."""
        return {
            'id': self.id,
            'data': self.data.isoformat(),
            'godzina_od': self.godzina_od.isoformat(),
            'godzina_do': self.godzina_do.isoformat(),
            'dostepny': self.dostepny,
            'lekarz_id': self.lekarz_id,
            'data_utworzenia': None
        }
    
    @classmethod
    def get_dostepne_terminy(cls, data_od, data_do, lekarz_id=None):
        """Pobiera dostępne terminy w podanym zakresie dat."""
        query = cls.query.filter(
            cls.data.between(data_od, data_do),
            cls.dostepny == True
        )
        
        if lekarz_id:
            query = query.filter_by(lekarz_id=lekarz_id)
            
        return query.all()
    
    def czy_dostepny(self):
        """Sprawdza czy termin jest dostępny do rezerwacji."""
        if not self.dostepny:
            return False
            
        # Sprawdź czy nie ma już zarejestrowanej wizyty na ten termin
        from models.wizyta import Wizyta
        wizyta = Wizyta.query.filter_by(
            termin_id=self.id,
            status=['ZAPLANOWANA', 'POTWIERDZONA']
        ).first()
        
        return wizyta is None
