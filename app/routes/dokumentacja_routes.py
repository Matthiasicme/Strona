from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db
from models.pacjent import Pacjent
from models.dokumentacja import DiagramDentystyczny, Podsumowanie, Recepta, ReceptaLek
from models.wizyta import Wizyta
from models.admin import LogSystemowy
from utils.helpers import handle_error_response, role_required
from datetime import datetime

dokumentacja_bp = Blueprint('dokumentacja', __name__)

@dokumentacja_bp.route('/diagram/<int:pacjent_id>', methods=['GET'])
@jwt_required()
def get_diagram_dentystyczny(pacjent_id):
    """
    Pobieranie diagramu dentystycznego pacjenta
    ---
    tags:
      - Dokumentacja medyczna
    security:
      - jwt: []
    parameters:
      - name: pacjent_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Diagram dentystyczny pacjenta
      404:
        description: Pacjent nie istnieje
      403:
        description: Brak uprawnień do wyświetlenia diagramu
    """
    identity = get_jwt_identity()
    user_id = identity['id']
    role = identity['role']
    
    # Sprawdzenie czy pacjent istnieje
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    # Sprawdzenie uprawnień
    if role == 'pacjent' and user_id != pacjent_id:
        return handle_error_response(403, "Brak uprawnień do wyświetlenia diagramu")
    
    # Pobranie diagramu dentystycznego pacjenta
    diagram = DiagramDentystyczny.query.filter_by(pacjent_id=pacjent_id).all()
    
    # Przygotowanie odpowiedzi
    result = [zab.to_dict() for zab in diagram]
    
    # Jeśli diagram jest pusty, zwróć standardową strukturę
    if not result:
        return jsonify({
            'status': 'success',
            'message': 'Brak danych diagramu dentystycznego dla pacjenta',
            'pacjent_id': pacjent_id,
            'diagram': []
        }), 200
    
    return jsonify({
        'status': 'success',
        'pacjent_id': pacjent_id,
        'diagram': result
    }), 200


