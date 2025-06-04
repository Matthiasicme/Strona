from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta, time
from sqlalchemy import and_, or_, func

from app import db
from models.lekarz import Lekarz
from models.wizyta import Termin, Wizyta
from models.admin import LogSystemowy
from models.pacjent import Pacjent
from utils.helpers import handle_error_response, role_required

lekarz_bp = Blueprint('lekarz', __name__)

@lekarz_bp.route('/', methods=['GET'])
def get_lekarze():
    """
    Pobieranie listy lekarzy
    ---
    tags:
      - Lekarze
    parameters:
      - name: specjalizacja
        in: query
        schema:
          type: string
      - name: aktywni
        in: query
        schema:
          type: boolean
    responses:
      200:
        description: Lista lekarzy
    """
    # Pobranie parametrów z zapytania
    specjalizacja = request.args.get('specjalizacja')
    aktywni = request.args.get('aktywni', 'true').lower() == 'true'
    
    # Budowanie zapytania
    query = Lekarz.query
    
    if specjalizacja:
        query = query.filter(Lekarz.specjalizacja == specjalizacja)
    
    if aktywni:
        query = query.filter(Lekarz.aktywny == True)
    
    # Sortowanie wyników
    query = query.order_by(Lekarz.nazwisko, Lekarz.imie)
    
    # Wykonanie zapytania
    lekarze = query.all()
    
    # Przygotowanie odpowiedzi
    result = []
    for lekarz in lekarze:
        lekarz_data = {
            'id': lekarz.id,
            'imie': lekarz.imie,
            'nazwisko': lekarz.nazwisko,
            'specjalizacja': lekarz.specjalizacja,
            'opis': lekarz.opis,
            'zdjecie_url': lekarz.zdjecie_url
        }
        result.append(lekarz_data)
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'lekarze': result
    }), 200


@lekarz_bp.route('/<int:lekarz_id>', methods=['GET'])
def get_lekarz(lekarz_id):
    """
    Pobieranie szczegółów lekarza
    ---
    tags:
      - Lekarze
    parameters:
      - name: lekarz_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Szczegóły lekarza
      404:
        description: Lekarz nie istnieje
    """
    lekarz = Lekarz.query.get(lekarz_id)
    if not lekarz:
        return handle_error_response(404, "Lekarz nie istnieje")
    
    # Przygotowanie odpowiedzi bez wrażliwych danych
    result = {
        'id': lekarz.id,
        'imie': lekarz.imie,
        'nazwisko': lekarz.nazwisko,
        'specjalizacja': lekarz.specjalizacja,
        'opis': lekarz.opis,
        'numer_pwz': lekarz.numer_pwz,
        'zdjecie_url': lekarz.zdjecie_url,
        'aktywny': lekarz.aktywny
    }
    
    return jsonify({
        'status': 'success',
        'lekarz': result
    }), 200


