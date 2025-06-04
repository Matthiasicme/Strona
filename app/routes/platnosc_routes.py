from flask import Blueprint, request, jsonify, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import uuid

from app import db
from models.platnosc import Platnosc, MetodaPlatnosci
from models.wizyta import Wizyta
from models.admin import LogSystemowy
from utils.helpers import handle_error_response, role_required

platnosc_bp = Blueprint('platnosc', __name__)

@platnosc_bp.route('/metody', methods=['GET'])
def get_metody_platnosci():
    """
    Pobieranie dostępnych metod płatności
    ---
    tags:
      - Płatności
    parameters:
      - name: aktywne
        in: query
        schema:
          type: boolean
    responses:
      200:
        description: Lista dostępnych metod płatności
    """
    # Pobranie parametrów z zapytania
    aktywne = request.args.get('aktywne', 'true').lower() == 'true'
    
    # Budowanie zapytania
    query = MetodaPlatnosci.query
    
    if aktywne:
        query = query.filter(MetodaPlatnosci.aktywna == True)
    
    # Wykonanie zapytania
    metody = query.all()
    
    # Przygotowanie odpowiedzi
    result = [metoda.to_dict() for metoda in metody]
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'metody_platnosci': result
    }), 200


@platnosc_bp.route('/<int:platnosc_id>', methods=['GET'])
@jwt_required()
def get_platnosc(platnosc_id):
    """
    Pobieranie szczegółów płatności
    ---
    tags:
      - Płatności
    security:
      - jwt: []
    parameters:
      - name: platnosc_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Szczegóły płatności
      404:
        description: Płatność nie istnieje
      403:
        description: Brak uprawnień do wyświetlenia płatności
    """
    identity = get_jwt_identity()
    user_id = identity['id']
    role = identity['role']
    
    # Pobranie płatności
    platnosc = Platnosc.query.get(platnosc_id)
    if not platnosc:
        return handle_error_response(404, "Płatność nie istnieje")
    
    # Pobranie powiązanej wizyty
    wizyta = Wizyta.query.filter_by(platnosc_id=platnosc_id).first()
    if not wizyta:
        return handle_error_response(404, "Brak powiązanej wizyty")
    
    # Sprawdzenie uprawnień
    if role == 'pacjent' and wizyta.pacjent_id != user_id:
        return handle_error_response(403, "Brak uprawnień do wyświetlenia płatności")
    elif role == 'lekarz' and wizyta.lekarz_id != user_id:
        return handle_error_response(403, "Brak uprawnień do wyświetlenia płatności")
    
    # Przygotowanie odpowiedzi
    platnosc_data = platnosc.to_dict(include_relations=True)
    
    return jsonify({
        'status': 'success',
        'platnosc': platnosc_data
    }), 200


