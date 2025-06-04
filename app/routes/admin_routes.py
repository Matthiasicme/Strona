from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.pacjent import Pacjent
from models.lekarz import Lekarz
from models.wizyta import Wizyta, Termin, Usluga
from models.platnosc import Platnosc, MetodaPlatnosci
from models.admin import Administrator, LogSystemowy, Archiwizacja
from models.powiadomienie import PowiadomienieKonfiguracja
from utils.helpers import handle_error_response, role_required
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta, date
import pandas as pd
import io
import csv

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_users():
    """
    Pobieranie listy użytkowników
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    parameters:
      - name: type
        in: query
        schema:
          type: string
          enum: [pacjent, lekarz, admin, all]
      - name: search
        in: query
        schema:
          type: string
      - name: status
        in: query
        schema:
          type: string
          enum: [active, inactive, all]
    responses:
      200:
        description: Lista użytkowników
    """
    # Pobranie parametrów z zapytania
    user_type = request.args.get('type', 'all')
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    
    result = {
        'pacjenci': [],
        'lekarze': [],
        'admini': []
    }
    
    # Filtr statusu
    is_active = None
    if status == 'active':
        is_active = True
    elif status == 'inactive':
        is_active = False
    
    # Przygotowanie wzorca wyszukiwania
    search_pattern = f"%{search}%" if search else None
    
    # Pobranie pacjentów
    if user_type in ['pacjent', 'all']:
        query = Pacjent.query
        
        if is_active is not None:
            query = query.filter(Pacjent.aktywny == is_active)
        
        if search_pattern:
            query = query.filter(
                or_(
                    Pacjent.imie.ilike(search_pattern),
                    Pacjent.nazwisko.ilike(search_pattern),
                    Pacjent.email.ilike(search_pattern),
                    Pacjent.telefon.ilike(search_pattern)
                )
            )
        
        pacjenci = query.all()
        result['pacjenci'] = [pacjent.to_dict() for pacjent in pacjenci]
    
    # Pobranie lekarzy
    if user_type in ['lekarz', 'all']:
        query = Lekarz.query
        
        if is_active is not None:
            query = query.filter(Lekarz.aktywny == is_active)
        
        if search_pattern:
            query = query.filter(
                or_(
                    Lekarz.imie.ilike(search_pattern),
                    Lekarz.nazwisko.ilike(search_pattern),
                    Lekarz.email.ilike(search_pattern),
                    Lekarz.telefon.ilike(search_pattern),
                    Lekarz.specjalizacja.ilike(search_pattern)
                )
            )
        
        lekarze = query.all()
        result['lekarze'] = [lekarz.to_dict() for lekarz in lekarze]
    
    # Pobranie administratorów
    if user_type in ['admin', 'all']:
        query = Administrator.query
        
        if is_active is not None:
            query = query.filter(Administrator.aktywny == is_active)
        
        if search_pattern:
            query = query.filter(
                or_(
                    Administrator.imie.ilike(search_pattern),
                    Administrator.nazwisko.ilike(search_pattern),
                    Administrator.email.ilike(search_pattern)
                )
            )
        
        admini = query.all()
        result['admini'] = [admin.to_dict() for admin in admini]
    
    # Podsumowanie
    total_count = len(result['pacjenci']) + len(result['lekarze']) + len(result['admini'])
    
    return jsonify({
        'status': 'success',
        'count': total_count,
        'users': result
    }), 200


