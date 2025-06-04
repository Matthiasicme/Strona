from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import json
from sqlalchemy import and_, or_, func

from app import db
from models.pacjent import Pacjent
from models.wizyta import Wizyta, Termin
from models.platnosc import Platnosc
from models.dokumentacja import DiagramDentystyczny, Recepta
from models.admin import LogSystemowy
from models.lekarz import Lekarz
from utils.helpers import handle_error_response, role_required, sanitize_input
from utils.validators import validate_email, validate_password, validate_phone

pacjent_bp = Blueprint('pacjent', __name__)

@pacjent_bp.route('/profile', methods=['GET'])
@jwt_required()
@role_required('pacjent')
def get_profile():
    """
    Pobieranie profilu pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    responses:
      200:
        description: Profil pacjenta
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    # Przygotowanie odpowiedzi bez wrażliwych danych
    profile = {
        'id': pacjent.id,
        'imie': pacjent.imie,
        'nazwisko': pacjent.nazwisko,
        'email': pacjent.email,
        'telefon': pacjent.telefon,
        'data_urodzenia': pacjent.data_urodzenia.strftime('%Y-%m-%d') if pacjent.data_urodzenia else None,
        'adres': pacjent.adres,
        'kod_pocztowy': pacjent.kod_pocztowy,
        'miasto': pacjent.miasto,
        'kraj': pacjent.kraj,
        'pesel': pacjent.pesel,
        'email_zweryfikowany': pacjent.email_zweryfikowany,
        'aktywny': pacjent.aktywny,
        'data_utworzenia': pacjent.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return jsonify({
        'status': 'success',
        'profile': profile
    }), 200


@pacjent_bp.route('/profile', methods=['PUT'])
@jwt_required()
@role_required('pacjent')
def update_profile():
    """
    Aktualizacja profilu pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              imie:
                type: string
              nazwisko:
                type: string
              telefon:
                type: string
              data_urodzenia:
                type: string
                format: date
              adres:
                type: string
              kod_pocztowy:
                type: string
              miasto:
                type: string
              kraj:
                type: string
              pesel:
                type: string
    responses:
      200:
        description: Profil został zaktualizowany pomyślnie
      400:
        description: Błędne dane
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    data = request.get_json()
    if not data:
        return handle_error_response(400, "Brak danych do aktualizacji")
    
    try:
        # Aktualizacja pól
        updateable_fields = [
            'imie', 'nazwisko', 'telefon', 'data_urodzenia', 
            'adres', 'kod_pocztowy', 'miasto', 'kraj', 'pesel'
        ]
        
        for field in updateable_fields:
            if field in data:
                value = data[field]
                
                # Walidacja i sanityzacja danych
                if field == 'telefon' and value:
                    if not validate_phone(value):
                        return handle_error_response(400, "Niepoprawny format numeru telefonu")
                
                if field == 'data_urodzenia' and value:
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
                
                # Sanityzacja danych tekstowych
                if field in ['imie', 'nazwisko', 'adres', 'miasto', 'kraj']:
                    value = sanitize_input(value)
                
                setattr(pacjent, field, value)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="AKTUALIZACJA_PROFILU",
            opis=f"Zaktualizowano profil pacjenta ID: {pacjent_id}",
            uzytkownik_id=pacjent_id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Profil został zaktualizowany pomyślnie',
            'profile': pacjent.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas aktualizacji profilu: {str(e)}")