@platnosc_bp.route('/<int:platnosc_id>/metoda', methods=['PUT'])
@jwt_required()
@role_required('pacjent')
def update_metoda_platnosci(platnosc_id):
    """
    Aktualizacja metody płatności
    ---
    tags:
      - Płatności
    security:
      - jwt: []
    parameters:
      - name: platnosc_id
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
              metoda_platnosci_id:
                type: integer
    responses:
      200:
        description: Metoda płatności została zaktualizowana
      404:
        description: Płatność lub metoda płatności nie istnieje
      403:
        description: Brak uprawnień do aktualizacji płatności
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'metoda_platnosci_id' not in data:
        return handle_error_response(400, "Brak wymaganego pola: metoda_platnosci_id")
    
    metoda_platnosci_id = data['metoda_platnosci_id']
    
    # Pobranie płatności
    platnosc = Platnosc.query.get(platnosc_id)
    if not platnosc:
        return handle_error_response(404, "Płatność nie istnieje")
    
    # Pobranie powiązanej wizyty
    wizyta = Wizyta.query.filter_by(platnosc_id=platnosc_id).first()
    if not wizyta:
        return handle_error_response(404, "Brak powiązanej wizyty")
    
    # Sprawdzenie uprawnień
    if wizyta.pacjent_id != pacjent_id:
        return handle_error_response(403, "Brak uprawnień do aktualizacji płatności")
    
    # Sprawdzenie czy metoda płatności istnieje i jest aktywna
    metoda = MetodaPlatnosci.query.filter_by(id=metoda_platnosci_id, aktywna=True).first()
    if not metoda:
        return handle_error_response(404, "Metoda płatności nie istnieje lub jest nieaktywna")
    
    # Sprawdzenie czy płatność można aktualizować
    if platnosc.status not in ['OCZEKUJĄCA', 'ANULOWANA']:
        return handle_error_response(400, f"Nie można aktualizować płatności o statusie {platnosc.status}")
    
    try:
        # Aktualizacja metody płatności
        platnosc.metoda_platnosci_id = metoda_platnosci_id
        
        # Resetowanie statusu, jeśli był anulowany
        if platnosc.status == 'ANULOWANA':
            platnosc.status = 'OCZEKUJĄCA'
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="AKTUALIZACJA_METODY_PLATNOSCI",
            opis=f"Zaktualizowano metodę płatności dla ID: {platnosc_id}",
            uzytkownik_id=pacjent_id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Metoda płatności została zaktualizowana pomyślnie',
            'platnosc': platnosc.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas aktualizacji metody płatności: {str(e)}")


@platnosc_bp.route('/<int:platnosc_id>/realizuj', methods=['POST'])
@jwt_required()
@role_required('pacjent')
def realizuj_platnosc(platnosc_id):
    """
    Realizacja płatności
    ---
    tags:
      - Płatności
    security:
      - jwt: []
    parameters:
      - name: platnosc_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Płatność została zrealizowana lub przygotowano link do płatności
      404:
        description: Płatność nie istnieje
      403:
        description: Brak uprawnień do realizacji płatności
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
    # Pobranie płatności
    platnosc = Platnosc.query.get(platnosc_id)
    if not platnosc:
        return handle_error_response(404, "Płatność nie istnieje")
    
    # Pobranie powiązanej wizyty
    wizyta = Wizyta.query.filter_by(platnosc_id=platnosc_id).first()
    if not wizyta:
        return handle_error_response(404, "Brak powiązanej wizyty")
    
    # Sprawdzenie uprawnień
    if wizyta.pacjent_id != pacjent_id:
        return handle_error_response(403, "Brak uprawnień do realizacji płatności")
    
    # Sprawdzenie czy płatność można realizować
    if platnosc.status not in ['OCZEKUJĄCA']:
        return handle_error_response(400, f"Nie można realizować płatności o statusie {platnosc.status}")
    
    # Sprawdzenie czy wybrano metodę płatności
    if not platnosc.metoda_platnosci_id:
        return handle_error_response(400, "Nie wybrano metody płatności")
    
    try:
        # Generowanie identyfikatora transakcji
        identyfikator_transakcji = str(uuid.uuid4())
        platnosc.identyfikator_transakcji = identyfikator_transakcji
        
        # Różna obsługa w zależności od metody płatności
        metoda = MetodaPlatnosci.query.get(platnosc.metoda_platnosci_id)
        
        if metoda.nazwa == 'Gotówka':
            # Dla płatności gotówką - oznaczenie do zapłaty w gabinecie
            platnosc.status = 'ZATWIERDZONA'
            platnosc.data_platnosci = datetime.utcnow()
            
            # Aktualizacja statusu wizyty
            wizyta.status = 'POTWIERDZONA'
            
            message = "Wybrano płatność gotówką. Prosimy o dokonanie płatności w gabinecie."
            url_platnosci = None
            
        else:
            # Dla płatności elektronicznych - generowanie linku do płatności
            # W rzeczywistej implementacji tutaj byłaby integracja z systemem płatności
            base_url = request.host_url.rstrip('/')
            url_platnosci = f"{base_url}/payment/process/{identyfikator_transakcji}"
            platnosc.url_platnosci = url_platnosci
            
            message = "Przygotowano link do płatności online. Prosimy o dokonanie płatności."
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="REALIZACJA_PLATNOSCI",
            opis=f"Realizacja płatności ID: {platnosc_id}, metoda: {metoda.nazwa}",
            uzytkownik_id=pacjent_id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': message,
            'url_platnosci': url_platnosci,
            'platnosc': platnosc.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas realizacji płatności: {str(e)}")


