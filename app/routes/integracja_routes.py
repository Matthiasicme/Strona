from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db
from models.wizyta import Termin, Wizyta
from models.admin import LogSystemowy
from models.lekarz import Lekarz
from models.pacjent import Pacjent
from models.dokumentacja import Recepta
from utils.helpers import handle_error_response, role_required
from datetime import datetime, timedelta
import requests
import json
import uuid

integracja_bp = Blueprint('integracja', __name__)

@integracja_bp.route('/znanylekarz/sync', methods=['POST'])
@jwt_required()
@role_required('admin')
def sync_znanylekarz():
    """
    Synchronizacja terminów z ZnanyLekarz
    ---
    tags:
      - Integracje
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              lekarz_id:
                type: integer
              data_od:
                type: string
                format: date
              data_do:
                type: string
                format: date
    responses:
      200:
        description: Synchronizacja z ZnanyLekarz zakończona pomyślnie
      400:
        description: Błędne dane
    """
    identity = get_jwt_identity()
    admin_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'lekarz_id' not in data:
        return handle_error_response(400, "Brak wymaganego pola: lekarz_id")
    
    lekarz_id = data['lekarz_id']
    
    # Przetworzenie dat
    try:
        data_od = datetime.strptime(data.get('data_od', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
        data_do = datetime.strptime(data.get('data_do', (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')), '%Y-%m-%d').date()
    except ValueError:
        return handle_error_response(400, "Niepoprawny format daty. Użyj formatu YYYY-MM-DD")
    
    # Pobranie lekarza
    lekarz = Lekarz.query.get(lekarz_id)
    if not lekarz:
        return handle_error_response(404, "Lekarz nie istnieje")
    
    try:
        # W rzeczywistym API wykonalibyśmy zapytanie do ZnanyLekarz
        # Tutaj symulujemy odpowiedź z API
        
        # Symulacja opóźnienia zapytania API
        # import time
        # time.sleep(1)
        
        # Przykładowe dane, które byłyby otrzymane z API ZnanyLekarz
        known_doctor_slots = [
            {
                "id": "zl_" + str(uuid.uuid4()),
                "date": "2025-04-29",
                "start_time": "10:00",
                "end_time": "10:30",
                "status": "available"
            },
            {
                "id": "zl_" + str(uuid.uuid4()),
                "date": "2025-04-29",
                "start_time": "10:30",
                "end_time": "11:00",
                "status": "booked"
            },
            {
                "id": "zl_" + str(uuid.uuid4()),
                "date": "2025-04-30",
                "start_time": "09:00",
                "end_time": "09:30",
                "status": "available"
            }
        ]
        
        # Pobranie terminów lekarza z naszej bazy
        local_terms = Termin.query.filter(
            Termin.lekarz_id == lekarz_id,
            Termin.data >= data_od,
            Termin.data <= data_do
        ).all()
        
        # Mapowanie lokalnych terminów
        local_terms_map = {}
        for term in local_terms:
            key = f"{term.data.strftime('%Y-%m-%d')}_{term.godzina_od.strftime('%H:%M')}_{term.godzina_do.strftime('%H:%M')}"
            local_terms_map[key] = term
        
        # Synchronizacja terminów
        synced_count = 0
        conflict_count = 0
        
        for slot in known_doctor_slots:
            slot_date = datetime.strptime(slot['date'], '%Y-%m-%d').date()
            slot_start = datetime.strptime(slot['start_time'], '%H:%M').time()
            slot_end = datetime.strptime(slot['end_time'], '%H:%M').time()
            
            key = f"{slot['date']}_{slot['start_time']}_{slot['end_time']}"
            
            if key in local_terms_map:
                # Termin istnieje w obu systemach
                term = local_terms_map[key]
                
                # Synchronizacja statusu
                if slot['status'] == 'available' and not term.dostepny:
                    # Sprawdzenie czy termin nie jest zajęty przez wizytę
                    if not Wizyta.query.filter_by(termin_id=term.id).first():
                        term.dostepny = True
                        synced_count += 1
                    else:
                        conflict_count += 1
                elif slot['status'] == 'booked' and term.dostepny:
                    term.dostepny = False
                    synced_count += 1
            else:
                # Termin istnieje tylko w ZnanyLekarz, dodajemy go do naszej bazy
                new_term = Termin(
                    data=slot_date,
                    godzina_od=slot_start,
                    godzina_do=slot_end,
                    dostepny=slot['status'] == 'available',
                    lekarz_id=lekarz_id
                )
                db.session.add(new_term)
                synced_count += 1
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="SYNCHRONIZACJA_ZNANYLEKARZ",
            opis=f"Zsynchronizowano terminy z ZnanyLekarz dla lekarza ID: {lekarz_id}",
            uzytkownik_id=admin_id,
            rola_uzytkownika="admin",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Synchronizacja z ZnanyLekarz zakończona pomyślnie',
            'synced_count': synced_count,
            'conflict_count': conflict_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas synchronizacji z ZnanyLekarz: {str(e)}")


@integracja_bp.route('/nfz/ewus', methods=['POST'])
@jwt_required()
@role_required('lekarz', 'admin')
def verify_ewus():
    """
    Weryfikacja ubezpieczenia pacjenta w systemie eWUŚ
    ---
    tags:
      - Integracje
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              pacjent_id:
                type: integer
              pesel:
                type: string
    responses:
      200:
        description: Weryfikacja eWUŚ zakończona pomyślnie
      400:
        description: Błędne dane
    """
    identity = get_jwt_identity()
    user_id = identity['id']
    role = identity['role']
    
    data = request.get_json()
    
    if not data or ('pacjent_id' not in data and 'pesel' not in data):
        return handle_error_response(400, "Brak wymaganych pól: pacjent_id lub pesel")
    
    try:
        # Pobranie danych pacjenta
        pesel = data.get('pesel')
        pacjent_id = data.get('pacjent_id')
        
        if pacjent_id:

            pacjent = Pacjent.query.get(pacjent_id)
            if not pacjent:
                return handle_error_response(404, "Pacjent nie istnieje")
            
            pesel = pacjent.pesel
        
        if not pesel:
            return handle_error_response(400, "Brak numeru PESEL do weryfikacji")
        
        # W rzeczywistym API wykonalibyśmy zapytanie do eWUŚ
        # Tutaj symulujemy odpowiedź z API
        
        # Przykładowe dane, które byłyby otrzymane z API eWUŚ
        # Dla testów - jeśli PESEL kończy się na 1, to ubezpieczony, jeśli 2 to nieubezpieczony, w przeciwnym razie błąd
        last_digit = pesel[-1]
        
        if last_digit == '1':
            status = 'UBEZPIECZONY'
            message = 'Pacjent jest ubezpieczony'
        elif last_digit == '2':
            status = 'NIEUBEZPIECZONY'
            message = 'Pacjent nie jest ubezpieczony'
        else:
            status = 'BŁĄD'
            message = 'Nie można zweryfikować statusu ubezpieczenia'
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="WERYFIKACJA_EWUS",
            opis=f"Zweryfikowano status ubezpieczenia dla PESEL: {pesel[:6]}******, Status: {status}",
            uzytkownik_id=user_id,
            rola_uzytkownika=role,
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': message,
            'ewus_status': status,
            'pesel_masked': pesel[:6] + '******',
            'data_weryfikacji': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas weryfikacji eWUŚ: {str(e)}")


@integracja_bp.route('/nfz/p1/recepta', methods=['POST'])
@jwt_required()
@role_required('lekarz')
def send_p1_recepta():
    """
    Wysłanie e-Recepty do systemu P1
    ---
    tags:
      - Integracje
    security:
      - jwt: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              recepta_id:
                type: integer
    responses:
      200:
        description: E-Recepta została wysłana do systemu P1
      400:
        description: Błędne dane
      404:
        description: Recepta nie istnieje
    """
    identity = get_jwt_identity()
    lekarz_id = identity['id']
    
    data = request.get_json()
    
    if not data or 'recepta_id' not in data:
        return handle_error_response(400, "Brak wymaganego pola: recepta_id")
    
    recepta_id = data['recepta_id']

    recepta = Recepta.query.get(recepta_id)
    if not recepta:
        return handle_error_response(404, "Recepta nie istnieje")
    
    # Pobranie wizyty i sprawdzenie czy lekarz ma do niej dostęp
    wizyta = recepta.wizyta
    if not wizyta:
        return handle_error_response(404, "Brak powiązanej wizyty")
    
    if wizyta.lekarz_id != lekarz_id:
        return handle_error_response(403, "Brak uprawnień do wysłania recepty")
    
    try:
        # W rzeczywistym API wykonalibyśmy zapytanie do systemu P1
        # Tutaj symulujemy odpowiedź z API
        
        # Przykładowe dane, które byłyby otrzymane z API P1
        p1_response = {
            "status": "OK",
            "message": "Recepta została wysłana do systemu P1",
            "kod_recepty": f"REC{recepta_id}{datetime.now().strftime('%Y%m%d%H%M')}",
            "identyfikator_p1": f"P1_{recepta_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        }
        
        # Aktualizacja danych recepty
        recepta.kod_recepty = p1_response['kod_recepty']
        recepta.identyfikator_p1 = p1_response['identyfikator_p1']
        recepta.status = 'WYSTAWIONA'
        
        # Logowanie akcji
        log = LogSystemowy(
            typ="INFO",
            akcja="WYSLANIE_RECEPTY_P1",
            opis=f"Wysłano e-Receptę ID: {recepta_id} do systemu P1",
            uzytkownik_id=lekarz_id,
            rola_uzytkownika="lekarz",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        
        # Zatwierdzenie zmian
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'E-Recepta została wysłana do systemu P1',
            'recepta': recepta.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas wysyłania e-Recepty do systemu P1: {str(e)}")


@integracja_bp.route('/znanylekarz/webhook', methods=['POST'])
def znanylekarz_webhook():
    """
    Webhook dla powiadomień z ZnanyLekarz
    ---
    tags:
      - Integracje
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              event_type:
                type: string
              slot_id:
                type: string
              status:
                type: string
              patient:
                type: object
              doctor_id:
                type: string
    responses:
      200:
        description: Webhook przetworzony pomyślnie
    """
    data = request.get_json()
    
    if not data or 'event_type' not in data:
        return handle_error_response(400, "Brak wymaganego pola: event_type")
    
    event_type = data['event_type']
    
    try:
        # Przetwarzanie różnych typów zdarzeń z ZnanyLekarz
        if event_type == 'appointment_booked':
            # Obsługa rezerwacji wizyty
            # W rzeczywistej implementacji przetwarzalibyśmy dane i aktualizowali naszą bazę
            
            # Logowanie akcji
            log = LogSystemowy(
                typ="INFO",
                akcja="WEBHOOK_ZNANYLEKARZ",
                opis=f"Otrzymano webhook z ZnanyLekarz: {event_type}",
                ip_adres=request.remote_addr
            )
            db.session.add(log)
            
            # Zatwierdzenie zmian
            db.session.commit()
            
        elif event_type == 'appointment_canceled':
            # Obsługa anulowania wizyty
            # W rzeczywistej implementacji przetwarzalibyśmy dane i aktualizowali naszą bazę
            
            # Logowanie akcji
            log = LogSystemowy(
                typ="INFO",
                akcja="WEBHOOK_ZNANYLEKARZ",
                opis=f"Otrzymano webhook z ZnanyLekarz: {event_type}",
                ip_adres=request.remote_addr
            )
            db.session.add(log)
            
            # Zatwierdzenie zmian
            db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook przetworzony pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return handle_error_response(500, f"Wystąpił błąd podczas przetwarzania webhooka: {str(e)}")