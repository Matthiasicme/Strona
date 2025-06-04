"""
Utility functions for sending notifications related to appointments.
"""
from datetime import datetime
from flask import current_app
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import db, Wizyta, Termin, Pacjent, Lekarz, Platnosc, Usluga, WizytaUsluga, LogSystemowy, Czekajacy, CzekajacyUsluga
from notification_service import NotificationService

def send_appointment_confirmation(appointment_id: int) -> None:
    """
    Send confirmation notification for a new appointment.
    
    Args:
        appointment_id: ID of the appointment
    """
    try:
        notification_service = NotificationService(db.session)
        
        # Get appointment details
        appointment = db.session.query(Wizyta).options(
            db.joinedload(Wizyta.termin),
            db.joinedload(Wizyta.lekarz),
            db.joinedload(Wizyta.pacjent)
        ).get(appointment_id)
        
        if not appointment or not appointment.termin or not appointment.pacjent or not appointment.lekarz:
            current_app.logger.error(f"Cannot send confirmation: Incomplete appointment data for ID {appointment_id}")
            return
        
        # Prepare context for the email template
        context = {
            'patient_name': f"{appointment.pacjent.imie} {appointment.pacjent.nazwisko}",
            'doctor_name': f"{appointment.lekarz.tytul} {appointment.lekarz.imie} {appointment.lekarz.nazwisko}",
            'appointment_date': appointment.termin.data.strftime('%Y-%m-%d'),
            'appointment_time': appointment.termin.godzina_od.strftime('%H:%M'),
            'clinic_name': current_app.config.get('CLINIC_NAME', 'Przychodnia Lekarska'),
            'clinic_phone': current_app.config.get('CLINIC_PHONE', ''),
            'clinic_email': current_app.config.get('CLINIC_EMAIL', '')
        }
        
        # Send the notification
        notification_service.send_notification(
            recipient_email=appointment.pacjent.email,
            recipient_phone=appointment.pacjent.telefon,
            template_name='appointment_confirmation',
            context=context
        )
        
        current_app.logger.info(f"Appointment confirmation sent for appointment ID: {appointment_id}")
        
    except Exception as e:
        current_app.logger.error(f"Error sending appointment confirmation: {str(e)}", exc_info=True)

def send_appointment_cancellation(appointment_id: int, reason: str = None) -> None:
    """
    Send cancellation notification for an appointment.
    
    Args:
        appointment_id: ID of the appointment
        reason: Optional reason for cancellation
    """
    try:
        notification_service = NotificationService(db.session)
        
        # Get appointment details
        appointment = db.session.query(Wizyta).options(
            db.joinedload(Wizyta.termin),
            db.joinedload(Wizyta.lekarz),
            db.joinedload(Wizyta.pacjent)
        ).get(appointment_id)
        
        if not appointment or not appointment.termin or not appointment.pacjent or not appointment.lekarz:
            current_app.logger.error(f"Cannot send cancellation: Incomplete appointment data for ID {appointment_id}")
            return
        
        # Prepare context for the email template
        context = {
            'patient_name': f"{appointment.pacjent.imie} {appointment.pacjent.nazwisko}",
            'doctor_name': f"{appointment.lekarz.tytul} {appointment.lekarz.imie} {appointment.lekarz.nazwisko}",
            'appointment_date': appointment.termin.data.strftime('%Y-%m-%d'),
            'appointment_time': appointment.termin.godzina_od.strftime('%H:%M'),
            'cancellation_reason': reason or 'Nie podano powodu',
            'clinic_name': current_app.config.get('CLINIC_NAME', 'Przychodnia Lekarska'),
            'clinic_phone': current_app.config.get('CLINIC_PHONE', ''),
            'clinic_email': current_app.config.get('CLINIC_EMAIL', '')
        }
        
        # Send the notification
        notification_service.send_notification(
            recipient_email=appointment.pacjent.email,
            recipient_phone=appointment.pacjent.telefon,
            template_name='appointment_cancellation',
            context=context
        )
        
        current_app.logger.info(f"Appointment cancellation sent for appointment ID: {appointment_id}")
        
    except Exception as e:
        current_app.logger.error(f"Error sending appointment cancellation: {str(e)}", exc_info=True)

def send_appointment_reminder(appointment_id: int) -> None:
    """
    Send reminder notification for an upcoming appointment.
    
    Args:
        appointment_id: ID of the appointment
    """
    try:
        notification_service = NotificationService(db.session)
        
        # Get appointment details
        appointment = db.session.query(Wizyta).options(
            db.joinedload(Wizyta.termin),
            db.joinedload(Wizyta.lekarz),
            db.joinedload(Wizyta.pacjent)
        ).get(appointment_id)
        
        if not appointment or not appointment.termin or not appointment.pacjent or not appointment.lekarz:
            current_app.logger.error(f"Cannot send reminder: Incomplete appointment data for ID {appointment_id}")
            return
        
        # Prepare context for the email template
        context = {
            'patient_name': f"{appointment.pacjent.imie} {appointment.pacjent.nazwisko}",
            'doctor_name': f"{appointment.lekarz.tytul} {appointment.lekarz.imie} {appointment.lekarz.nazwisko}",
            'appointment_date': appointment.termin.data.strftime('%Y-%m-%d'),
            'appointment_time': appointment.termin.godzina_od.strftime('%H:%M'),
            'doctor_specialization': appointment.lekarz.specjalizacja or '',
            'clinic_name': current_app.config.get('CLINIC_NAME', 'Przychodnia Lekarska'),
            'clinic_address': current_app.config.get('CLINIC_ADDRESS', ''),
            'clinic_phone': current_app.config.get('CLINIC_PHONE', ''),
            'clinic_email': current_app.config.get('CLINIC_EMAIL', '')
        }
        
        # Send the notification
        notification_service.send_notification(
            recipient_email=appointment.pacjent.email,
            recipient_phone=appointment.pacjent.telefon,
            template_name='appointment_reminder',
            context=context
        )
        
        current_app.logger.info(f"Appointment reminder sent for appointment ID: {appointment_id}")
        
    except Exception as e:
        current_app.logger.error(f"Error sending appointment reminder: {str(e)}", exc_info=True)