@dokumentacja_bp.route('/diagram/<int:pacjent_id>/zab/<int:numer_zeba>', methods=['PUT'])
@jwt_required()
@role_required('lekarz')
def update_zab(pacjent_id, numer_zeba):
    """
    Aktualizacja stanu zęba w diagramie dentystycznym
    ---
    tags:
      - Dokumentacja medyczna
    security:
      - jwt: []
    parameters:
      - name: pacjent_id
        in: path
        required: true
        schema:
          type: integer
      - name: numer_zeba
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
              status:
                type: string
              opis:
                type: string
    responses:
      200:
        description: Stan zęba został zaktualizowany
      404:
        description: Pacjent nie istnieje
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    # Sprawdzenie czy pacjent istnieje
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    # Sprawdzenie czy numer zęba jest prawidłowy (11-48)
    if numer_zeba < 11 or numer_zeba > 48:
        return handle_error_response(400, "Nieprawidłowy numer zęba. Zakres: 11-48")
    
    data = request.get_json()
    
    if not data or 'status' not in data:
        return handle_error_response(400, "Brak wymaganego pola: status")
    
    status = data['status']
    opis = data.get('opis')
    
    try:
        # Sprawdzenie czy wpis dla zęba już istnieje
        zab = DiagramDentystyczny.query.filter_by(pacjent_id=pacjent_id, numer_zeba=numer_zeba).first()
        
        if zab:
            # Aktualizacja istniejącego wpisu
            zab.status = status
            zab.opis = opis
            zab.data_modyfikacji = datetime.utcnow()
            message = "Stan zęba został zaktualizowany"
        else:
            # Utworzenie nowego wpisu
            zab = DiagramDentystyczny(
                pacjent_id=pacjent_id,
                numer_zeba=numer_zeba,
                status=status,
                opis=opis
            )
            db.session.add(zab)
            message = "Stan zęba został dodany do diagramu"
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="AKTUALIZACJA_DIAGRAMU_DENTYSTYCZNEGO",
            opis=f"Zaktualizowano stan zęba {numer_zeba} dla pacjenta ID: {pacjent_id}",
            uzytkownik_id=lekarz_id,
            rola_uzytkownika="lekarz",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': message,
            'zab': zab.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas aktualizacji diagramu: {str(e)}")


@dokumentacja_bp.route('/podsumowanie/<int:wizyta_id>', methods=['POST'])
@jwt_required()
@role_required('lekarz')
def create_podsumowanie(wizyta_id):
    """
    Dodanie podsumowania wizyty
    ---
    tags:
      - Dokumentacja medyczna
    security:
      - jwt: []
    parameters:
      - name: wizyta_id
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
              szczegoly:
                type: string
              zalecenia:
                type: string
              nastepna_wizyta_zalecana:
                type: boolean
    responses:
      201:
        description: Podsumowanie wizyty zostało dodane
      404:
        description: Wizyta nie istnieje
      403:
        description: Brak uprawnień do dodania podsumowania
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    # Pobranie wizyty
    wizyta = Wizyta.query.get(wizyta_id)
    if not wizyta:
        return handle_error_response(404, "Wizyta nie istnieje")
    
    # Sprawdzenie uprawnień
    if wizyta.lekarz_id != lekarz_id:
        return handle_error_response(403, "Brak uprawnień do dodania podsumowania")
    
    # Sprawdzenie czy wizyta może mieć podsumowanie
    if wizyta.status not in ['POTWIERDZONA', 'ZAKOŃCZONA']:
        return handle_error_response(400, f"Nie można dodać podsumowania do wizyty o statusie {wizyta.status}")
    
    # Sprawdzenie czy podsumowanie już istnieje
    istniejace_podsumowanie = Podsumowanie.query.filter_by(wizyta_id=wizyta_id).first()
    if istniejace_podsumowanie:
        return handle_error_response(400, "Podsumowanie dla tej wizyty już istnieje. Użyj metody PUT, aby zaktualizować.")
    
    data = request.get_json()
    
    if not data or 'szczegoly' not in data:
        return handle_error_response(400, "Brak wymaganego pola: szczegoly")
    
    szczegoly = data['szczegoly']
    zalecenia = data.get('zalecenia')
    nastepna_wizyta_zalecana = data.get('nastepna_wizyta_zalecana', False)
    
    try:
        # Utworzenie nowego podsumowania
        podsumowanie = Podsumowanie(
            wizyta_id=wizyta_id,
            szczegoly=szczegoly,
            zalecenia=zalecenia,
            nastepna_wizyta_zalecana=nastepna_wizyta_zalecana
        )
        db.session.add(podsumowanie)
        
        # Aktualizacja statusu wizyty
        wizyta.status = 'ZAKOŃCZONA'
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="DODANIE_PODSUMOWANIA_WIZYTY",
            opis=f"Dodano podsumowanie wizyty ID: {wizyta_id}",
            uzytkownik_id=lekarz_id,
            rola_uzytkownika="lekarz",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Podsumowanie wizyty zostało dodane pomyślnie',
            'podsumowanie': podsumowanie.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas dodawania podsumowania: {str(e)}")


