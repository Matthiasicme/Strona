"""
Skrypt do testowania wysyłki emaili w środowisku deweloperskim.
Uruchom: python send_test_email.py
"""
import os
import sys
from datetime import datetime, timedelta

# Dodaj katalog główny projektu do ścieżki Pythona
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.utils.email_service import send_verification_email

app = create_app()

def send_test_email():
    """Wysyła przykładowy email weryfikacyjny."""
    with app.app_context():
        recipient_email = input("Podaj adres email odbiorcy: ")
        user_id = 1  # Przykładowe ID użytkownika
        
        # Generowanie tokenu weryfikacyjnego
        verification_token = "test_token_1234567890"
        
        print(f"Wysyłanie testowego emaila na adres: {recipient_email}")
        
        # Wysłanie emaila
        success = send_verification_email(
            recipient_email=recipient_email,
            verification_token=verification_token,
            user_id=user_id
        )
        
        if success:
            print("Email został wysłany pomyślnie!")
            print(f"Link weryfikacyjny: {app.config['FRONTEND_URL']}/verify-email?token={verification_token}&user_id={user_id}")
        else:
            print("Wystąpił błąd podczas wysyłania emaila.")

if __name__ == '__main__':
    send_test_email()