@lekarz_bp.route('/kalendarz', methods=['GET'])
@jwt_required()
@role_required('lekarz')
def get_moj_kalendarz():
    """
    Pobieranie kalendarza lekarza
    ---
    tags:
      - Lekarze
    security:
      - jwt: []
    parameters:
      - name: data_od
        in: query
        schema:
          type: string
          format: date
      - name: data_do
        in: query
        schema:
          type: string
          format: date
      - name: status
        in: query
        schema:
          type: string
    responses:
      200:
        description: Kalendarz lekarza
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    # Pobranie parametrów z zapytania
    data_od_str = request.args.get('data_od')
    data_do_str = request.args.get('data_do')
    status = request.args.get('status')
    
    # Przetworzenie dat
    try:
        data_od = datetime.strptime(data_od_str, '%Y-%m-%d').date() if data_od_str else datetime.now().date()
        data_do = datetime.strptime(data_do_str, '%Y-%m-%d').date() if data_do_str else (data_od + timedelta(days=30))
    except ValueError:
        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
    
    # Budowanie zapytania dla terminów
    terminy_query = Termin.query.filter(
        Termin.lekarz_id == lekarz_id,
        Termin.data >= data_od,
        Termin.data <= data_do
    ).order_by(Termin.data, Termin.godzina_od)
    
    # Wykonanie zapytania
    terminy = terminy_query.all()
    
    # Przygotowanie odpowiedzi
    result = []
    for termin in terminy:
        termin_data = termin.to_dict()
        
        # Dodanie informacji o wizycie, jeśli termin jest zajęty
        if not termin.dostepny:
            wizyta = Wizyta.query.filter_by(termin_id=termin.id).first()
            if wizyta:
                # Filtrowanie po statusie wizyty, jeśli podano
                if status and wizyta.status != status:
                    continue
                
                termin_data['wizyta'] = {
                    'id': wizyta.id,
                    'status': wizyta.status,
                    'pacjent_id': wizyta.pacjent_id,
                    'opis': wizyta.opis
                }
        
        result.append(termin_data)
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'terminy': result
    }), 200


@lekarz_bp.route('/kalendarz/termin', methods=['POST'])
@jwt_required()
@role_required('lekarz')
def dodaj_terminy():
    """
    Dodawanie terminów do kalendarza
    ---
    tags:
      - Lekarze
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              data:
                type: string
                format: date
              godzina_od:
                type: string
                format: time
              godzina_do:
                type: string
                format: time
              interwal:
                type: integer
              cykliczne:
                type: boolean
              liczba_tygodni:
                type: integer
    responses:
      201:
        description: Terminy zostały dodane pomyślnie
      400:
        description: Błędne dane
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'data' not in data or 'godzina_od' not in data or 'godzina_do' not in data:
        return handle_error_response(400, "Brak wymaganych pól: data, godzina_od, godzina_do")
    
    try:
        # Przetworzenie daty i godzin
        data_terminu = datetime.strptime(data['data'], '%Y-%m-%d').date()
        godzina_od = datetime.strptime(data['godzina_od'], '%H:%M').time()
        godzina_do = datetime.strptime(data['godzina_do'], '%H:%M').time()
        
        # Sprawdzenie czy godzina rozpoczęcia jest przed godziną zakończenia
        if godzina_od >= godzina_do:
            return handle_error_response(400, "Godzina rozpoczęcia musi być wcześniejsza niż godzina zakończenia")
        
        # Parametry opcjonalne
        interwal = data.get('interwal', 30)  # Domyślny interwał 30 minut
        cykliczne = data.get('cykliczne', False)
        liczba_tygodni = data.get('liczba_tygodni', 1)
        
        if interwal <= 0:
            return handle_error_response(400, "Interwał musi być większy od 0")
        
        if cykliczne and (liczba_tygodni <= 0 or liczba_tygodni > 52):
            return handle_error_response(400, "Liczba tygodni musi być w zakresie 1-52")
        
        # Utworzenie dat dla terminów cyklicznych
        daty = [data_terminu]
        if cykliczne:
            for i in range(1, liczba_tygodni):
                daty.append(data_terminu + timedelta(days=7 * i))
        
        # Utworzenie przedziałów czasowych na podstawie interwału
        terminy = []
        for data_term in daty:
            current_time = godzina_od
            while current_time < godzina_do:
                next_time = (datetime.combine(datetime.min, current_time) + timedelta(minutes=interwal)).time()
                if next_time <= godzina_do:
                    terminy.append((data_term, current_time, next_time))
                current_time = next_time
        
        # Dodanie terminów do bazy danych
        dodane_terminy = []
        for data_term, od, do in terminy:
            # Sprawdzenie czy termin już istnieje
            istniejacy_termin = Termin.query.filter_by(
                lekarz_id=lekarz_id,
                data=data_term,
                godzina_od=od,
                godzina_do=do
            ).first()
            
            if istniejacy_termin:
                continue
            
            termin = Termin(
                data=data_term,
                godzina_od=od,
                godzina_do=do,
                lekarz_id=lekarz_id
            )
            db.session.add(termin)
            dodane_terminy.append(termin)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="DODANIE_TERMINOW",
            opis=f"Dodano {len(dodane_terminy)} terminów dla lekarza ID: {lekarz_id}",
            uzytkownik_id=lekarz_id,
            rola_uzytkownika="lekarz",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Dodano {len(dodane_terminy)} nowych terminów',
            'terminy': [termin.to_dict() for termin in dodane_terminy]
        }), 201
        
    except ValueError as e:
        return handle_error_response(400, f"Niepoprawny format daty lub godziny: {str(e)}")
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas dodawania terminów: {str(e)}")


