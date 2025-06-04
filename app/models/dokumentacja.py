from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db

class Podsumowanie(db.Model):
    __tablename__ = 'podsumowanie'
    
    id = db.Column(db.Integer, primary_key=True)
    wizyta_id = db.Column(db.Integer, db.ForeignKey('wizyta.id'), nullable=False)
    szczegoly = db.Column(db.Text, nullable=False)
    zalecenia = db.Column(db.Text, nullable=True)
    nastepna_wizyta_zalecana = db.Column(db.Boolean, default=False)
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, wizyta_id, szczegoly, **kwargs):
        self.wizyta_id = wizyta_id
        self.szczegoly = szczegoly
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'wizyta_id': self.wizyta_id,
            'szczegoly': self.szczegoly,
            'zalecenia': self.zalecenia,
            'nastepna_wizyta_zalecana': self.nastepna_wizyta_zalecana,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def __repr__(self):
        return f"<Podsumowanie {self.id}: Wizyta {self.wizyta_id}>"


class DiagramDentystyczny(db.Model):
    __tablename__ = 'diagram_dentystyczny'
    
    id = db.Column(db.Integer, primary_key=True)
    pacjent_id = db.Column(db.Integer, db.ForeignKey('pacjent.id'), nullable=False)
    numer_zeba = db.Column(db.Integer, nullable=False)  # 11-48 zgodnie z międzynarodowym systemem numeracji
    status = db.Column(db.String(50), nullable=False)
    opis = db.Column(db.Text, nullable=True)
    data_modyfikacji = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('pacjent_id', 'numer_zeba', name='uq_pacjent_zab'),
    )
    
    def __init__(self, pacjent_id, numer_zeba, status, **kwargs):
        self.pacjent_id = pacjent_id
        self.numer_zeba = numer_zeba
        self.status = status
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'pacjent_id': self.pacjent_id,
            'numer_zeba': self.numer_zeba,
            'status': self.status,
            'opis': self.opis,
            'data_modyfikacji': self.data_modyfikacji.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def __repr__(self):
        return f"<DiagramDentystyczny {self.id}: Pacjent {self.pacjent_id}, Ząb {self.numer_zeba}, Status {self.status}>"


class Recepta(db.Model):
    __tablename__ = 'recepta'
    
    id = db.Column(db.Integer, primary_key=True)
    wizyta_id = db.Column(db.Integer, db.ForeignKey('wizyta.id'), nullable=False)
    kod_recepty = db.Column(db.String(20), nullable=True)  # Kod e-Recepty
    identyfikator_p1 = db.Column(db.String(100), nullable=True)  # Identyfikator w systemie P1
    opis = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='UTWORZONA')
    data_utworzenia = db.Column(db.DateTime, default=datetime.utcnow)
    data_modyfikacji = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacje
    leki = db.relationship('ReceptaLek', backref='recepta', lazy='dynamic')
    
    def __init__(self, wizyta_id, opis, **kwargs):
        self.wizyta_id = wizyta_id
        self.opis = opis
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self, include_relations=False):
        result = {
            'id': self.id,
            'wizyta_id': self.wizyta_id,
            'kod_recepty': self.kod_recepty,
            'identyfikator_p1': self.identyfikator_p1,
            'opis': self.opis,
            'status': self.status,
            'data_utworzenia': self.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S'),
            'data_modyfikacji': self.data_modyfikacji.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if include_relations:
            result['leki'] = [lek.to_dict() for lek in self.leki]
        
        return result
    
    def __repr__(self):
        return f"<Recepta {self.id}: Wizyta {self.wizyta_id}, Status {self.status}>"


class ReceptaLek(db.Model):
    __tablename__ = 'recepta_lek'
    
    id = db.Column(db.Integer, primary_key=True)
    recepta_id = db.Column(db.Integer, db.ForeignKey('recepta.id'), nullable=False)
    nazwa = db.Column(db.String(100), nullable=False)
    dawkowanie = db.Column(db.String(200), nullable=False)
    ilosc = db.Column(db.Integer, nullable=False)
    refundacja = db.Column(db.Boolean, default=False)
    
    def __init__(self, recepta_id, nazwa, dawkowanie, ilosc, refundacja=False):
        self.recepta_id = recepta_id
        self.nazwa = nazwa
        self.dawkowanie = dawkowanie
        self.ilosc = ilosc
        self.refundacja = refundacja
    
    def to_dict(self):
        return {
            'id': self.id,
            'recepta_id': self.recepta_id,
            'nazwa': self.nazwa,
            'dawkowanie': self.dawkowanie,
            'ilosc': self.ilosc,
            'refundacja': self.refundacja
        }
    
    def __repr__(self):
        return f"<ReceptaLek {self.id}: {self.nazwa}, {self.ilosc} szt.>"