@admin_bp.route('/user/status', methods=['PUT'])
@jwt_required()
@role_required('admin')
def update_user_status():
    """
    Aktualizacja statusu użytkownika
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              user_type:
                type: string
                enum: [pacjent, lekarz, admin]
              user_id:
                type: integer
              active:
                type: boolean
    responses:
      200:
        description: Status użytkownika został zaktualizowany
      404:
        description: Użytkownik nie istnieje
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'user_type' not in data or 'user_id' not in data or 'active' not in data:
        return handle_error_response(400, "Brak wymaganych pól: user_type, user_id, active")
    
    user_type = data['user_type']
    user_id = data['user_id']
    active = data['active']
    
    try:
        # Aktualizacja statusu użytkownika w zależności od typu
        if user_type == 'pacjent':
            user = Pacjent.query.get(user_id)
            field_name = 'aktywny'
        elif user_type == 'lekarz':
            user = Lekarz.query.get(user_id)
            field_name = 'aktywny'
        elif user_type == 'admin':
            user = Administrator.query.get(user_id)
            field_name = 'aktywny'
            
            # Sprawdzenie czy administrator nie próbuje dezaktywować samego siebie
            if user_id == admin_id and not active:
                return handle_error_response(400, "Nie można dezaktywować własnego konta")
        else:
            return handle_error_response(400, "Nieprawidłowy typ użytkownika")
        
        if not user:
            return handle_error_response(404, "Użytkownik nie istnieje")
        
        # Aktualizacja statusu
        setattr(user, field_name, active)
        
        # Logowanie akcji
        action = "AKTYWACJA" if active else "DEZAKTYWACJA"
        log = LogSystemowy(
            typ="INFO",
            akcja=f"{action}_UZYTKOWNIKA",
            opis=f"{action} użytkownika typu {user_type}, ID: {user_id}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Status użytkownika został {("aktywowany" if active else "dezaktywowany")} pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas aktualizacji statusu: {str(e)}")


@admin_bp.route('/uslugi', methods=['POST'])
@jwt_required()
@role_required('admin')
def create_usluga():
    """
    Dodawanie nowej usługi
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              nazwa:
                type: string
              opis:
                type: string
              cena:
                type: number
              czas_trwania:
                type: integer
    responses:
      201:
        description: Usługa została dodana pomyślnie
      400:
        description: Błędne dane
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'nazwa' not in data or 'cena' not in data or 'czas_trwania' not in data:
        return handle_error_response(400, "Brak wymaganych pól: nazwa, cena, czas_trwania")
    
    try:
        # Sprawdzenie czy nazwa usługi jest unikalna
        if Usluga.query.filter(func.lower(Usluga.nazwa) == func.lower(data['nazwa'])).first():
            return handle_error_response(400, "Usługa o podanej nazwie już istnieje")
        
        # Utworzenie nowej usługi
        usluga = Usluga(
            nazwa=data['nazwa'],
            opis=data.get('opis'),
            cena=float(data['cena']),
            czas_trwania=int(data['czas_trwania']),
            aktywna=data.get('aktywna', True)
        )
        db.session.add(usluga)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="DODANIE_USLUGI",
            opis=f"Dodano nową usługę: {data['nazwa']}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Usługa została dodana pomyślnie',
            'usluga': usluga.to_dict()
        }), 201
        
    except ValueError:
        return handle_error_response(400, "Niepoprawny format ceny lub czasu trwania")
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas dodawania usługi: {str(e)}")


