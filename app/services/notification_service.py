import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app, render_template
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db
from models.powiadomienie import Email, SMS, PowiadomienieKonfiguracja
from models.wizyta import Wizyta
from base_service import BaseService, ServiceError

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for handling notifications including:
    - Sending email and SMS notifications
    - Managing notification templates
    - Tracking notification status
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize the notification service.
        
        Args:
            db_session: Optional database session
        """
        self.db_session = db_session or db.session
        self.email_service = BaseService(Email, self.db_session)
        self.sms_service = BaseService(SMS, self.db_session)
        self.config_service = BaseService(PowiadomienieKonfiguracja, self.db_session)
    
    def send_appointment_confirmation(self, appointment_id: int) -> Dict[str, Any]:
        """
        Send appointment confirmation notification.
        
        Args:
            appointment_id: ID of the appointment
            
        Returns:
            Dict with notification details
        """
        return self._send_notification(appointment_id, 'POTWIERDZENIE')
    
    def send_appointment_reminder(self, appointment_id: int) -> Dict[str, Any]:
        """
        Send appointment reminder notification.
        
        Args:
            appointment_id: ID of the appointment
            
        Returns:
            Dict with notification details
        """
        return self._send_notification(appointment_id, 'PRZYPOMNIENIE')
    
    def send_appointment_cancellation(self, appointment_id: int) -> Dict[str, Any]:
        """
        Send appointment cancellation notification.
        
        Args:
            appointment_id: ID of the appointment
            
        Returns:
            Dict with notification details
        """
        return self._send_notification(appointment_id, 'ANULOWANIE')
    
    def _send_notification(self, appointment_id: int, notification_type: str) -> Dict[str, Any]:
        """
        Internal method to send a notification.
        
        Args:
            appointment_id: ID of the appointment
            notification_type: Type of notification (POTWIERDZENIE, PRZYPOMNIENIE, ANULOWANIE)
            
        Returns:
            Dict with notification details
            
        Raises:
            ServiceError: If notification fails to send
        """
        try:
            # Get appointment details
            appointment = self.db_session.query(Wizyta).get(appointment_id)
            if not appointment:
                raise ServiceError(f"Appointment with ID {appointment_id} not found")
            
            # Get notification configuration
            config = self.config_service.get_first(typ=notification_type, aktywny=True)
            if not config:
                raise ServiceError(f"No active configuration found for {notification_type} notifications")
            
            # Prepare context for templates
            context = {
                'appointment': appointment,
                'patient': appointment.pacjent,
                'doctor': appointment.lekarz,
                'appointment_time': f"{appointment.termin.data} {appointment.termin.godzina_od}",
                'current_date': datetime.now().strftime('%Y-%m-%d')
            }
            
            # Send email if template exists
            email_sent = False
            if config.szablon_email:
                try:
                    subject = f"{notification_type.capitalize()} wizyty - {appointment.termin.data}"
                    body = render_template('emails/appointment_notification.html', **context)
                    
                    # In a real app, you would use Flask-Mail or similar
                    # For now, we'll just log it
                    logger.info(f"Would send email to {appointment.pacjent.email} with subject: {subject}")
                    logger.debug(f"Email body: {body}")
                    
                    # Save email record
                    email = Email(
                        wizyta_id=appointment_id,
                        temat=subject,
                        tresc=body,
                        data_wyslania=datetime.now(),
                        status='WYSŁANY'
                    )
                    self.db_session.add(email)
                    email_sent = True
                    
                except Exception as e:
                    logger.error(f"Failed to send email notification: {str(e)}")
            
            # Send SMS if template exists
            sms_sent = False
            if config.szablon_sms:
                try:
                    message = config.szablon_sms.format(**context)
                    
                    # In a real app, you would integrate with an SMS gateway
                    logger.info(f"Would send SMS to {appointment.pacjent.telefon} with message: {message}")
                    
                    # Save SMS record
                    sms = SMS(
                        wizyta_id=appointment_id,
                        tresc=message,
                        data_wyslania=datetime.now(),
                        status='WYSŁANY'
                    )
                    self.db_session.add(sms)
                    sms_sent = True
                    
                except Exception as e:
                    logger.error(f"Failed to send SMS notification: {str(e)}")
            
            self.db_session.commit()
            
            return {
                'success': email_sent or sms_sent,
                'email_sent': email_sent,
                'sms_sent': sms_sent,
                'appointment_id': appointment_id,
                'notification_type': notification_type
            }
            
        except SQLAlchemyError as e:
            self.db_session.rollback()
            logger.error(f"Database error in _send_notification: {str(e)}")
            raise ServiceError("Failed to send notification due to a database error")
        except Exception as e:
            logger.error(f"Unexpected error in _send_notification: {str(e)}")
            raise ServiceError("Failed to send notification due to an unexpected error")