@pacjent_bp.route('/change-password', methods=['PUT'])
@jwt_required()
@role_required('pacjent')
def change_password():
    """
    Zmiana hasła pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              current_password:
                type: string
              new_password:
                type: string
    responses:
      200:
        description: Hasło zostało zmienione pomyślnie
      400:
        description: Błędne dane
      401:
        description: Nieprawidłowe aktualne hasło
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    data = request.get_json()
    if not data or 'current_password' not in data or 'new_password' not in data:
        return handle_error_response(400, "Brak wymaganych pól: current_password, new_password")
    
    current_password = data['current_password']
    new_password = data['new_password']
    
    # Sprawdzenie aktualnego hasła
    if not pacjent.check_password(current_password):
        return handle_error_response(401, "Nieprawidłowe aktualne hasło")
    
    # Walidacja nowego hasła
    if not validate_password(new_password):
        return handle_error_response(400, "Nowe hasło nie spełnia wymagań bezpieczeństwa")
    
    try:
        # Ustawienie nowego hasła
        pacjent.set_password(new_password)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="SECURITY",
            akcja="ZMIANA_HASLA",
            opis=f"Zmieniono hasło dla pacjenta ID: {pacjent_id}",
            uzytkownik_id=pacjent_id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Hasło zostało zmienione pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas zmiany hasła: {str(e)}")


@pacjent_bp.route('/historia', methods=['GET'])
@jwt_required()
@role_required('pacjent')
def get_historia():
    """
    Pobieranie historii medycznej pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    parameters:
      - name: include
        in: query
        schema:
          type: string
          enum: [wizyty, recepty, diagram, all]
      - name: od_daty
        in: query
        schema:
          type: string
          format: date
      - name: do_daty
        in: query
        schema:
          type: string
          format: date
    responses:
      200:
        description: Historia medyczna pacjenta
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    # Pobranie parametrów z zapytania
    include = request.args.get('include', 'all')
    od_daty_str = request.args.get('od_daty')
    do_daty_str = request.args.get('do_daty')
    
    # Przetworzenie dat
    try:
        od_daty = datetime.strptime(od_daty_str, '%Y-%m-%d').date() if od_daty_str else None
        do_daty = datetime.strptime(do_daty_str, '%Y-%m-%d').date() if do_daty_str else None
    except ValueError:
        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
    
    result = {}
    
    # Wizyty
    if include in ['wizyty', 'all']:
        wizyty_query = Wizyta.query.join(Termin).filter(Wizyta.pacjent_id == pacjent_id)
        
        if od_daty:
            wizyty_query = wizyty_query.filter(Termin.data >= od_daty)
        
        if do_daty:
            wizyty_query = wizyty_query.filter(Termin.data <= do_daty)
        
        wizyty_query = wizyty_query.order_by(Termin.data.desc(), Termin.godzina_od.desc())
        
        wizyty = wizyty_query.all()
        result['wizyty'] = [wizyta.to_dict(include_relations=True) for wizyta in wizyty]
    
    # Recepty
    if include in ['recepty', 'all']:
        recepty_query = Recepta.query.join(Wizyta).filter(Wizyta.pacjent_id == pacjent_id)
        
        if od_daty or do_daty:
            recepty_query = recepty_query.join(Termin)
            
            if od_daty:
                recepty_query = recepty_query.filter(Termin.data >= od_daty)
            
            if do_daty:
                recepty_query = recepty_query.filter(Termin.data <= do_daty)
        
        recepty_query = recepty_query.order_by(Recepta.data_utworzenia.desc())
        
        recepty = recepty_query.all()
        result['recepty'] = [recepta.to_dict(include_relations=True) for recepta in recepty]
    
    # Diagram dentystyczny
    if include in ['diagram', 'all']:
        diagram = DiagramDentystyczny.query.filter_by(pacjent_id=pacjent_id).all()
        result['diagram'] = [zab.to_dict() for zab in diagram]
    
    return jsonify({
        'status': 'success',
        'pacjent_id': pacjent_id,
        'historia': result
    }), 200