@admin_bp.route('/uslugi/<int:usluga_id>', methods=['PUT'])
@jwt_required()
@role_required('admin')
def update_usluga(usluga_id):
    """
    Aktualizacja usługi
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    parameters:
      - name: usluga_id
        in: path
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              nazwa:
                type: string
              opis:
                type: string
              cena:
                type: number
              czas_trwania:
                type: integer
              aktywna:
                type: boolean
    responses:
      200:
        description: Usługa została zaktualizowana pomyślnie
      404:
        description: Usługa nie istnieje
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    # Pobranie usługi
    usluga = Usluga.query.get(usluga_id)
    if not usluga:
        return handle_error_response(404, "Usługa nie istnieje")
    
    data = request.get_json()
    if not data:
        return handle_error_response(400, "Brak danych do aktualizacji")
    
    try:
        # Sprawdzenie czy nazwa usługi jest unikalna (jeśli zmieniona)
        if 'nazwa' in data and data['nazwa'] != usluga.nazwa:
            if Usluga.query.filter(
                func.lower(Usluga.nazwa) == func.lower(data['nazwa']),
                Usluga.id != usluga_id
            ).first():
                return handle_error_response(400, "Usługa o podanej nazwie już istnieje")
        
        # Aktualizacja pól
        if 'nazwa' in data:
            usluga.nazwa = data['nazwa']
        if 'opis' in data:
            usluga.opis = data['opis']
        if 'cena' in data:
            usluga.cena = float(data['cena'])
        if 'czas_trwania' in data:
            usluga.czas_trwania = int(data['czas_trwania'])
        if 'aktywna' in data:
            usluga.aktywna = bool(data['aktywna'])
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="AKTUALIZACJA_USLUGI",
            opis=f"Zaktualizowano usługę ID: {usluga_id}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Usługa została zaktualizowana pomyślnie',
            'usluga': usluga.to_dict()
        }), 200
        
    except ValueError:
        return handle_error_response(400, "Niepoprawny format ceny lub czasu trwania")
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas aktualizacji usługi: {str(e)}")


@admin_bp.route('/metody-platnosci', methods=['POST'])
@jwt_required()
@role_required('admin')
def create_metoda_platnosci():
    """
    Dodawanie nowej metody płatności
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              nazwa:
                type: string
              aktywna:
                type: boolean
    responses:
      201:
        description: Metoda płatności została dodana pomyślnie
      400:
        description: Błędne dane
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'nazwa' not in data:
        return handle_error_response(400, "Brak wymaganego pola: nazwa")
    
    try:
        # Sprawdzenie czy nazwa metody płatności jest unikalna
        if MetodaPlatnosci.query.filter(func.lower(MetodaPlatnosci.nazwa) == func.lower(data['nazwa'])).first():
            return handle_error_response(400, "Metoda płatności o podanej nazwie już istnieje")
        
        # Utworzenie nowej metody płatności
        metoda = MetodaPlatnosci(
            nazwa=data['nazwa'],
            aktywna=data.get('aktywna', True)
        )
        db.session.add(metoda)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="DODANIE_METODY_PLATNOSCI",
            opis=f"Dodano nową metodę płatności: {data['nazwa']}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Metoda płatności została dodana pomyślnie',
            'metoda': metoda.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas dodawania metody płatności: {str(e)}")


