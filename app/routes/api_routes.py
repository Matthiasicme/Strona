from flask import Blueprint, jsonify, redirect, url_for, current_app, request
from flask_login import login_required, current_user
from flask_jwt_extended import get_jwt_identity
from models.lekarz import Lekarz
from models.usluga import Usluga
from models.pacjent import Pacjent
from models.termin import Termin
from models.wizyta import Wizyta
from datetime import datetime, time, date
from sqlalchemy import and_, or_
from app import db

api_bp = Blueprint('api', __name__)

@api_bp.route('/lekarze')
@login_required
def get_lekarze():
    """Pobierz listę aktywnych lekarzy."""
    lekarze = Lekarz.query.filter_by(aktywny=True).all()
    return jsonify([{
        'id': l.id,
        'imie': l.imie,
        'nazwisko': l.nazwisko,
        'tytul':'dr',
        'specjalizacja': l.specjalizacja,
        'opis': l.opis
    } for l in lekarze])

@api_bp.route('/uslugi')
@login_required
def get_uslugi():
    """Pobierz listę aktywnych usług."""
    uslugi = Usluga.query.filter_by(aktywna=True).all()
    return jsonify([{
        'id': u.id,
        'nazwa': u.nazwa,
        'opis': u.opis,
        'cena': float(u.cena) if u.cena else 0,
        'czas_trwania': u.czas_trwania,
        'kategoria': u.kategoria
    } for u in uslugi])

@api_bp.route('/wizyty')
@login_required
def get_wizyty():
    """Pobierz wizyty użytkownika do wyświetlenia w kalendarzu."""
    from models.wizyta import Wizyta
    from models.termin import Termin
    
    wizyty = db.session.query(Wizyta, Termin).join(Termin).filter(
        Wizyta.pacjent_id == current_user.id
    ).all()
    
    events = []
    for wizyta, termin in wizyty:
        events.append({
            'id': wizyta.id,
            'title': f'Wizyta u {wizyta.lekarz.tytul} {wizyta.lekarz.nazwisko}',
            'start': f"{termin.data.isoformat()}T{termin.godzina_od.isoformat()}",
            'end': f"{termin.data.isoformat()}T{termin.godzina_do.isoformat()}",
            'status': wizyta.status,
            'className': f'status-{wizyta.status.lower()}'
        })
    
    return jsonify(events)

@api_bp.route('/pacjenci')
@login_required
def get_pacjenci():
    """Pobierz listę pacjentów (dla lekarzy) lub zwróć dane własnego konta (dla pacjentów)."""
    # Sprawdź czy użytkownik to lekarz
    if hasattr(current_user, 'rola') and current_user.rola == 'lekarz':
        # Pobierz pacjentów przypisanych do lekarza
        pacjenci = db.session.query(Pacjent).join(Wizyta).filter(Wizyta.lekarz_id == current_user.id).distinct().all()
    else:
        # Dla pacjenta zwróć tylko jego dane
        pacjenci = [current_user]
    
    # Przygotuj odpowiedź
    result = [{
        'id': p.id,
        'imie': p.imie,
        'nazwisko': p.nazwisko,
        'email': p.email,
        'telefon': getattr(p, 'telefon', ''),
        'pesel': getattr(p, 'pesel', '')
    } for p in pacjenci]
    
    return jsonify(result)

@api_bp.route('/terminy')
@login_required
def get_terminy():
    """Pobierz dostępne terminy w podanym zakresie dat dla danego lekarza."""
    lekarz_id = request.args.get('lekarz_id', type=int)
    data_od = request.args.get('data_od')
    data_do = request.args.get('data_do')
    
    if not all([lekarz_id, data_od, data_do]):
        return jsonify({'status': 'error', 'message': 'Brak wymaganych parametrów'}), 400
    
    try:
        data_od = datetime.strptime(data_od, '%Y-%m-%d').date()
        data_do = datetime.strptime(data_do, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Nieprawidłowy format daty. Użyj formatu RRRR-MM-DD'}), 400
    
    try:
        # Pobierz wszystkie terminy dla danego lekarza w podanym zakresie dat
        wszystkie_terminy = Termin.query.filter(
            Termin.lekarz_id == lekarz_id,
            Termin.data.between(data_od, data_do)
        ).all()
        
        # Przygotuj odpowiedź
        result = []
        for termin in wszystkie_terminy:
            # Sprawdź czy termin ma przypisaną wizytę
            has_wizyta = termin.wizyta is not None
            status = 'zajety' if has_wizyta else 'wolny'
            
            result.append({
                'id': termin.id,
                'lekarz_id': termin.lekarz_id,
                'data': termin.data.isoformat(),
                'godzina_od': termin.godzina_od.strftime('%H:%M'),
                'godzina_do': termin.godzina_do.strftime('%H:%M'),
                'status': status
            })
        
        return jsonify({
            'status': 'success',
            'terminy': result
        })
        
    except Exception as e:
        current_app.logger.error(f'Error in get_terminy: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': f'Wystąpił błąd serwera: {str(e)}'
        }), 500
