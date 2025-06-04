from flask import Blueprint, request, jsonify, current_app, url_for, render_template_string, redirect
from flask_jwt_extended import (
    create_access_token, create_refresh_token, 
    jwt_required, get_jwt_identity, get_jwt
)
from datetime import datetime
from uuid import uuid4

from app import db
from models.pacjent import Pacjent
from models.lekarz import Lekarz
from models.admin import Administrator, LogSystemowy
from utils.validators import validate_email, validate_password
from utils.helpers import handle_error_response
from utils.email_service import send_verification_email, generate_verification_token, verify_token
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register/pacjent', methods=['POST'])
def register_pacjent():
    """
    Rejestracja pacjenta
    ---
    tags:
      - Autoryzacja
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
              email:
                type: string
              haslo:
                type: string
              telefon:
                type: string
    responses:
      201:
        description: Konto pacjenta utworzone pomyślnie
      400:
        description: Błędne dane lub adres email jest już używany
    """
    data = request.get_json()
    
    # Sprawdzenie czy wymagane pola są obecne
    required_fields = ['imie', 'nazwisko', 'email', 'haslo', 'telefon']
    for field in required_fields:
        if field not in data:
            return handle_error_response(400, f"Brak wymaganego pola: {field}")
    
    # Walidacja danych
    if not validate_email(data['email']):
        return handle_error_response(400, "Niepoprawny format adresu email")
    
    if not validate_password(data['haslo']):
        return handle_error_response(400, "Hasło nie spełnia wymagań bezpieczeństwa")
    
    # Sprawdzenie czy email już istnieje
    if Pacjent.query.filter_by(email=data['email']).first():
        return handle_error_response(400, "Adres email jest już używany")
    
    try:
        # Utworzenie nowego pacjenta
        nowy_pacjent = Pacjent(
            imie=data['imie'],
            nazwisko=data['nazwisko'],
            email=data['email'],
            haslo=data['haslo'],
            telefon=data['telefon']
        )
        
        # Dodanie opcjonalnych pól
        optional_fields = ['data_urodzenia', 'adres', 'kod_pocztowy', 'miasto', 'kraj', 'pesel']
        for field in optional_fields:
            if field in data:
                setattr(nowy_pacjent, field, data[field])
        
        # Zapisanie do bazy danych
        db.session.add(nowy_pacjent)
        db.session.commit()
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="REJESTRACJA_PACJENTA",
            opis=f"Zarejestrowano nowego pacjenta: {nowy_pacjent.email}",
            uzytkownik_id=nowy_pacjent.id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        # Generowanie tokenu weryfikacyjnego
        verification_token = generate_verification_token(nowy_pacjent.id)
        
        # Wysłanie emaila weryfikacyjnego
        email_sent = send_verification_email(
            recipient_email=nowy_pacjent.email,
            verification_token=verification_token,
            user_id=nowy_pacjent.id
        )
        
        if not email_sent:
            current_app.logger.error(f"Nie udało się wysłać emaila weryfikacyjnego do {nowy_pacjent.email}")
        
        return jsonify({
            'status': 'success',
            'message': 'Konto zostało utworzone pomyślnie. Sprawdź swoją skrzynkę email, aby zweryfikować konto.',
            'id': nowy_pacjent.id,
            'email_verification_sent': email_sent
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Błąd podczas rejestracji pacjenta: {str(e)}")
        return handle_error_response(500, f"Wystąpił błąd podczas rejestracji: {str(e)}")


@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    """
    Weryfikacja adresu email użytkownika
    ---
    tags:
      - Autoryzacja
    parameters:
      - name: token
        in: query
        required: true
        schema:
          type: string
      - name: user_id
        in: query
        required: true
        schema:
          type: string
    responses:
      200:
        description: Email został zweryfikowany pomyślnie
      400:
        description: Nieprawidłowy lub przedawniony token
    """
    token = request.args.get('token')
    user_id = request.args.get('user_id')
    
    if not token or not user_id:
        return handle_error_response(400, "Brak wymaganych parametrów: token i user_id")
    
    try:
        # Weryfikacja tokenu
        token_user_id = verify_token(token)
        
        if not token_user_id or str(token_user_id) != str(user_id):
            return handle_error_response(400, "Nieprawidłowy lub przedawniony token")
        
        # Znajdź użytkownika
        pacjent = Pacjent.query.get(user_id)
        if not pacjent:
            return handle_error_response(404, "Użytkownik nie istnieje")
        
        # Aktywuj konto
        pacjent.email_zweryfikowany = True
        db.session.commit()
        
        # Przekieruj na stronę sukcesu
        return redirect(f"{current_app.config['FRONTEND_URL']}/success?verified=true&email={pacjent.email}")
        
    except Exception as e:
        current_app.logger.error(f"Błąd podczas weryfikacji emaila: {str(e)}")
        return handle_error_response(400, "Wystąpił błąd podczas weryfikacji emaila")


@auth_bp.route('/register/lekarz', methods=['POST'])
def register_lekarz():
    """
    Rejestracja lekarza
    ---
    tags:
      - Autoryzacja
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
              email:
                type: string
              haslo:
                type: string
              telefon:
                type: string
              specjalizacja:
                type: string
    responses:
      201:
        description: Konto lekarza utworzone pomyślnie
      400:
        description: Błędne dane lub adres email jest już używany
    """
    data = request.get_json()
    
    # Sprawdzenie czy wymagane pola są obecne
    required_fields = ['imie', 'nazwisko', 'email', 'haslo', 'telefon', 'specjalizacja']
    for field in required_fields:
        if field not in data:
            return handle_error_response(400, f"Brak wymaganego pola: {field}")
    
    # Walidacja danych
    if not validate_email(data['email']):
        return handle_error_response(400, "Niepoprawny format adresu email")
    
    if not validate_password(data['haslo']):
        return handle_error_response(400, "Hasło nie spełnia wymagań bezpieczeństwa")
    
    # Sprawdzenie czy email już istnieje
    if Lekarz.query.filter_by(email=data['email']).first():
        return handle_error_response(400, "Adres email jest już używany")
    
    try:
        # Utworzenie nowego lekarza
        nowy_lekarz = Lekarz(
            imie=data['imie'],
            nazwisko=data['nazwisko'],
            email=data['email'],
            haslo=data['haslo'],
            telefon=data['telefon'],
            specjalizacja=data['specjalizacja']
        )
        
        # Dodanie opcjonalnych pól
        optional_fields = ['opis', 'numer_pwz', 'zdjecie_url']
        for field in optional_fields:
            if field in data:
                setattr(nowy_lekarz, field, data[field])
        
        # Zapisanie do bazy danych
        db.session.add(nowy_lekarz)
        db.session.commit()
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="REJESTRACJA_LEKARZA",
            opis=f"Zarejestrowano nowego lekarza: {nowy_lekarz.email}",
            uzytkownik_id=nowy_lekarz.id,
            rola_uzytkownika="lekarz",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Konto lekarza zostało utworzone pomyślnie.',
            'id': nowy_lekarz.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas rejestracji: {str(e)}")


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Logowanie użytkownika
    ---
    tags:
      - Autoryzacja
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              email:
                type: string
              haslo:
                type: string
              rola:
                type: string
                enum: [pacjent, lekarz, admin]
    responses:
      200:
        description: Zalogowano pomyślnie
      401:
        description: Błędne dane logowania
    """
    data = request.get_json()
    
    # Sprawdzenie czy wymagane pola są obecne
    if not data or 'email' not in data or 'haslo' not in data or 'rola' not in data:
        return handle_error_response(400, "Brak wymaganych pól: email, haslo, rola")
    
    email = data['email']
    haslo = data['haslo']
    rola = data['rola']
    
    if rola == 'pacjent':
        user = Pacjent.query.filter_by(email=email).first()
    elif rola == 'lekarz':
        user = Lekarz.query.filter_by(email=email).first()
    elif rola == 'admin':
        user = Administrator.query.filter_by(email=email).first()
    else:
        return handle_error_response(400, "Nieprawidłowa rola")
    
    # Sprawdzenie czy użytkownik istnieje i hasło jest poprawne
    if not user or not user.check_password(haslo):
        return handle_error_response(401, "Nieprawidłowy email lub hasło")
    
    # Sprawdzenie czy konto jest aktywne
    if not user.is_active():
        return handle_error_response(403, "Konto jest nieaktywne")
    
    # Aktualizacja ostatniego logowania dla admina
    if rola == 'admin':
        
        user.ostatnie_logowanie = datetime.utcnow()
        db.session.commit()
    
    # Logowanie akcji
    log = LogSystemowy(
        typ="INFO",
        akcja="LOGOWANIE",
        opis=f"Zalogowano użytkownika: {user.email}",
        uzytkownik_id=user.id,
        rola_uzytkownika=rola,
        ip_adres=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    # Generowanie tokenów JWT
    tokens = user.get_tokens()
    
    # Zwrócenie odpowiedzi
    return jsonify({
        'status': 'success',
        'message': 'Zalogowano pomyślnie',
        'user': {
            'id': user.id,
            'imie': user.imie,
            'nazwisko': user.nazwisko,
            'email': user.email,
            'rola': rola
        },
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token']
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Odświeżenie tokenu JWT
    ---
    tags:
      - Autoryzacja
    security:
      - jwt_refresh: []
    responses:
      200:
        description: Token odświeżony pomyślnie
      401:
        description: Nieprawidłowy token odświeżający
    """
    identity = get_jwt_identity()
    
    if not identity or 'id' not in identity or 'role' not in identity:
        return handle_error_response(401, "Nieprawidłowy token")
    
    user_id = identity['id']
    role = identity['role']
    
    if role == 'pacjent':
        user = Pacjent.query.get(user_id)
    elif role == 'lekarz':
        user = Lekarz.query.get(user_id)
    elif role == 'admin':
        user = Administrator.query.get(user_id)
    else:
        return handle_error_response(401, "Nieprawidłowa rola")
    
    if not user:
        return handle_error_response(401, "Użytkownik nie istnieje")
    
    # Sprawdzenie czy konto jest aktywne
    if not user.is_active():
        return handle_error_response(403, "Konto jest nieaktywne")
    
    # Generowanie nowego tokenu dostępu
    access_token = create_access_token(identity=identity)
    
    return jsonify({
        'status': 'success',
        'message': 'Token odświeżony pomyślnie',
        'access_token': access_token
    }), 200


@auth_bp.route('/reset-password/request', methods=['POST'])
def request_password_reset():
    """
    Żądanie resetu hasła
    ---
    tags:
      - Autoryzacja
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              email:
                type: string
              rola:
                type: string
                enum: [pacjent, lekarz, admin]
    responses:
      200:
        description: Link do resetu hasła został wysłany
      404:
        description: Użytkownik nie istnieje
    """
    data = request.get_json()
    
    if not data or 'email' not in data or 'rola' not in data:
        return handle_error_response(400, "Brak wymaganych pól: email, rola")
    
    email = data['email']
    rola = data['rola']
    
    if rola == 'pacjent':
        user = Pacjent.query.filter_by(email=email).first()
    elif rola == 'lekarz':
        user = Lekarz.query.filter_by(email=email).first()
    elif rola == 'admin':
        user = Administrator.query.filter_by(email=email).first()
    else:
        return handle_error_response(400, "Nieprawidłowa rola")
    
    if not user:
        return handle_error_response(404, "Użytkownik o podanym adresie email nie istnieje")
    
    # Generowanie tokenu resetu hasła
    
    reset_token = str(uuid4())
    
    # TODO: Zapis tokenu do bazy lub pamięci podręcznej
    # TODO: Wysłanie emaila z linkiem do resetu hasła
    
    # Logowanie akcji
    log = LogSystemowy(
        typ="INFO",
        akcja="RESET_HASLA_ZADANIE",
        opis=f"Żądanie resetu hasła dla: {user.email}",
        uzytkownik_id=user.id,
        rola_uzytkownika=rola,
        ip_adres=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Link do resetu hasła został wysłany na podany adres email'
    }), 200