@admin_bp.route('/metody-platnosci/<int:metoda_id>', methods=['PUT'])
@jwt_required()
@role_required('admin')
def update_metoda_platnosci(metoda_id):
    """
    Aktualizacja metody płatności
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    parameters:
      - name: metoda_id
        in: path
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              nazwa:
                type: string
              aktywna:
                type: boolean
    responses:
      200:
        description: Metoda płatności została zaktualizowana pomyślnie
      404:
        description: Metoda płatności nie istnieje
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    # Pobranie metody płatności
    metoda = MetodaPlatnosci.query.get(metoda_id)
    if not metoda:
        return handle_error_response(404, "Metoda płatności nie istnieje")
    
    data = request.get_json()
    if not data:
        return handle_error_response(400, "Brak danych do aktualizacji")
    
    try:
        # Sprawdzenie czy nazwa metody płatności jest unikalna (jeśli zmieniona)
        if 'nazwa' in data and data['nazwa'] != metoda.nazwa:
            if MetodaPlatnosci.query.filter(
                func.lower(MetodaPlatnosci.nazwa) == func.lower(data['nazwa']),
                MetodaPlatnosci.id != metoda_id
            ).first():
                return handle_error_response(400, "Metoda płatności o podanej nazwie już istnieje")
        
        # Aktualizacja pól
        if 'nazwa' in data:
            metoda.nazwa = data['nazwa']
        if 'aktywna' in data:
            metoda.aktywna = bool(data['aktywna'])
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="AKTUALIZACJA_METODY_PLATNOSCI",
            opis=f"Zaktualizowano metodę płatności ID: {metoda_id}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Metoda płatności została zaktualizowana pomyślnie',
            'metoda': metoda.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas aktualizacji metody płatności: {str(e)}")


@admin_bp.route('/powiadomienia/konfiguracja', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_powiadomienia_konfiguracja():
    """
    Pobieranie konfiguracji powiadomień
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    responses:
      200:
        description: Lista konfiguracji powiadomień
    """
    # Pobranie wszystkich konfiguracji powiadomień
    konfiguracje = PowiadomienieKonfiguracja.query.all()
    
    # Przygotowanie odpowiedzi
    result = [konfiguracja.to_dict() for konfiguracja in konfiguracje]
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'konfiguracje': result
    }), 200


@admin_bp.route('/powiadomienia/konfiguracja', methods=['POST'])
@jwt_required()
@role_required('admin')
def create_powiadomienie_konfiguracja():
    """
    Dodawanie nowej konfiguracji powiadomień
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              typ:
                type: string
              czas_przed_wizyta:
                type: integer
              szablon_email:
                type: string
              szablon_sms:
                type: string
              aktywny:
                type: boolean
    responses:
      201:
        description: Konfiguracja powiadomień została dodana pomyślnie
      400:
        description: Błędne dane
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'typ' not in data:
        return handle_error_response(400, "Brak wymaganego pola: typ")
    
    try:
        # Sprawdzenie czy typ konfiguracji jest unikalny
        if PowiadomienieKonfiguracja.query.filter_by(typ=data['typ']).first():
            return handle_error_response(400, "Konfiguracja o podanym typie już istnieje")
        
        # Utworzenie nowej konfiguracji
        konfiguracja = PowiadomienieKonfiguracja(
            typ=data['typ'],
            czas_przed_wizyta=data.get('czas_przed_wizyta'),
            szablon_email=data.get('szablon_email'),
            szablon_sms=data.get('szablon_sms'),
            aktywny=data.get('aktywny', True)
        )
        db.session.add(konfiguracja)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="DODANIE_KONFIGURACJI_POWIADOMIENIA",
            opis=f"Dodano nową konfigurację powiadomienia typu: {data['typ']}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Konfiguracja powiadomień została dodana pomyślnie',
            'konfiguracja': konfiguracja.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas dodawania konfiguracji: {str(e)}")


