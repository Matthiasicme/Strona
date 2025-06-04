from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, get_jwt, verify_jwt_in_request
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from functools import wraps
import jwt as pyjwt

from app import db
from models.pacjent import Pacjent
from models.lekarz import Lekarz
from models.wizyta import Wizyta, Termin, WizytaUsluga, Usluga
from models.platnosc import Platnosc
from models.admin import LogSystemowy
from models.powiadomienie import Email, SMS
from utils.helpers import handle_error_response, role_required

wizyta_bp = Blueprint('wizyta', __name__)

@wizyta_bp.route('/terminy', methods=['GET'])
def get_terminy():
    """
    Pobieranie dostępnych terminów
    ---
    tags:
      - Wizyty
    parameters:
      - name: lekarz_id
        in: query
        schema:
          type: integer
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
    responses:
      200:
        description: Lista dostępnych terminów
    """
    # Pobranie parametrów z zapytania
    lekarz_id = request.args.get('lekarz_id', type=int)
    data_od_str = request.args.get('data_od')
    data_do_str = request.args.get('data_do')
    
    # Przetworzenie dat
    try:
        data_od = datetime.strptime(data_od_str, '%Y-%m-%d').date() if data_od_str else datetime.now().date()
        data_do = datetime.strptime(data_do_str, '%Y-%m-%d').date() if data_do_str else (data_od + timedelta(days=30))
    except ValueError:
        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
    
    # Budowanie zapytania
    query = Termin.query.filter(Termin.dostepny == True)
    
    if lekarz_id:
        query = query.filter(Termin.lekarz_id == lekarz_id)
    
    query = query.filter(and_(Termin.data >= data_od, Termin.data <= data_do))
    
    # Sortowanie wyników
    query = query.order_by(Termin.data, Termin.godzina_od)
    
    # Wykonanie zapytania
    terminy = query.all()
    
    # Przygotowanie odpowiedzi
    result = []
    for termin in terminy:
        item = termin.to_dict()
        
        # Dodanie informacji o lekarzu
        lekarz = Lekarz.query.get(termin.lekarz_id)
        if lekarz:
            item['lekarz'] = {
                'id': lekarz.id,
                'imie': lekarz.imie,
                'nazwisko': lekarz.nazwisko,
                'specjalizacja': lekarz.specjalizacja
            }
        
        result.append(item)
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'terminy': result
    }), 200