@lekarz_bp.route('/kalendarz/termin/<int:termin_id>', methods=['DELETE'])
@jwt_required()
@role_required('lekarz')
def usun_termin(termin_id):
    """
    Usuwanie terminu z kalendarza
    ---
    tags:
      - Lekarze
    security:
      - jwt: []
    parameters:
      - name: termin_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Termin został usunięty
      404:
        description: Termin nie istnieje
      403:
        description: Brak uprawnień do usunięcia terminu
      400:
        description: Nie można usunąć zajętego terminu
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    # Pobranie terminu
    termin = Termin.query.get(termin_id)
    if not termin:
        return handle_error_response(404, "Termin nie istnieje")
    
    # Sprawdzenie uprawnień
    if termin.lekarz_id != lekarz_id:
        return handle_error_response(403, "Brak uprawnień do usunięcia terminu")
    
    # Sprawdzenie czy termin jest dostępny
    if not termin.dostepny:
        return handle_error_response(400, "Nie można usunąć zajętego terminu")
    
    try:
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="USUNIECIE_TERMINU",
            opis=f"Usunięto termin ID: {termin_id} dla lekarza ID: {lekarz_id}",
            uzytkownik_id=lekarz_id,
            rola_uzytkownika="lekarz",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Usunięcie terminu
        db.session.delete(termin)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Termin został usunięty pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas usuwania terminu: {str(e)}")


@lekarz_bp.route('/pacjenci', methods=['GET'])
@jwt_required()
@role_required('lekarz')
def get_pacjenci_lekarza():
    """
    Pobieranie listy pacjentów lekarza
    ---
    tags:
      - Lekarze
    security:
      - jwt: []
    parameters:
      - name: search
        in: query
        schema:
          type: string
    responses:
      200:
        description: Lista pacjentów lekarza
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    # Pobranie parametrów z zapytania
    search = request.args.get('search', '')
    
    query = db.session.query(Pacjent).distinct().join(Wizyta).filter(Wizyta.lekarz_id == lekarz_id)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Pacjent.imie.ilike(search_pattern),
                Pacjent.nazwisko.ilike(search_pattern),
                Pacjent.email.ilike(search_pattern),
                Pacjent.telefon.ilike(search_pattern)
            )
        )
    
    # Sortowanie wyników
    query = query.order_by(Pacjent.nazwisko, Pacjent.imie)
    
    # Wykonanie zapytania
    pacjenci = query.all()
    
    # Przygotowanie odpowiedzi
    result = []
    for pacjent in pacjenci:
        # Policzenie liczby wizyt dla pacjenta u tego lekarza
        liczba_wizyt = Wizyta.query.filter_by(pacjent_id=pacjent.id, lekarz_id=lekarz_id).count()
        
        # Pobranie ostatniej wizyty
        ostatnia_wizyta = Wizyta.query.filter_by(pacjent_id=pacjent.id, lekarz_id=lekarz_id).order_by(Wizyta.data_utworzenia.desc()).first()
        
        pacjent_data = {
            'id': pacjent.id,
            'imie': pacjent.imie,
            'nazwisko': pacjent.nazwisko,
            'email': pacjent.email,
            'telefon': pacjent.telefon,
            'liczba_wizyt': liczba_wizyt,
            'ostatnia_wizyta': ostatnia_wizyta.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S') if ostatnia_wizyta else None
        }
        result.append(pacjent_data)
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'pacjenci': result
    }), 200


@lekarz_bp.route('/statystyki', methods=['GET'])
@jwt_required()
@role_required('lekarz')
def get_statystyki_lekarza():
    """
    Pobieranie statystyk lekarza
    ---
    tags:
      - Lekarze
    security:
      - jwt: []
    parameters:
      - name: okres
        in: query
        schema:
          type: string
          enum: [dzien, tydzien, miesiac, rok]
    responses:
      200:
        description: Statystyki lekarza
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    # Pobranie parametrów z zapytania
    okres = request.args.get('okres', 'miesiac')
    
    # Określenie dat na podstawie okresu
    today = datetime.now().date()
    
    if okres == 'dzien':
        data_od = today
        data_do = today
    elif okres == 'tydzien':
        data_od = today - timedelta(days=today.weekday())
        data_do = data_od + timedelta(days=6)
    elif okres == 'rok':
        data_od = datetime(today.year, 1, 1).date()
        data_do = datetime(today.year, 12, 31).date()
    else:  # miesiac (domyślnie)
        data_od = datetime(today.year, today.month, 1).date()
        if today.month == 12:
            data_do = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            data_do = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
    
    # Statystyki wizyt
    wizyty_query = Wizyta.query.join(Termin).filter(
        Wizyta.lekarz_id == lekarz_id,
        Termin.data >= data_od,
        Termin.data <= data_do
    )
    
    liczba_wizyt = wizyty_query.count()
    
    # Statystyki wizyt według statusu
    wizyty_statusy = db.session.query(
        Wizyta.status, func.count(Wizyta.id)
    ).join(Termin).filter(
        Wizyta.lekarz_id == lekarz_id,
        Termin.data >= data_od,
        Termin.data <= data_do
    ).group_by(Wizyta.status).all()
    
    statusy = {status: count for status, count in wizyty_statusy}
    
    # Statystyki terminów
    terminy_query = Termin.query.filter(
        Termin.lekarz_id == lekarz_id,
        Termin.data >= data_od,
        Termin.data <= data_do
    )
    
    liczba_terminow = terminy_query.count()
    liczba_dostepnych = terminy_query.filter(Termin.dostepny == True).count()
    liczba_zajetych = liczba_terminow - liczba_dostepnych
    
    # Przygotowanie odpowiedzi
    result = {
        'okres': okres,
        'data_od': data_od.strftime('%Y-%m-%d'),
        'data_do': data_do.strftime('%Y-%m-%d'),
        'liczba_wizyt': liczba_wizyt,
        'wizyty_statusy': statusy,
        'liczba_terminow': liczba_terminow,
        'liczba_dostepnych': liczba_dostepnych,
        'liczba_zajetych': liczba_zajetych,
        'procent_wypelnienia': round(liczba_zajetych / liczba_terminow * 100, 2) if liczba_terminow > 0 else 0
    }
    
    return jsonify({
        'status': 'success',
        'statystyki': result
    }), 200