@pacjent_bp.route('/statystyki', methods=['GET'])
@jwt_required()
@role_required('pacjent')
def get_statystyki():
    """
    Pobieranie statystyk pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    parameters:
      - name: okres
        in: query
        schema:
          type: string
          enum: [miesiac, rok, wszystko]
    responses:
      200:
        description: Statystyki pacjenta
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    # Pobranie parametrów z zapytania
    okres = request.args.get('okres', 'wszystko')
    
    # Określenie dat na podstawie okresu
    today = datetime.now().date()
    
    if okres == 'miesiac':
        data_od = datetime(today.year, today.month, 1).date()
        if today.month == 12:
            data_do = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            data_do = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
    elif okres == 'rok':
        data_od = datetime(today.year, 1, 1).date()
        data_do = datetime(today.year, 12, 31).date()
    else:  # wszystko
        data_od = None
        data_do = None
    
    try:
        # Liczba wszystkich wizyt
        wizyty_query = Wizyta.query.filter(Wizyta.pacjent_id == pacjent_id)
        
        if data_od or data_do:
            wizyty_query = wizyty_query.join(Termin)
            
            if data_od:
                wizyty_query = wizyty_query.filter(Termin.data >= data_od)
            
            if data_do:
                wizyty_query = wizyty_query.filter(Termin.data <= data_do)
        
        liczba_wizyt = wizyty_query.count()
        
        # Wizyty według statusu
        wizyty_statusy = db.session.query(
            Wizyta.status, func.count(Wizyta.id)
        ).filter(Wizyta.pacjent_id == pacjent_id)
        
        if data_od or data_do:
            wizyty_statusy = wizyty_statusy.join(Termin)
            
            if data_od:
                wizyty_statusy = wizyty_statusy.filter(Termin.data >= data_od)
            
            if data_do:
                wizyty_statusy = wizyty_statusy.filter(Termin.data <= data_do)
        
        wizyty_statusy = wizyty_statusy.group_by(Wizyta.status).all()
        
        statusy = {status: count for status, count in wizyty_statusy}
        
        # Suma wydatków
        wydatki_query = db.session.query(func.sum(Platnosc.kwota)).join(
            Wizyta, Wizyta.platnosc_id == Platnosc.id
        ).filter(
            Wizyta.pacjent_id == pacjent_id,
            Platnosc.status == 'ZATWIERDZONA'
        )
        
        if data_od or data_do:
            wydatki_query = wydatki_query.join(Termin)
            
            if data_od:
                wydatki_query = wydatki_query.filter(Termin.data >= data_od)
            
            if data_do:
                wydatki_query = wydatki_query.filter(Termin.data <= data_do)
        
        suma_wydatkow = wydatki_query.scalar() or 0
        
        # Najczęściej wybierani lekarze
        lekarze_query = db.session.query(
            Wizyta.lekarz_id, func.count(Wizyta.id)
        ).filter(Wizyta.pacjent_id == pacjent_id)
        
        if data_od or data_do:
            lekarze_query = lekarze_query.join(Termin)
            
            if data_od:
                lekarze_query = lekarze_query.filter(Termin.data >= data_od)
            
            if data_do:
                lekarze_query = lekarze_query.filter(Termin.data <= data_do)
        
        lekarze_query = lekarze_query.group_by(Wizyta.lekarz_id).order_by(func.count(Wizyta.id).desc()).limit(3)
        
        top_lekarze = []
        for lekarz_id, count in lekarze_query.all():
            lekarz = Lekarz.query.get(lekarz_id)
            if lekarz:
                top_lekarze.append({
                    'id': lekarz.id,
                    'imie': lekarz.imie,
                    'nazwisko': lekarz.nazwisko,
                    'specjalizacja': lekarz.specjalizacja,
                    'liczba_wizyt': count
                })
        
        # Przygotowanie odpowiedzi
        result = {
            'okres': okres,
            'data_od': data_od.strftime('%Y-%m-%d') if data_od else None,
            'data_do': data_do.strftime('%Y-%m-%d') if data_do else None,
            'liczba_wizyt': liczba_wizyt,
            'wizyty_statusy': statusy,
            'suma_wydatkow': float(suma_wydatkow),
            'top_lekarze': top_lekarze
        }
        
        return jsonify({
            'status': 'success',
            'statystyki': result
        }), 200
        
    except Exception as e:
        return handle_error_response(500, f"Wystąpił błąd podczas pobierania statystyk: {str(e)}")


@pacjent_bp.route('/powiadomienia/preferencje', methods=['GET'])
@jwt_required()
@role_required('pacjent')
def get_powiadomienia_preferencje():
    """
    Pobieranie preferencji powiadomień pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    responses:
      200:
        description: Preferencje powiadomień pacjenta
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    # W rzeczywistej implementacji tutaj byłby kod do pobrania preferencji powiadomień z bazy danych
    # Na potrzeby demonstracji zwracamy przykładowe dane
    
    preferencje = {
        'email': True,
        'sms': True,
        'przypomnienie_wizyta': 24,  # godziny przed wizytą
        'potwierdzenie_wizyta': True,
        'anulowanie_wizyta': True,
        'powiadomienie_platnosc': True
    }
    
    return jsonify({
        'status': 'success',
        'preferencje': preferencje
    }), 200