@wizyta_bp.route('/umow', methods=['POST'])
@jwt_required()
@role_required('pacjent')
def umow_wizyte():
    """
    Umawianie wizyty
    ---
    tags:
      - Wizyty
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              termin_id:
                type: integer
              uslugi:
                type: array
                items:
                  type: object
                  properties:
                    usluga_id:
                      type: integer
                    ilosc:
                      type: integer
    responses:
      201:
        description: Wizyta została umówiona pomyślnie
      400:
        description: Błędne dane lub termin jest już zajęty
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'termin_id' not in data:
        return handle_error_response(400, "Brak wymaganego pola: termin_id")
    
    termin_id = data['termin_id']
    
    # Sprawdzenie czy termin istnieje i jest dostępny
    termin = Termin.query.get(termin_id)
    if not termin:
        return handle_error_response(404, "Termin nie istnieje")
    
    if not termin.dostepny:
        return handle_error_response(400, "Termin jest już zajęty")
    
    # Sprawdzenie czy pacjent istnieje
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    try:
        # Utworzenie nowej wizyty
        wizyta = Wizyta(
            pacjent_id=pacjent_id,
            lekarz_id=termin.lekarz_id,
            termin_id=termin_id,
            status='ZAPLANOWANA'
        )
        
        # Dodanie opcjonalnych pól
        optional_fields = ['opis', 'notatka_wewnetrzna']
        for field in optional_fields:
            if field in data:
                setattr(wizyta, field, data[field])
        
        # Zapisanie wizyty do bazy danych
        db.session.add(wizyta)
        
        # Oznaczenie terminu jako zajęty
        termin.dostepny = False
        
        # Dodanie usług do wizyty, jeśli są dostępne
        if 'uslugi' in data and isinstance(data['uslugi'], list):
            total_kwota = 0
            
            for item in data['uslugi']:
                if 'usluga_id' not in item:
                    continue
                
                usluga_id = item['usluga_id']
                ilosc = item.get('ilosc', 1)
                
                usluga = Usluga.query.get(usluga_id)
                if not usluga:
                    continue
                
                wizyta_usluga = WizytaUsluga(
                    wizyta_id=wizyta.id,
                    usluga_id=usluga_id,
                    ilosc=ilosc
                )
                db.session.add(wizyta_usluga)
                
                total_kwota += float(usluga.cena) * ilosc
            
            # Utworzenie płatności dla wizyty
            if total_kwota > 0:
                platnosc = Platnosc(
                    kwota=total_kwota,
                    status='OCZEKUJĄCA'
                )
                db.session.add(platnosc)
                db.session.flush()  # Generowanie ID płatności
                
                # Przypisanie płatności do wizyty
                wizyta.platnosc_id = platnosc.id
        
        # Utworzenie powiadomień
        email = Email(
            wizyta_id=wizyta.id,
            temat="Potwierdzenie rejestracji wizyty",
            tresc=f"Potwierdzamy rejestrację wizyty w dniu {termin.data} o godzinie {termin.godzina_od}."
        )
        db.session.add(email)
        
        sms = SMS(
            wizyta_id=wizyta.id,
            tresc=f"Potwierdzamy wizytę {termin.data} o {termin.godzina_od}. Gabinet stomatologiczny."
        )
        db.session.add(sms)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="UMOWIENIE_WIZYTY",
            opis=f"Umówiono wizytę dla pacjenta ID: {pacjent_id}, termin ID: {termin_id}",
            uzytkownik_id=pacjent_id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        # TODO: Wysłanie powiadomień
        
        return jsonify({
            'status': 'success',
            'message': 'Wizyta została umówiona pomyślnie',
            'wizyta_id': wizyta.id,
            'platnosc_id': wizyta.platnosc_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas umawiania wizyty: {str(e)}")


@wizyta_bp.route('/<int:wizyta_id>', methods=['GET'])
@jwt_required()
def get_wizyta(wizyta_id):
    """
    Pobieranie szczegółów wizyty
    ---
    tags:
      - Wizyty
    security:
      - jwt: []
    parameters:
      - name: wizyta_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Szczegóły wizyty
      404:
        description: Wizyta nie istnieje
      403:
        description: Brak uprawnień do wyświetlenia wizyty
    """
    identity = get_jwt_identity()
    user_id = identity['id']
    role = identity['role']
    
    # Pobranie wizyty
    wizyta = Wizyta.query.get(wizyta_id)
    if not wizyta:
        return handle_error_response(404, "Wizyta nie istnieje")
    
    # Sprawdzenie uprawnień
    if role == 'pacjent' and wizyta.pacjent_id != user_id:
        return handle_error_response(403, "Brak uprawnień do wyświetlenia wizyty")
    elif role == 'lekarz' and wizyta.lekarz_id != user_id:
        return handle_error_response(403, "Brak uprawnień do wyświetlenia wizyty")
    
    # Przygotowanie odpowiedzi
    wizyta_data = wizyta.to_dict(include_relations=True)
    
    return jsonify({
        'status': 'success',
        'wizyta': wizyta_data
    }), 200


@wizyta_bp.route('/<int:wizyta_id>/anuluj', methods=['POST'])
@jwt_required()
def anuluj_wizyte(wizyta_id):
    """
    Anulowanie wizyty
    ---
    tags:
      - Wizyty
    security:
      - jwt: []
    parameters:
      - name: wizyta_id
        in: path
        required: true
        schema:
          type: integer
    requestBody:
      required: false
      content:
        application/json:
          schema:
            type: object
            properties:
              powod:
                type: string
    responses:
      200:
        description: Wizyta została anulowana pomyślnie
      404:
        description: Wizyta nie istnieje
      403:
        description: Brak uprawnień do anulowania wizyty
    """
    identity = get_jwt_identity()
    user_id = identity['id']
    role = identity['role']
    
    # Pobranie wizyty
    wizyta = Wizyta.query.get(wizyta_id)
    if not wizyta:
        return handle_error_response(404, "Wizyta nie istnieje")
    
    # Sprawdzenie uprawnień
    if role == 'pacjent' and wizyta.pacjent_id != user_id:
        return handle_error_response(403, "Brak uprawnień do anulowania wizyty")
    elif role == 'lekarz' and wizyta.lekarz_id != user_id:
        return handle_error_response(403, "Brak uprawnień do anulowania wizyty")
    
    # Sprawdzenie czy wizyta może być anulowana
    if wizyta.status == 'ANULOWANA':
        return handle_error_response(400, "Wizyta jest już anulowana")
    if wizyta.status == 'ZAKOŃCZONA':
        return handle_error_response(400, "Nie można anulować zakończonej wizyty")
    
    data = request.get_json() or {}
    powod = data.get('powod', '')
    
    try:
        # Aktualizacja statusu wizyty
        wizyta.status = 'ANULOWANA'
        wizyta.opis = f"{wizyta.opis or ''}\n\nAnulowano: {powod}"
        
        # Zwolnienie terminu
        termin = Termin.query.get(wizyta.termin_id)
        if termin:
            termin.dostepny = True
        
        # Anulowanie płatności, jeśli istnieje
        if wizyta.platnosc_id:
            platnosc = Platnosc.query.get(wizyta.platnosc_id)
            if platnosc and platnosc.status == 'OCZEKUJĄCA':
                platnosc.status = 'ANULOWANA'
        
        # Utworzenie powiadomień
        email = Email(
            wizyta_id=wizyta.id,
            temat="Anulowanie wizyty",
            tresc=f"Informujemy, że wizyta w dniu {termin.data} o godzinie {termin.godzina_od} została anulowana."
        )
        db.session.add(email)
        
        sms = SMS(
            wizyta_id=wizyta.id,
            tresc=f"Wizyta {termin.data} o {termin.godzina_od} została anulowana. Gabinet stomatologiczny."
        )
        db.session.add(sms)
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="ANULOWANIE_WIZYTY",
            opis=f"Anulowano wizytę ID: {wizyta_id}, powód: {powod}",
            uzytkownik_id=user_id,
            rola_uzytkownika=role,
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        # TODO: Wysłanie powiadomień
        
        return jsonify({
            'status': 'success',
            'message': 'Wizyta została anulowana pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas anulowania wizyty: {str(e)}")


@wizyta_bp.route('/moje', methods=['GET'])
@jwt_required()
def get_moje_wizyty():
    """
    Pobieranie wizyt użytkownika
    ---
    tags:
      - Wizyty
    security:
      - jwt: []
    parameters:
      - name: status
        in: query
        schema:
          type: string
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
    responses:
      200:
        description: Lista wizyt użytkownika
    """
    identity = get_jwt_identity()
    user_id = identity['id']
    role = identity['role']
    
    # Pobranie parametrów z zapytania
    status = request.args.get('status')
    data_od_str = request.args.get('data_od')
    data_do_str = request.args.get('data_do')
    
    # Przetworzenie dat
    try:
        data_od = datetime.strptime(data_od_str, '%Y-%m-%d').date() if data_od_str else None
        data_do = datetime.strptime(data_do_str, '%Y-%m-%d').date() if data_do_str else None
    except ValueError:
        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
    
    # Budowanie zapytania
    query = Wizyta.query
    
    if role == 'pacjent':
        query = query.filter(Wizyta.pacjent_id == user_id)
    elif role == 'lekarz':
        query = query.filter(Wizyta.lekarz_id == user_id)
    
    if status:
        query = query.filter(Wizyta.status == status)
    
    if data_od or data_do:
        query = query.join(Termin)
        
        if data_od:
            query = query.filter(Termin.data >= data_od)
        
        if data_do:
            query = query.filter(Termin.data <= data_do)
    
    # Sortowanie wyników
    query = query.join(Termin).order_by(Termin.data, Termin.godzina_od)
    
    # Wykonanie zapytania
    wizyty = query.all()
    
    # Przygotowanie odpowiedzi
    result = []
    for wizyta in wizyty:
        result.append(wizyta.to_dict(include_relations=True))
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'wizyty': result
    }), 200


@wizyta_bp.route('/uslugi', methods=['GET'])
def get_uslugi():
    """
    Pobieranie dostępnych usług
    ---
    tags:
      - Usługi
    parameters:
      - name: aktywne
        in: query
        schema:
          type: boolean
    responses:
      200:
        description: Lista dostępnych usług
    """
    try:
        # Pobranie parametrów z zapytania
        aktywne = request.args.get('aktywne', 'true').lower() == 'true'
        
        # Budowanie zapytania
        query = Usluga.query
        
        if aktywne:
            query = query.filter(Usluga.aktywna == True)
        
        # Wykonanie zapytania
        uslugi = query.order_by(Usluga.nazwa).all()
        
        # Przygotowanie odpowiedzi
        result = []
        for usluga in uslugi:
            result.append({
                'id': usluga.id,
                'nazwa': usluga.nazwa,
                'cena': float(usluga.cena) if usluga.cena else 0.0,
                'czas_trwania': usluga.czas_trwania,
                'opis': usluga.opis,
                'aktywna': usluga.aktywna
            })
        
        return jsonify({
            'status': 'success',
            'count': len(result),
            'uslugi': result
        }), 200
        
    except Exception as e:
        return handle_error_response(500, f"Wystąpił błąd podczas pobierania usług: {str(e)}")


@wizyta_bp.route('/lekarze', methods=['GET'])
@jwt_required()
def get_doctors():
    """
    Pobieranie listy lekarzy
    ---
    tags:
      - API
    responses:
      200:
        description: Lista lekarzy
    """
    try:
        doctors = Lekarz.query.all()
        result = []
        for doctor in doctors:
            result.append({
                'id': doctor.id,
                'imie': doctor.imie,
                'nazwisko': doctor.nazwisko,
                'specjalizacja': doctor.specjalizacja,
                'numer_pwz': doctor.numer_pwz,
                'numer_telefonu': doctor.numer_telefonu,
                'email': doctor.email
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@wizyta_bp.route('/pacjenci', methods=['GET'])
@jwt_required()
def get_patients():
    """
    Pobieranie listy pacjentów
    ---
    tags:
      - API
    responses:
      200:
        description: Lista pacjentów
    """
    try:
        patients = Pacjent.query.all()
        result = []
        for patient in patients:
            result.append({
                'id': patient.id,
                'imie': patient.imie,
                'nazwisko': patient.nazwisko,
                'pesel': patient.pesel,
                'data_urodzenia': patient.data_urodzenia.isoformat() if patient.data_urodzenia else None,
                'numer_telefonu': patient.numer_telefonu,
                'email': patient.email
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@wizyta_bp.route('/uslugi', methods=['GET'])
@jwt_required()
def get_services():
    """
    Pobieranie listy usług
    ---
    tags:
      - API
    responses:
      200:
        description: Lista usług
    """
    try:
        services = Usluga.query.filter_by(aktywna=True).all()
        result = []
        for service in services:
            result.append({
                'id': service.id,
                'nazwa': service.nazwa,
                'cena': float(service.cena) if service.cena else 0.0,
                'czas_trwania': service.czas_trwania,
                'opis': service.opis
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@wizyta_bp.route('', methods=['POST'])
def create_appointment():
    """
    Tworzenie nowej wizyty
    ---
    tags:
      - API
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              pacjent_id:
                type: integer
              lekarz_id:
                type: integer
              data:
                type: string
                format: date
              godzina:
                type: string
                format: time
              uslugi:
                type: array
                items:
                  type: integer
    responses:
      201:
        description: Wizyta została utworzona pomyślnie
      400:
        description: Błędne dane wejściowe
    """
    try:
        data = request.get_json()
        
        # Walidacja danych wejściowych
        required_fields = ['pacjent_id', 'lekarz_id', 'data', 'godzina']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Brak wymaganego pola: {field}'}), 400
        
        # Konwersja daty i godziny
        try:
            data_wizyty = datetime.strptime(data['data'], '%Y-%m-%d').date()
            godzina_wizyty = datetime.strptime(data['godzina'], '%H:%M').time()
        except ValueError as e:
            return jsonify({'error': 'Nieprawidłowy format daty lub godziny'}), 400
        
        # Sprawdzenie czy pacjent istnieje
        pacjent = Pacjent.query.get(data['pacjent_id'])
        if not pacjent:
            return jsonify({'error': 'Podany pacjent nie istnieje'}), 404
        
        # Sprawdzenie czy lekarz istnieje
        lekarz = Lekarz.query.get(data['lekarz_id'])
        if not lekarz:
            return jsonify({'error': 'Podany lekarz nie istnieje'}), 404
        
        # Sprawdzenie czy data wizyty nie jest z przeszłości
        if data_wizyty < datetime.now().date() or \
           (data_wizyty == datetime.now().date() and godzina_wizyty < datetime.now().time()):
            return jsonify({'error': 'Nie można umówić wizyty w przeszłości'}), 400
        
        # Sprawdzenie czy lekarz ma już wizytę w tym terminie
        existing_termin = Termin.query.join(Wizyta).filter(
            Termin.lekarz_id == data['lekarz_id'],
            Termin.data == data_wizyty,
            Termin.godzina_od <= godzina_wizyty,
            Termin.godzina_do > godzina_wizyty,
            Wizyta.status != 'ANULOWANA'
        ).first()
        
        if existing_termin:
            return jsonify({'error': 'Lekarz ma już zaplanowaną wizytę w tym terminie'}), 400
        
        # Tworzenie nowego terminu
        czas_trwania = timedelta(minutes=30)  # Domyślny czas trwania wizyty
        
        # Jeśli podano usługi, oblicz łączny czas trwania
        if 'uslugi' in data and isinstance(data['uslugi'], list) and len(data['uslugi']) > 0:
            uslugi = Usluga.query.filter(Usluga.id.in_(data['uslugi'])).all()
            if uslugi:
                # Załóżmy, że każda usługa trwa 30 minut, chyba że ma określony czas
                czas_trwania = timedelta(minutes=sum(usluga.czas_trwania or 30 for usluga in uslugi))
        
        godzina_zakonczenia = (datetime.combine(datetime.min, godzina_wizyty) + czas_trwania).time()
        
        # Tworzenie nowego terminu
        nowy_termin = Termin(
            data=data_wizyty,
            godzina_od=godzina_wizyty,
            godzina_do=godzina_zakonczenia,
            lekarz_id=data['lekarz_id'],
            dostepny=False
        )
        db.session.add(nowy_termin)
        db.session.flush()  # Pobierz ID nowego terminu
        
        # Tworzenie nowej wizyty
        nowa_wizyta = Wizyta(
            pacjent_id=data['pacjent_id'],
            lekarz_id=data['lekarz_id'],
            termin_id=nowy_termin.id,
            status='ZAPLANOWANA',
            data_utworzenia=datetime.utcnow(),
            data_modyfikacji=datetime.utcnow()
        )
        db.session.add(nowa_wizyta)
        db.session.flush()  # Pobierz ID nowej wizyty
        
        # Dodawanie usług do wizyty
        if 'uslugi' in data and isinstance(data['uslugi'], list):
            for usluga_id in data['uslugi']:
                usluga = Usluga.query.get(usluga_id)
                if usluga:
                    wizyta_usluga = WizytaUsluga(
                        wizyta_id=nowa_wizyta.id,
                        usluga_id=usluga_id,
                        ilosc=1
                    )
                    db.session.add(wizyta_usluga)
        
        # Zatwierdzenie zmian w bazie danych
        db.session.commit()
        
        return jsonify({
            'message': 'Wizyta została umówiona pomyślnie',
            'wizyta_id': nowa_wizyta.id,
            'termin_id': nowy_termin.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podczas tworzenia wizyty: {str(e)}')
        return jsonify({'error': 'Wystąpił błąd podczas przetwarzania żądania'}), 500