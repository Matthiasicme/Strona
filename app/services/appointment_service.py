from datetime import datetime, timedelta, time, date
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum, auto
import logging
from flask import current_app, request
from sqlalchemy.orm import joinedload, contains_eager, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, func, text
from app import db
from app.models.wizyta import Wizyta, Termin, WizytaUsluga
from app.models.pacjent import Pacjent
from app.models.lekarz import Lekarz
from app.models.platnosc import Platnosc, MetodaPlatnosci
from app.models.usluga import Usluga
from app.models.admin import LogSystemowy
from app.models.czekajacy import Czekajacy, CzekajacyUsluga
from app.models.powiadomienie import (
    PowiadomienieKonfiguracja, Powiadomienie, 
    TypPowiadomienia, StatusPowiadomienia, SzablonPowiadomienia,
    TresnoscPowiadomienia
)
from app.services.base_service import BaseService, ServiceError
from app.services.notification_service import NotificationService
from app.services.notification_utils import (
    send_appointment_confirmation,
    send_appointment_cancellation,
    send_appointment_reminder
)

# Initialize logger
logger = logging.getLogger(__name__)


class AppointmentStatus(str, Enum):
    PLANNED = 'ZAPLANOWANA'
    COMPLETED = 'ZAKOŃCZONA'
    CANCELLED = 'ANULOWANA'
    RESCHEDULED = 'PRZENIESIONA'
    WAITING = 'OCZEKUJĄCA'


class WaitingListStatus(str, Enum):
    PENDING = 'OCZEKUJĄCA'
    NOTIFIED = 'POWIADOMIONA'
    CANCELLED = 'ANULOWANA'
    FULFILLED = 'ZREALIZOWANA'