@dokumentacja_bp.route('/podsumowanie/<int:wizyta_id>', methods=['GET'])
@jwt_required()
def get_podsumowanie(wizyta_id):
    """
    Pobieranie podsumowania wizyty
    ---
    tags:
      - Dokumentacja medyczna
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
        description: Podsumowanie wizyty
      404:
        description: Wizyta lub podsumowanie nie istnieje
      403:
        description: Brak uprawnień do wyświetlenia podsumowania
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
        return handle_error_response(403, "Brak uprawnień do wyświetlenia podsumowania")
    elif role == 'lekarz' and wizyta.lekarz_id != user_id:
        return handle_error_response(403, "Brak uprawnień do wyświetlenia podsumowania")
    
    # Pobranie podsumowania
    podsumowanie = Podsumowanie.query.filter_by(wizyta_id=wizyta_id).first()
    if not podsumowanie:
        return handle_error_response(404, "Podsumowanie dla tej wizyty nie istnieje")
    
    return jsonify({
        'status': 'success',
        'podsumowanie': podsumowanie.to_dict()
    }), 200


@dokumentacja_bp.route('/recepta/<int:wizyta_id>', methods=['POST'])
@jwt_required()
@role_required('lekarz')
def create_recepta(wizyta_id):
    """
    Wystawienie e-Recepty
    ---
    tags:
      - Dokumentacja medyczna
    security:
      - jwt: []
    parameters:
      - name: wizyta_id
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
              opis:
                type: string
              leki:
                type: array
                items:
                  type: object
                  properties:
                    nazwa:
                      type: string
                    dawkowanie:
                      type: string
                    ilosc:
                      type: integer
                    refundacja:
                      type: boolean
    responses:
      201:
        description: E-Recepta została wystawiona
      404:
        description: Wizyta nie istnieje
      403:
        description: Brak uprawnień do wystawienia recepty
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    # Pobranie wizyty
    wizyta = Wizyta.query.get(wizyta_id)
    if not wizyta:
        return handle_error_response(404, "Wizyta nie istnieje")
    
    # Sprawdzenie uprawnień
    if wizyta.lekarz_id != lekarz_id:
        return handle_error_response(403, "Brak uprawnień do wystawienia recepty")
    
    data = request.get_json()
    
    if not data or 'opis' not in data or 'leki' not in data or not isinstance(data['leki'], list):
        return handle_error_response(400, "Brak wymaganych pól lub nieprawidłowy format danych")
    
    opis = data['opis']
    leki_data = data['leki']
    
    if not leki_data:
        return handle_error_response(400, "Lista leków nie może być pusta")
    
    try:
        # Utworzenie nowej recepty
        recepta = Recepta(
            wizyta_id=wizyta_id,
            opis=opis,
            status='UTWORZONA'
        )
        db.session.add(recepta)
        db.session.flush()  # Generowanie ID recepty
        
        # Dodanie leków do recepty
        for lek_data in leki_data:
            if 'nazwa' not in lek_data or 'dawkowanie' not in lek_data or 'ilosc' not in lek_data:
                continue
            
            lek = ReceptaLek(
                recepta_id=recepta.id,
                nazwa=lek_data['nazwa'],
                dawkowanie=lek_data['dawkowanie'],
                ilosc=lek_data['ilosc'],
                refundacja=lek_data.get('refundacja', False)
            )
            db.session.add(lek)
        
        # TODO: Integracja z systemem P1 (e-Recepta)
        # W prawdziwej implementacji tutaj byłoby wywołanie API systemu P1
        
        # Przykładowe dane, które byłyby otrzymane z systemu P1
        recepta.kod_recepty = f"REC{wizyta_id}{datetime.now().strftime('%Y%m%d%H%M')}"
        recepta.identyfikator_p1 = f"P1_{recepta.kod_recepty}"
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="WYSTAWIENIE_RECEPTY",
            opis=f"Wystawiono receptę dla wizyty ID: {wizyta_id}",
            uzytkownik_id=lekarz_id,
            rola_uzytkownika="lekarz",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'E-Recepta została wystawiona pomyślnie',
            'recepta': recepta.to_dict(include_relations=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas wystawiania recepty: {str(e)}")


@dokumentacja_bp.route('/recepty/<int:pacjent_id>', methods=['GET'])
@jwt_required()
def get_recepty_pacjenta(pacjent_id):
    """
    Pobieranie recept pacjenta
    ---
    tags:
      - Dokumentacja medyczna
    security:
      - jwt: []
    parameters:
      - name: pacjent_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Lista recept pacjenta
      404:
        description: Pacjent nie istnieje
      403:
        description: Brak uprawnień do wyświetlenia recept
    """
    identity = get_jwt_identity()
    user_id = identity['id']
    role = identity['role']
    
    # Sprawdzenie czy pacjent istnieje
    pacjent = Pacjent.query.get(pacjent_id)
    if not pacjent:
        return handle_error_response(404, "Pacjent nie istnieje")
    
    # Sprawdzenie uprawnień
    if role == 'pacjent' and user_id != pacjent_id:
        return handle_error_response(403, "Brak uprawnień do wyświetlenia recept")
    
    # Pobranie recept pacjenta
    recepty = db.session.query(Recepta).join(Wizyta).filter(Wizyta.pacjent_id == pacjent_id).all()
    
    # Przygotowanie odpowiedzi
    result = []
    for recepta in recepty:
        recepta_data = recepta.to_dict(include_relations=True)
        result.append(recepta_data)
    
    return jsonify({
        'status': 'success',
        'count': len(result),
        'recepty': result
    }), 200