@pacjent_bp.route('/powiadomienia/preferencje', methods=['PUT'])
@jwt_required()
@role_required('pacjent')
def update_powiadomienia_preferencje():
    """
    Aktualizacja preferencji powiadomień pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              email:
                type: boolean
              sms:
                type: boolean
              przypomnienie_wizyta:
                type: integer
              potwierdzenie_wizyta:
                type: boolean
              anulowanie_wizyta:
                type: boolean
              powiadomienie_platnosc:
                type: boolean
    responses:
      200:
        description: Preferencje powiadomień zostały zaktualizowane pomyślnie
      400:
        description: Błędne dane
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    data = request.get_json()
    if not data:
        return handle_error_response(400, "Brak danych do aktualizacji")
    
    try:
        # W rzeczywistej implementacji tutaj byłby kod do aktualizacji preferencji powiadomień w bazie danych
        # Na potrzeby demonstracji udajemy, że aktualizujemy dane
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="AKTUALIZACJA_PREFERENCJI_POWIADOMIEN",
            opis=f"Zaktualizowano preferencje powiadomień dla pacjenta ID: {pacjent_id}",
            uzytkownik_id=pacjent_id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Preferencje powiadomień zostały zaktualizowane pomyślnie',
            'preferencje': data
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas aktualizacji preferencji powiadomień: {str(e)}")


@pacjent_bp.route('/delete-account', methods=['DELETE'])
@jwt_required()
@role_required('pacjent')
def delete_account():
    """
    Usunięcie konta pacjenta
    ---
    tags:
      - Pacjent
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              password:
                type: string
    responses:
      200:
        description: Konto zostało usunięte pomyślnie
      400:
        description: Błędne dane
      401:
        description: Nieprawidłowe hasło
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie pacjenta
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    data = request.get_json()
    if not data or 'password' not in data:
        return handle_error_response(400, "Brak wymaganego pola: password")
    
    password = data['password']
    
    # Sprawdzenie hasła
    if not pacjent.check_password(password):
        return handle_error_response(401, "Nieprawidłowe hasło")
    
    try:
        # Sprawdzenie czy pacjent ma aktywne wizyty
        active_visits = Wizyta.query.join(Termin).filter(
            Wizyta.pacjent_id == pacjent_id,
            Wizyta.status.in_(['ZAPLANOWANA', 'POTWIERDZONA']),
            Termin.data >= datetime.now().date()
        ).count()
        
        if active_visits > 0:
            return handle_error_response(400, "Nie można usunąć konta, ponieważ masz zaplanowane wizyty")
        
        # W rzeczywistej implementacji możemy nie usuwać konta całkowicie, tylko je dezaktywować
        # i anonimizować dane, aby zachować integralność bazy danych
        
        # Dezaktywacja konta
        pacjent.aktywny = False
        pacjent.email = f"deleted_{pacjent.id}@example.com"  # Anonimizacja emaila
        pacjent.telefon = "**********"  # Anonimizacja telefonu
        pacjent.imie = "Usunięty"
        pacjent.nazwisko = "Użytkownik"
        pacjent.pesel = None
        pacjent.adres = None
        pacjent.kod_pocztowy = None
        pacjent.miasto = None
        pacjent.kraj = None
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="SECURITY",
            akcja="USUNIECIE_KONTA",
            opis=f"Usunięto konto pacjenta ID: {pacjent_id}",
            uzytkownik_id=pacjent_id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Konto zostało usunięte pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas usuwania konta: {str(e)}")