class AppointmentService:
    """
    Service for handling appointment-related operations including:
    - Booking and managing appointments
    - Rescheduling appointments
    - Managing waiting lists
    - Sending notifications
    - Calendar integration
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize the appointment service.
        
        Args:
            db_session: Optional database session (uses Flask-SQLAlchemy session by default)
        """
        self.db_session = db_session or db.session
        self.termin_service = BaseService(Termin, self.db_session)
        self.wizyta_service = BaseService(Wizyta, self.db_session)
        self.notification_service = NotificationService(self.db_session)
    
    def get_available_slots(
        self, 
        doctor_id: int, 
        start_date: datetime, 
        end_date: datetime,
        duration_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots for a doctor within a date range
        
        Args:
            doctor_id: ID of the doctor
            start_date: Start of date range
            end_date: End of date range
            duration_minutes: Minimum duration required for the appointment
            
        Returns:
            List of available time slots with details
        """
        # Get all available slots for the doctor in the date range
        available_slots = self.db_session.query(Termin).filter(
            Termin.lekarz_id == doctor_id,
            Termin.dostepny == True,
            Termin.data >= start_date.date(),
            Termin.data <= end_date.date()
        ).order_by(Termin.data, Termin.godzina_od).all()
        
        # Filter out slots that are too short
        min_duration = timedelta(minutes=duration_minutes)
        available_slots = [
            slot for slot in available_slots
            if (datetime.combine(slot.data, slot.godzina_do) - 
                datetime.combine(slot.data, slot.godzina_od)) >= min_duration
        ]
        
        # Convert to dictionary format
        return [{
            'id': slot.id,
            'data': slot.data.isoformat(),
            'godzina_od': slot.godzina_od.strftime('%H:%M'),
            'godzina_do': slot.godzina_do.strftime('%H:%M'),
            'lekarz_id': slot.lekarz_id,
            'duration_minutes': int((datetime.combine(slot.data, slot.godzina_do) - 
                                  datetime.combine(slot.data, slot.godzina_od)).total_seconds() / 60)
        } for slot in available_slots]
    
    def book_appointment(
        self,
        patient_id: int,
        doctor_id: int,
        slot_id: int,
        services: Optional[List[Dict[str, int]]] = None,
        notes: Optional[str] = None,
        from_waiting_list: bool = False
    ) -> Dict[str, Any]:
        """
        Book a new appointment
        
        Args:
            patient_id: ID of the patient
            doctor_id: ID of the doctor
            slot_id: ID of the time slot
            services: List of service IDs and quantities
            notes: Optional appointment notes
            from_waiting_list: Whether this booking is from the waiting list
            
        Returns:
            Dictionary with appointment details
            
        Raises:
            ServiceError: If booking fails
        """
        # Start a transaction
        try:
            # Check if patient exists and is active
            patient = self.db_session.query(Pacjent).get(patient_id)
            if not patient or not patient.aktywny:
                raise ServiceError("Nieprawidlowy pacjent lub konto nieaktywne", code=400)
            
            # Check if doctor exists and is active
            doctor = self.db_session.query(Lekarz).get(doctor_id)
            if not doctor or not doctor.aktywny:
                raise ServiceError("Nieprawidlowy lekarz lub konto nieaktywne", code=400)
            
            # Check if slot exists and is available or if booking from waiting list
            slot = self.termin_service.get(slot_id)
            if not slot or (not slot.dostepny and not from_waiting_list) or slot.lekarz_id != doctor_id:
                # If slot is not available, add to waiting list if not already from waiting list
                if not from_waiting_list:
                    self._add_to_waiting_list(patient_id, doctor_id, slot_id, services, notes)
                    raise ServiceError(
                        "Wybrany termin jest niedostepny. Zostales dodany do listy oczekujacych.", 
                        code=409,  # Conflict
                        extra={"waiting_list_added": True}
                    )
                else:
                    raise ServiceError("Wybrany termin jest juz niedostepny.", code=400)
            
            # Calculate total amount for services
            total_amount = 0
            service_details = []
            
            if services:
                service_ids = [s['usluga_id'] for s in services]
                services_db = {s.id: s for s in self.db_session.query(Usluga).filter(Usluga.id.in_(service_ids)).all()}
                
                for item in services:
                    service_id = item['usluga_id']
                    quantity = item.get('ilosc', 1)
                    
                    if service_id not in services_db:
                        raise ServiceError(f"Usluga o ID {service_id} nie istnieje", code=400)
                    
                    service = services_db[service_id]
                    total_amount += float(service.cena) * quantity
                    service_details.append({
                        'usluga': service,
                        'ilosc': quantity,
                        'cena_jednostkowa': float(service.cena)
                    })
            
            # Create payment record if services were selected
            payment = None
            if total_amount > 0:
                payment = Platnosc(
                    kwota=total_amount,
                    status='OCZEKUJACA',
                    data_utworzenia=datetime.utcnow()
                )
                self.db_session.add(payment)
                self.db_session.flush()  # Get the payment ID
            
            # Create the appointment
            appointment = Wizyta(
                pacjent_id=patient_id,
                lekarz_id=doctor_id,
                termin_id=slot_id,
                status=AppointmentStatus.PLANNED,
                platnosc_id=payment.id if payment else None,
                opis=notes,
                data_utworzenia=datetime.utcnow(),
                data_modyfikacji=datetime.utcnow()
            )
            self.db_session.add(appointment)
            self.db_session.flush()  # Get the appointment ID
            
            # Mark the slot as unavailable
            slot.dostepny = False
            
            # Add services to the appointment
            for detail in service_details:
                wizyta_usluga = WizytaUsluga(
                    wizyta_id=appointment.id,
                    usluga_id=detail['usluga'].id,
                    ilosc=detail['ilosc']
                )
                self.db_session.add(wizyta_usluga)
            
            # If this is from waiting list, update waiting list status
            if from_waiting_list:
                self._update_waiting_list_status(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    slot_id=slot_id,
                    status=WaitingListStatus.FULFILLED
                )
            
            # Commit the transaction
            self.db_session.commit()
            
            # Send confirmation notification
            try:
                send_appointment_confirmation(appointment.id)
            except Exception as e:
                logger.error(f"Error sending appointment confirmation: {str(e)}")
                # Continue with the booking even if notification fails
            
            # Emit socket event for real-time updates
            socketio.emit('appointment_booked', {
                'appointment_id': appointment.id,
                'patient_id': patient_id,
                'doctor_id': doctor_id,
                'slot_id': slot_id
            })
            
            # Return appointment details
            return self._get_appointment_details(appointment.id)
            
        except ServiceError as se:
            self.db_session.rollback()
            raise
        except SQLAlchemyError as e:
            self.db_session.rollback()
            raise ServiceError(f"Blad bazy danych podczas rezerwacji wizyty: {str(e)}", code=500)
        except Exception as e:
            self.db_session.rollback()
            raise ServiceError(f"Nieoczekiwany blad podczas rezerwacji wizyty: {str(e)}", code=500)
    
    def reschedule_appointment(
        self, 
        appointment_id: int, 
        new_slot_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reschedule an existing appointment to a new time slot
        
        Args:
            appointment_id: ID of the appointment to reschedule
            new_slot_id: ID of the new time slot
            reason: Optional reason for rescheduling
            
        Returns:
            Dictionary with rescheduling result
            
        Raises:
            ServiceError: If rescheduling fails
        """
        try:
            # Get the appointment with related data
            appointment = self.db_session.query(Wizyta).options(
                joinedload(Wizyta.termin),
                joinedload(Wizyta.platnosc),
                joinedload(Wizyta.pacjent)
            ).get(appointment_id)
            
            if not appointment:
                raise ServiceError("Wizyta nie istnieje", code=404)
                
            if appointment.status == AppointmentStatus.CANCELLED:
                raise ServiceError("Nie można przenieść anulowanej wizyty", code=400)
                
            if appointment.status == AppointmentStatus.COMPLETED:
                raise ServiceError("Nie można przenieść zakończonej wizyty", code=400)
            
            # Check if new slot exists and is available
            new_slot = self.termin_service.get(new_slot_id)
            if not new_slot or not new_slot.dostepny:
                raise ServiceError("Wybrany termin jest niedostępny", code=400)
            
            # Get the old slot to mark it as available
            old_slot = appointment.termin
            
            # Start transaction
            try:
                # Update appointment with new slot
                appointment.termin_id = new_slot_id
                appointment.status = AppointmentStatus.RESCHEDULED
                appointment.data_modyfikacji = datetime.utcnow()
                
                # Update slot availability
                old_slot.dostepny = True
                new_slot.dostepny = False
                
                # Log the rescheduling
                log = LogSystemowy(
                    typ_operacji='PRZENIESIENIE_WIZYTY',
                    opis=f"Wizyta przeniesiona z terminu {old_slot.data} {old_slot.godzina_od} na {new_slot.data} {new_slot.godzina_od}",
                    szczegoly=reason,
                    data_operacji=datetime.utcnow()
                )
                self.db_session.add(log)
                
                # Commit the transaction
                self.db_session.commit()
                
                # Send notification about rescheduling
                self._send_reschedule_notification(appointment.id, old_slot, new_slot)
                
                return {
                    'status': 'success',
                    'message': 'Wizyta została pomyślnie przełożona',
                    'appointment': self._get_appointment_details(appointment.id)
                }
                
            except Exception as e:
                self.db_session.rollback()
                raise ServiceError(f"Błąd podczas przenoszenia wizyty: {str(e)}", code=500)
                
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(f"Nieoczekiwany błąd podczas przenoszenia wizyty: {str(e)}", code=500)
    
    def _add_to_waiting_list(
        self,
        patient_id: int,
        doctor_id: int,
        slot_id: int,
        services: Optional[List[Dict[str, int]]] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a patient to the waiting list for a specific time slot
        
        Args:
            patient_id: ID of the patient
            doctor_id: ID of the doctor
            slot_id: ID of the requested time slot
            services: List of requested services
            notes: Optional notes
            
        Returns:
            Dictionary with waiting list entry details
        """
        try:
            # Check if patient is already on the waiting list for this slot
            existing = self.db_session.query(Czekajacy).filter(
                Czekajacy.pacjent_id == patient_id,
                Czekajacy.termin_id == slot_id,
                Czekajacy.status.in_([WaitingListStatus.PENDING, WaitingListStatus.NOTIFIED])
            ).first()
            
            if existing:
                return {
                    'status': 'info',
                    'message': 'Jesteś już na liście oczekujących na ten termin',
                    'waiting_list_id': existing.id
                }
            
            # Create new waiting list entry
            waiting_entry = Czekajacy(
                pacjent_id=patient_id,
                lekarz_id=doctor_id,
                termin_id=slot_id,
                status=WaitingListStatus.PENDING,
                data_dodania=datetime.utcnow(),
                notatki=notes
            )
            
            self.db_session.add(waiting_entry)
            self.db_session.flush()  # Get the ID
            
            # Add services to waiting list entry if provided
            if services:
                for service in services:
                    czekajacy_usluga = CzekajacyUsluga(
                        czekajacy_id=waiting_entry.id,
                        usluga_id=service['usluga_id'],
                        ilosc=service.get('ilosc', 1)
                    )
                    self.db_session.add(czekajacy_usluga)
            
            self.db_session.commit()
            
            # Notify admin about new waiting list entry
            self._notify_admin_about_waiting_list(waiting_entry.id)
            
            return {
                'status': 'success',
                'message': 'Zostałeś dodany do listy oczekujących na wybrany termin',
                'waiting_list_id': waiting_entry.id
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Błąd podczas wysyłania powiadomienia o przełożeniu wizyty: {str(e)}")
            raise ServiceError(f"Błąd podczas dodawania do listy oczekujących: {str(e)}")
    
    
    def _send_reschedule_notification(self, appointment_id: int, old_slot: 'Termin', new_slot: 'Termin') -> None:
        """
        Send notification about appointment rescheduling
        
        Args:
            appointment_id: ID of the appointment
            old_slot: The original time slot
            new_slot: The new time slot
        """
        try:
            # Get appointment with related data
            appointment = self.db_session.query(Wizyta).options(
                joinedload(Wizyta.pacjent),
                joinedload(Wizyta.lekarz)
            ).get(appointment_id)
            
            if not appointment or not appointment.pacjent or not appointment.lekarz:
                return
            
            # Prepare notification context
            context = {
                'patient_name': f"{appointment.pacjent.imie} {appointment.pacjent.nazwisko}",
                'doctor_name': f"{appointment.lekarz.imie} {appointment.lekarz.nazwisko}",
                'old_appointment_date': old_slot.data.isoformat(),
                'old_appointment_time': old_slot.godzina_od.strftime('%H:%M'),
                'new_appointment_date': new_slot.data.isoformat(),
                'new_appointment_time': new_slot.godzina_od.strftime('%H:%M'),
                'appointment_id': appointment_id,
                'clinic_name': current_app.config.get('CLINIC_NAME', 'Przychodnia Lekarska'),
                'clinic_phone': current_app.config.get('CLINIC_PHONE', ''),
                'clinic_email': current_app.config.get('CLINIC_EMAIL', '')
            }
            
            # Send notification to patient
            try:
                self.notification_service.send_notification(
                    recipient_email=appointment.pacjent.email,
                    recipient_phone=appointment.pacjent.telefon,
                    template_name='appointment_rescheduled',
                    context=context
                )
                logger.info(f"Reschedule notification sent for appointment ID: {appointment_id}")
            except Exception as e:
                logger.error(f"Error sending reschedule notification: {str(e)}", exc_info=True)
                # Don't re-raise to avoid breaking the main flow
                
        except Exception as e:
            logger.error(f"Error preparing reschedule notification: {str(e)}", exc_info=True)
            # Don't re-raise to avoid breaking the main flow

    def _send_waiting_list_notification(self, waiting_list_id: int) -> None:
        """
        Send notification to patient about available slot from waiting list
        
        Args:
            waiting_list_id: ID of the waiting list entry
        """
        try:
            # Get waiting list entry with related data
            entry = self.db_session.query(Czekajacy).options(
                joinedload(Czekajacy.pacjent),
                joinedload(Czekajacy.lekarz),
                joinedload(Czekajacy.termin)
            ).get(waiting_list_id)
            
            if not entry or not entry.pacjent or not entry.lekarz or not entry.termin:
                return
            
            # Prepare notification context
            context = {
                'patient_name': f"{entry.pacjent.imie} {entry.pacjent.nazwisko}",
                'doctor_name': f"{entry.lekarz.imie} {entry.lekarz.nazwisko}",
                'appointment_date': entry.termin.data.isoformat(),
                'appointment_time': entry.termin.godzina_od.strftime('%H:%M'),
                'waiting_list_id': waiting_list_id,
                'expiry_hours': 24,  # Standard expiry time in hours
                'clinic_name': current_app.config.get('CLINIC_NAME', 'Przychodnia Lekarska'),
                'clinic_phone': current_app.config.get('CLINIC_PHONE', ''),
                'clinic_email': current_app.config.get('CLINIC_EMAIL', '')
            }
            
            # Send notification to patient
            try:
                self.notification_service.send_notification(
                    recipient_email=entry.pacjent.email,
                    recipient_phone=entry.pacjent.telefon,
                    template_name='waiting_list_available',
                    context=context
                )
                logger.info(f"Waiting list notification sent for entry ID: {waiting_list_id}")
            except Exception as e:
                logger.error(f"Error sending waiting list notification: {str(e)}", exc_info=True)
                # Don't re-raise to avoid breaking the main flow
                
        except Exception as e:
            logger.error(f"Error preparing waiting list notification: {str(e)}", exc_info=True)
            # Don't re-raise to avoid breaking the main flow

    def _notify_admin_about_waiting_list(self, waiting_list_id: int) -> None:
        """
        Notify admin about new waiting list entry
        
        Args:
            waiting_list_id: ID of the waiting list entry
        """
        try:
            # Get waiting list entry with related data
            entry = self.db_session.query(Czekajacy).options(
                joinedload(Czekajacy.pacjent),
                joinedload(Czekajacy.lekarz),
                joinedload(Czekajacy.termin)
            ).get(waiting_list_id)
            
            if not entry or not entry.pacjent or not entry.termin:
                return
            
            # Get admin email from config
            admin_email = current_app.config.get('ADMIN_EMAIL')
            if not admin_email:
                logger.warning("No ADMIN_EMAIL configured, skipping admin notification")
                return
            
            # Prepare notification data
            patient_name = f"{entry.pacjent.imie} {entry.pacjent.nazwisko}"
            doctor_name = f"{entry.lekarz.imie} {entry.lekarz.nazwisko}"
            
            # Prepare context for the notification
            context = {
                'patient_name': patient_name,
                'doctor_name': doctor_name,
                'appointment_date': entry.termin.data.isoformat(),
                'appointment_time': entry.termin.godzina_od.strftime('%H:%M'),
                'waiting_list_id': waiting_list_id,
                'patient_phone': entry.pacjent.telefon,
                'patient_email': entry.pacjent.email,
                'entry_date': entry.data_dodania.strftime('%Y-%m-%d %H:%M'),
                'notes': entry.uwagi or 'Brak uwag',
                'clinic_name': current_app.config.get('CLINIC_NAME', 'Przychodnia Lekarska'),
                'clinic_phone': current_app.config.get('CLINIC_PHONE', ''),
                'clinic_email': current_app.config.get('CLINIC_EMAIL', ''),
                'admin_dashboard_url': current_app.config.get('ADMIN_DASHBOARD_URL', '#')
            }
            
            # Send notification to admin using the notification service
            try:
                self.notification_service.send_notification(
                    recipient_email=admin_email,
                    template_name='admin_waiting_list_notification',
                    context=context
                )
                logger.info(f"Admin notified about waiting list entry ID: {waiting_list_id}")
            except Exception as e:
                logger.error(f"Error sending admin notification about waiting list: {str(e)}", exc_info=True)
            
            # Commit any database changes
            self.db_session.commit()
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Błąd podczas powiadamiania administratora o nowym wpisie na liście oczekujących: {str(e)}", exc_info=True)
            # Don't re-raise to avoid breaking the main flow

    def _update_waiting_list_status(
        self,
        patient_id: int,
        doctor_id: int,
        slot_id: int,
        status: WaitingListStatus
    ) -> None:
        """
        Update status of a waiting list entry
        
        Args:
            patient_id: ID of the patient
            doctor_id: ID of the doctor
            slot_id: ID of the time slot
            status: New status to set
        """
        try:
            entry = self.db_session.query(Czekajacy).filter(
                Czekajacy.pacjent_id == patient_id,
                Czekajacy.lekarz_id == doctor_id,
                Czekajacy.termin_id == slot_id,
                Czekajacy.status == WaitingListStatus.PENDING
            ).first()
            
            if entry:
                entry.status = status
                entry.data_modyfikacji = datetime.utcnow()
                self.db_session.commit()
                
        except Exception as e:
            self.db_session.rollback()
            raise ServiceError(f"Błąd podczas aktualizacji listy oczekujących: {str(e)}", code=500)
    
    def get_waiting_list_entries(
        self,
        doctor_id: Optional[int] = None,
        slot_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get waiting list entries with optional filters
        
        Args:
            doctor_id: Filter by doctor ID
            slot_id: Filter by time slot ID
            status: Filter by status
            
        Returns:
            List of waiting list entries with details
        """
        query = self.db_session.query(Czekajacy).options(
            joinedload(Czekajacy.pacjent),
            joinedload(Czekajacy.lekarz),
            joinedload(Czekajacy.termin)
        )
        
        if doctor_id:
            query = query.filter(Czekajacy.lekarz_id == doctor_id)
            
        if slot_id:
            query = query.filter(Czekajacy.termin_id == slot_id)
            
        if status:
            query = query.filter(Czekajacy.status == status)
        
        entries = query.order_by(Czekajacy.data_dodania).all()
        
        return [{
            'id': entry.id,
            'patient': {
                'id': entry.pacjent.id,
                'imie': entry.pacjent.imie,
                'nazwisko': entry.pacjent.nazwisko,
                'email': entry.pacjent.email
            },
            'doctor': {
                'id': entry.lekarz.id,
                'imie': entry.lekarz.imie,
                'nazwisko': entry.lekarz.nazwisko,
                'specjalizacja': entry.lekarz.specjalizacja
            },
            'slot': {
                'id': entry.termin.id,
                'data': entry.termin.data.isoformat(),
                'godzina_od': entry.termin.godzina_od.strftime('%H:%M'),
                'godzina_do': entry.termin.godzina_do.strftime('%H:%M')
            },
            'status': entry.status,
            'data_dodania': entry.data_dodania.isoformat(),
            'notatki': entry.notatki
        } for entry in entries]
    
    def process_waiting_list_for_slot(self, slot_id: int) -> None:
        """
        Process waiting list when a time slot becomes available
        
        Args:
            slot_id: ID of the available time slot
        """
        try:
            # Get the first patient in the waiting list for this slot
            waiting_entry = self.db_session.query(Czekajacy).filter(
                Czekajacy.termin_id == slot_id,
                Czekajacy.status == WaitingListStatus.PENDING
            ).order_by(Czekajacy.data_dodania).first()
            
            if waiting_entry:
                # Mark as notified
                waiting_entry.status = WaitingListStatus.NOTIFIED
                waiting_entry.data_modyfikacji = datetime.utcnow()
                
                # Send notification to the patient
                self._send_waiting_list_notification(waiting_entry.id)
                
                self.db_session.commit()
                
        except Exception as e:
            self.db_session.rollback()
            raise ServiceError(f"Błąd podczas przetwarzania listy oczekujących: {str(e)}", code=500)
    
    def cancel_appointment(self, appointment_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel an existing appointment
        
        Args:
            appointment_id: ID of the appointment to cancel
            reason: Optional cancellation reason
            
        Returns:
            Dictionary with cancellation result
            
        Raises:
            ServiceError: If cancellation fails
        """
        try:
            # Get the appointment with related data
            appointment = self.db_session.query(Wizyta).options(
                joinedload(Wizyta.termin),
                joinedload(Wizyta.platnosc),
                joinedload(Wizyta.pacjent)
            ).get(appointment_id)
            
            if not appointment:
                raise ServiceError("Wizyta nie istnieje", code=404)
                
            if appointment.status == 'ANULOWANA':
                raise ServiceError("Wizyta została już anulowana", code=400)
                
            if appointment.status == 'ZAKOŃCZONA':
                raise ServiceError("Nie można anulować zakończonej wizyty", code=400)
            
            # Update appointment status
            appointment.status = 'ANULOWANA'
            appointment.data_modyfikacji = datetime.utcnow()
            
            # Mark the slot as available again
            if appointment.termin:
                appointment.termin.dostepny = True
            
            # Update payment status if exists
            if appointment.platnosc and appointment.platnosc.status == 'OCZEKUJĄCA':
                appointment.platnosc.status = 'ANULOWANA'
                appointment.platnosc.data_modyfikacji = datetime.utcnow()
            
            # Log the cancellation reason
            if reason:
                log = LogSystemowy(
                    typ_operacji='ANULOWANIE_WIZYTY',
                    opis=f"Anulowano wizytę {appointment_id}",
                    szczegoly=f"Powód: {reason}",
                    data_operacji=datetime.utcnow()
                )
                self.db_session.add(log)
            
            # Commit the transaction
            self.db_session.commit()
            
            # Send cancellation notification
            try:
                send_appointment_cancellation(appointment_id, reason)
            except Exception as e:
                logger.error(f"Error sending appointment cancellation: {str(e)}")
                # Continue with the cancellation even if notification fails
            
            return {
                'status': 'success',
                'message': 'Wizyta została anulowana pomyślnie',
                'appointment_id': appointment_id
            }
            
        except ServiceError:
            self.db_session.rollback()
            raise
        except Exception as e:
            self.db_session.rollback()
            raise ServiceError(f"Błąd podczas anulowania wizyty: {str(e)}", code=500)
    
    def get_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """
        Get appointment details by ID
        
        Args:
            appointment_id: ID of the appointment
            
        Returns:
            Dictionary with appointment details
            
        Raises:
            ServiceError: If appointment not found
        """
        appointment = self.db_session.query(Wizyta).get(appointment_id)
        if not appointment:
            raise ServiceError("Wizyta nie istnieje", code=404)
            
        return self._get_appointment_details(appointment_id)
    
    def _get_appointment_details(self, appointment_id: int) -> Dict[str, Any]:
        """Helper method to get detailed appointment information"""
        appointment = self.db_session.query(Wizyta).options(
            joinedload(Wizyta.termin),
            joinedload(Wizyta.lekarz),
            joinedload(Wizyta.pacjent),
            joinedload(Wizyta.platnosc),
            joinedload(Wizyta.uslugi).joinedload(WizytaUsluga.usluga)
        ).get(appointment_id)
        
        if not appointment:
            raise ServiceError("Wizyta nie istnieje", code=404)
        
        # Build the response
        result = {
            'id': appointment.id,
            'status': appointment.status,
            'data_utworzenia': appointment.data_utworzenia.isoformat(),
            'data_modyfikacji': appointment.data_modyfikacji.isoformat(),
            'opis': appointment.opis,
            'termin': None,
            'lekarz': None,
            'pacjent': None,
            'platnosc': None,
            'uslugi': []
        }
        
        # Add termin details
        if appointment.termin:
            result['termin'] = {
                'id': appointment.termin.id,
                'data': appointment.termin.data.isoformat(),
                'godzina_od': appointment.termin.godzina_od.strftime('%H:%M'),
                'godzina_do': appointment.termin.godzina_do.strftime('%H:%M')
            }
        
        # Add doctor details
        if appointment.lekarz:
            result['lekarz'] = {
                'id': appointment.lekarz.id,
                'imie': appointment.lekarz.imie,
                'nazwisko': appointment.lekarz.nazwisko,
                'specjalizacja': appointment.lekarz.specjalizacja
            }
        
        # Add patient details (limited for privacy)
        if appointment.pacjent:
            result['pacjent'] = {
                'id': appointment.pacjent.id,
                'imie': appointment.pacjent.imie,
                'nazwisko': appointment.pacjent.nazwisko
            }
        
        # Add payment details
        # Add payment details if exists
        if hasattr(appointment, 'platnosc') and appointment.platnosc:
            result['platnosc'] = {
                'id': appointment.platnosc.id,
                'kwota': float(appointment.platnosc.kwota) if appointment.platnosc.kwota else 0.0,
                'status': appointment.platnosc.status
            }
        
        # Add services
        if hasattr(appointment, 'uslugi') and appointment.uslugi:
            result['uslugi'] = [{
                'id': wu.usluga.id,
                'nazwa': wu.usluga.nazwa,
                'cena': float(wu.usluga.cena),
                'ilosc': wu.ilosc
            } for wu in appointment.uslugi]
        
        return result
    
    def get_patient_appointments(
        self, 
        patient_id: int, 
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all appointments for a patient with optional filters
        
        Args:
            patient_id: ID of the patient
            status: Filter by status (e.g., 'ZAPLANOWANA', 'ZAKOŃCZONA', 'ANULOWANA')
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            List of appointment dictionaries
        """
        query = self.db_session.query(Wizyta).filter(
            Wizyta.pacjent_id == patient_id
        ).options(
            joinedload(Wizyta.termin),
            joinedload(Wizyta.lekarz)
        )
        
        if status:
            # Use the enum value if it's an enum, otherwise use the string as is
            status_value = status.value if hasattr(status, 'value') else status.upper()
            query = query.filter(Wizyta.status == status_value)
            
        if start_date:
            query = query.join(Termin).filter(Termin.data >= start_date.date())
            
        if end_date:
            if not start_date:
                query = query.join(Termin)
            query = query.filter(Termin.data <= end_date.date())
        
        # Order by date and time
        query = query.join(Termin).order_by(Termin.data, Termin.godzina_od)
        
        appointments = query.all()
        
        # Convert to dictionary format
        result = []
        for appt in appointments:
            result.append({
                'id': appt.id,
                'status': appt.status,
                'data': appt.termin.data.isoformat() if appt.termin else None,
                'godzina_od': appt.termin.godzina_od.strftime('%H:%M') if appt.termin else None,
                'godzina_do': appt.termin.godzina_do.strftime('%H:%M') if appt.termin else None,
                'lekarz': {
                    'id': appt.lekarz.id,
                    'imie': appt.lekarz.imie,
                    'nazwisko': appt.lekarz.nazwisko,
                    'specjalizacja': appt.lekarz.specjalizacja
                } if appt.lekarz else None
            })
        
        return result