@admin_bp.route('/archiwizacja', methods=['POST'])
@jwt_required()
@role_required('admin')
def create_archiwizacja():
    """
    Tworzenie nowej archiwizacji
    ---
    tags:
      - Administracja
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              nazwa:
                type: string
              opis:
                type: string
              typ:
                type: string
                enum: [PELNA, PRZYROSTOWA]
    responses:
      201:
        description: Archiwizacja została zainicjowana pomyślnie
      400:
        description: Błędne dane
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'nazwa' not in data or 'typ' not in data:
        return handle_error_response(400, "Brak wymaganych pól: nazwa, typ")
    
    if data['typ'] not in ['PELNA', 'PRZYROSTOWA']:
        return handle_error_response(400, "Nieprawidłowy typ archiwizacji. Dozwolone wartości: PELNA, PRZYROSTOWA")
    
    try:
        # Utworzenie nowej archiwizacji
        archiwizacja = Archiwizacja(
            nazwa=data['nazwa'],
            opis=data.get('opis'),
            typ=data['typ'],
            administrator_id=admin_id
        )
        db.session.add(archiwizacja)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="ROZPOCZECIE_ARCHIWIZACJI",
            opis=f"Rozpoczęto archiwizację: {data['nazwa']}, typ: {data['typ']}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        # Tutaj można uruchomić proces archiwizacji w tle
        # W prawdziwej implementacji byłoby to zadanie asynchroniczne
        
        return jsonify({
            'status': 'success',
            'message': 'Archiwizacja została zainicjowana pomyślnie',
            'archiwizacja': archiwizacja.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas inicjowania archiwizacji: {str(e)}")


@admin_bp.route('/raporty/wizyty', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_raport_wizyty():
    """
    Generowanie raportu wizyt
    ---
    tags:
      - Raporty
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
      - name: lekarz_id
        in: query
        schema:
          type: integer
      - name: format
        in: query
        schema:
          type: string
          enum: [json, csv]
    responses:
      200:
        description: Raport wizyt
    """
    # Pobranie parametrów z zapytania
    data_od_str = request.args.get('data_od')
    data_do_str = request.args.get('data_do')
    status = request.args.get('status')
    lekarz_id = request.args.get('lekarz_id', type=int)
    export_format = request.args.get('format', 'json')
    
    # Przetworzenie dat
    try:
        data_od = datetime.strptime(data_od_str, '%Y-%m-%d').date() if data_od_str else (datetime.now().date() - timedelta(days=30))
        data_do = datetime.strptime(data_do_str, '%Y-%m-%d').date() if data_do_str else datetime.now().date()
    except ValueError:
        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
    
    # Budowanie zapytania
    query = db.session.query(
        Wizyta.id,
        Wizyta.status,
        Wizyta.data_utworzenia,
        Termin.data,
        Termin.godzina_od,
        Termin.godzina_do,
        Pacjent.id.label('pacjent_id'),
        Pacjent.imie.label('pacjent_imie'),
        Pacjent.nazwisko.label('pacjent_nazwisko'),
        Lekarz.id.label('lekarz_id'),
        Lekarz.imie.label('lekarz_imie'),
        Lekarz.nazwisko.label('lekarz_nazwisko'),
        Lekarz.specjalizacja,
        Platnosc.kwota,
        Platnosc.status.label('platnosc_status')
    ).join(
        Termin, Wizyta.termin_id == Termin.id
    ).join(
        Pacjent, Wizyta.pacjent_id == Pacjent.id
    ).join(
        Lekarz, Wizyta.lekarz_id == Lekarz.id
    ).outerjoin(
        Platnosc, Wizyta.platnosc_id == Platnosc.id
    ).filter(
        Termin.data >= data_od,
        Termin.data <= data_do
    )
    
    if status:
        query = query.filter(Wizyta.status == status)
    
    if lekarz_id:
        query = query.filter(Wizyta.lekarz_id == lekarz_id)
    
    # Sortowanie wyników
    query = query.order_by(Termin.data, Termin.godzina_od)
    
    # Wykonanie zapytania
    wizyty = query.all()
    
    # Przygotowanie danych do eksportu
    result = []
    for wizyta in wizyty:
        result.append({
            'wizyta_id': wizyta.id,
            'status': wizyta.status,
            'data_utworzenia': wizyta.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S'),
            'data_wizyty': wizyta.data.strftime('%Y-%m-%d'),
            'godzina_od': wizyta.godzina_od.strftime('%H:%M'),
            'godzina_do': wizyta.godzina_do.strftime('%H:%M'),
            'pacjent_id': wizyta.pacjent_id,
            'pacjent': f"{wizyta.pacjent_imie} {wizyta.pacjent_nazwisko}",
            'lekarz_id': wizyta.lekarz_id,
            'lekarz': f"{wizyta.lekarz_imie} {wizyta.lekarz_nazwisko}",
            'specjalizacja': wizyta.specjalizacja,
            'kwota': float(wizyta.kwota) if wizyta.kwota else None,
            'platnosc_status': wizyta.platnosc_status
        })
    
    # Eksport w wybranym formacie
    if export_format == 'csv':
        # Utworzenie DataFrame z danymi
        df = pd.DataFrame(result)
        
        # Konwersja do CSV
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_NONNUMERIC)
        
        # Przygotowanie odpowiedzi
        response = jsonify({
            'status': 'success',
            'count': len(result),
            'data': output.getvalue()
        })
        
        # Ustawienie nagłówków dla pliku CSV
        # response.headers["Content-Disposition"] = f"attachment; filename=raport_wizyty_{data_od}_{data_do}.csv"
        # response.headers["Content-Type"] = "text/csv"
        
        return response, 200
    else:
        # Domyślnie JSON
        return jsonify({
            'status': 'success',
            'count': len(result),
            'parametry': {
                'data_od': data_od.strftime('%Y-%m-%d'),
                'data_do': data_do.strftime('%Y-%m-%d'),
                'status': status,
                'lekarz_id': lekarz_id
            },
            'wizyty': result
        }), 200


@admin_bp.route('/raporty/platnosci', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_raport_platnosci():
    """
    Generowanie raportu płatności
    ---
    tags:
      - Raporty
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
      - name: metoda_platnosci_id
        in: query
        schema:
          type: integer
      - name: format
        in: query
        schema:
          type: string
          enum: [json, csv]
    responses:
      200:
        description: Raport płatności
    """
    # Pobranie parametrów z zapytania
    data_od_str = request.args.get('data_od')
    data_do_str = request.args.get('data_do')
    status = request.args.get('status')
    metoda_platnosci_id = request.args.get('metoda_platnosci_id', type=int)
    export_format = request.args.get('format', 'json')
    
    # Przetworzenie dat
    try:
        data_od = datetime.strptime(data_od_str, '%Y-%m-%d').date() if data_od_str else (datetime.now().date() - timedelta(days=30))
        data_do = datetime.strptime(data_do_str, '%Y-%m-%d').date() if data_do_str else datetime.now().date()
    except ValueError:
        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
    
    # Budowanie zapytania
    query = db.session.query(
        Platnosc.id,
        Platnosc.kwota,
        Platnosc.status,
        Platnosc.identyfikator_transakcji,
        Platnosc.data_platnosci,
        Platnosc.data_utworzenia,
        MetodaPlatnosci.id.label('metoda_id'),
        MetodaPlatnosci.nazwa.label('metoda_nazwa'),
        Wizyta.id.label('wizyta_id'),
        Wizyta.status.label('wizyta_status'),
        Pacjent.id.label('pacjent_id'),
        Pacjent.imie.label('pacjent_imie'),
        Pacjent.nazwisko.label('pacjent_nazwisko')
    ).outerjoin(
        MetodaPlatnosci, Platnosc.metoda_platnosci_id == MetodaPlatnosci.id
    ).join(
        Wizyta, Wizyta.platnosc_id == Platnosc.id
    ).join(
        Pacjent, Wizyta.pacjent_id == Pacjent.id
    ).filter(
        Platnosc.data_utworzenia >= datetime.combine(data_od, datetime.min.time()),
        Platnosc.data_utworzenia <= datetime.combine(data_do, datetime.max.time())
    )
    
    if status:
        query = query.filter(Platnosc.status == status)
    
    if metoda_platnosci_id:
        query = query.filter(Platnosc.metoda_platnosci_id == metoda_platnosci_id)
    
    # Sortowanie wyników
    query = query.order_by(desc(Platnosc.data_utworzenia))
    
    # Wykonanie zapytania
    platnosci = query.all()
    
    # Przygotowanie danych do eksportu
    result = []
    for platnosc in platnosci:
        result.append({
            'platnosc_id': platnosc.id,
            'kwota': float(platnosc.kwota) if platnosc.kwota else None,
            'status': platnosc.status,
            'identyfikator_transakcji': platnosc.identyfikator_transakcji,
            'data_platnosci': platnosc.data_platnosci.strftime('%Y-%m-%d %H:%M:%S') if platnosc.data_platnosci else None,
            'data_utworzenia': platnosc.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S'),
            'metoda_id': platnosc.metoda_id,
            'metoda_nazwa': platnosc.metoda_nazwa,
            'wizyta_id': platnosc.wizyta_id,
            'wizyta_status': platnosc.wizyta_status,
            'pacjent_id': platnosc.pacjent_id,
            'pacjent': f"{platnosc.pacjent_imie} {platnosc.pacjent_nazwisko}"
        })
    
    # Eksport w wybranym formacie
    if export_format == 'csv':
        # Utworzenie DataFrame z danymi
        df = pd.DataFrame(result)
        
        # Konwersja do CSV
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_NONNUMERIC)
        
        # Przygotowanie odpowiedzi
        response = jsonify({
            'status': 'success',
            'count': len(result),
            'data': output.getvalue()
        })
        
        # Ustawienie nagłówków dla pliku CSV
        # response.headers["Content-Disposition"] = f"attachment; filename=raport_platnosci_{data_od}_{data_do}.csv"
        # response.headers["Content-Type"] = "text/csv"
        
        return response, 200
    else:
        # Domyślnie JSON
        return jsonify({
            'status': 'success',
            'count': len(result),
            'parametry': {
                'data_od': data_od.strftime('%Y-%m-%d'),
                'data_do': data_do.strftime('%Y-%m-%d'),
                'status': status,
                'metoda_platnosci_id': metoda_platnosci_id
            },
            'platnosci': result
        }), 200


@admin_bp.route('/statystyki/dashboard', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_dashboard_statistics():
    """
    Pobieranie statystyk dla dashboardu administratora
    ---
    tags:
      - Raporty
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
        description: Statystyki dla dashboardu
    """
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
    
    try:
        # Statystyki wizyt
        wizyty_query = Wizyta.query.join(Termin).filter(
            Termin.data >= data_od,
            Termin.data <= data_do
        )
        
        liczba_wizyt = wizyty_query.count()
        
        # Statystyki wizyt według statusu
        wizyty_statusy = db.session.query(
            Wizyta.status, func.count(Wizyta.id)
        ).join(Termin).filter(
            Termin.data >= data_od,
            Termin.data <= data_do
        ).group_by(Wizyta.status).all()
        
        statusy = {status: count for status, count in wizyty_statusy}
        
        # Statystyki płatności
        platnosci_query = db.session.query(
            Platnosc.status, func.count(Platnosc.id), func.sum(Platnosc.kwota)
        ).filter(
            Platnosc.data_utworzenia >= datetime.combine(data_od, datetime.min.time()),
            Platnosc.data_utworzenia <= datetime.combine(data_do, datetime.max.time())
        ).group_by(Platnosc.status).all()
        
        platnosci = {}
        total_przychod = 0
        
        for status, count, kwota in platnosci_query:
            platnosci[status] = {
                'count': count,
                'kwota': float(kwota) if kwota else 0
            }
            if status == 'ZATWIERDZONA':
                total_przychod += float(kwota) if kwota else 0
        
        # Statystyki lekarzy
        lekarze_query = db.session.query(
            Lekarz.id, Lekarz.imie, Lekarz.nazwisko, func.count(Wizyta.id)
        ).join(Wizyta).join(Termin).filter(
            Termin.data >= data_od,
            Termin.data <= data_do
        ).group_by(Lekarz.id, Lekarz.imie, Lekarz.nazwisko).order_by(func.count(Wizyta.id).desc()).limit(5).all()
        
        top_lekarze = []
        for id, imie, nazwisko, count in lekarze_query:
            top_lekarze.append({
                'id': id,
                'imie': imie,
                'nazwisko': nazwisko,
                'liczba_wizyt': count
            })
        
        # Przygotowanie odpowiedzi
        result = {
            'okres': okres,
            'data_od': data_od.strftime('%Y-%m-%d'),
            'data_do': data_do.strftime('%Y-%m-%d'),
            'liczba_wizyt': liczba_wizyt,
            'wizyty_statusy': statusy,
            'platnosci': platnosci,
            'przychod': total_przychod,
            'top_lekarze': top_lekarze
        }
        
        return jsonify({
            'status': 'success',
            'statystyki': result
        }), 200
        
    except Exception as e:
        return handle_error_response(500, f"Wystąpił błąd podczas pobierania statystyk: {str(e)}")