@platnosc_bp.route('/callback', methods=['POST'])
def payment_callback():
    """
    Callback od systemu płatności (webhook)
    ---
    tags:
      - Płatności
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              transaction_id:
                type: string
              status:
                type: string
              amount:
                type: string
    responses:
      200:
        description: Callback przetworzony pomyślnie
    """
    data = request.get_json()
    
    if not data or 'transaction_id' not in data or 'status' not in data:
        return handle_error_response(400, "Brak wymaganych pól: transaction_id, status")
    
    transaction_id = data['transaction_id']
    status = data['status']
    
    # Mapowanie statusów zewnętrznego systemu płatności na wewnętrzne statusy
    status_mapping = {
        'completed': 'ZATWIERDZONA',
        'pending': 'OCZEKUJĄCA',
        'failed': 'ODRZUCONA',
        'canceled': 'ANULOWANA'
    }
    
    internal_status = status_mapping.get(status.lower(), 'OCZEKUJĄCA')
    
    try:
        # Znalezienie płatności po identyfikatorze transakcji
        platnosc = Platnosc.query.filter_by(identyfikator_transakcji=transaction_id).first()
        if not platnosc:
            return handle_error_response(404, "Płatność nie istnieje")
        
        # Aktualizacja statusu płatności
        platnosc.status = internal_status
        
        if internal_status == 'ZATWIERDZONA':
            platnosc.data_platnosci = datetime.utcnow()
            
            # Aktualizacja statusu wizyty, jeśli płatność zatwierdzona
            wizyta = Wizyta.query.filter_by(platnosc_id=platnosc.id).first()
            if wizyta:
                wizyta.status = 'POTWIERDZONA'
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="CALLBACK_PLATNOSCI",
            opis=f"Otrzymano callback dla transakcji: {transaction_id}, status: {status}",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Callback przetworzony pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas przetwarzania callback: {str(e)}")


@platnosc_bp.route('/historia', methods=['GET'])
@jwt_required()
@role_required('pacjent')
def get_historia_platnosci():
    """
    Pobieranie historii płatności użytkownika
    ---
    tags:
      - Płatności
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
        description: Historia płatności użytkownika
    """
    identity = get_jwt_identity()
    pacjent_id = identity['id']
    
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
    query = db.session.query(Platnosc).join(Wizyta).filter(Wizyta.pacjent_id == pacjent_id)
    
    if status:
        query = query.filter(Platnosc.status == status)
    
    if data_od:
        query = query.filter(Platnosc.data_utworzenia >= datetime.combine(data_od, datetime.min.time()))
    
    if data_do:
        query = query.filter(Platnosc.data_utworzenia <= datetime.combine(data_do, datetime.max.time()))
    
    # Sortowanie wyników
    query = query.order_by(Platnosc.data_utworzenia.desc())
    
    # Wykonanie zapytania
    platnosci = query.all()
    
    # Przygotowanie odpowiedzi
    result = []
    for platnosc in platnosci:
        platnosc_data = platnosc.to_dict()
        
        # Dodanie informacji o wizycie
        wizyta = Wizyta.query.filter_by(platnosc_id=platnosc.id).first()
        if wizyta:
            platnosc_data['wizyta'] = {
                'id': wizyta.id,
                'status': wizyta.status,
                'data_utworzenia': wizyta.data_utworzenia.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        result.append(platnosc_data)
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'platnosci': result
    }), 200