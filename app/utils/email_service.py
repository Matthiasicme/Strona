import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template_string, current_app
from datetime import datetime, timedelta
import jwt

def send_verification_email(recipient_email, verification_token, user_id):
    """
    Wysyła email weryfikacyjny do użytkownika
    """
    # Konfiguracja wiadomości email
    subject = "Weryfikacja adresu email - System Rejestracji Wizyt"
    
    # Link weryfikacyjny
    verification_url = f"{current_app.config['FRONTEND_URL']}/verify-email?token={verification_token}&user_id={user_id}"
    
    # Szablon wiadomości HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Weryfikacja adresu email</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #0056b3;
                color: white !important;
                text-decoration: none;
                border-radius: 5px;
                margin: 15px 0;
            }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Witaj w naszym systemie rejestracji wizyt!</h2>
            <p>Dziękujemy za rejestrację. Aby aktywować swoje konto, kliknij przycisk poniżej:</p>
            
            <p>
                <a href="{{ verification_url }}" class="button">Aktywuj konto</a>
            </p>
            
            <p>Jeśli przycisk nie działa, skopiuj i wklej poniższy link w pasek adresu przeglądarki:</p>
            <p>{{ verification_url }}</p>
            
            <p>Link aktywacyjny jest ważny przez 24 godziny.</p>
            
            <div class="footer">
                <p>Jeśli to nie Ty zakładałeś konto, zignoj tę wiadomość.</p>
                <p>© 2023 System Rejestracji Wizyt. Wszelkie prawa zastrzeżone.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Wypełnienie szablonu danymi
    html = render_template_string(html, verification_url=verification_url)
    
    # Tworzenie wiadomości
    msg = MIMEMultipart()
    msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = recipient_email
    msg['Subject'] = subject
    
    # Dołączenie treści HTML
    msg.attach(MIMEText(html, 'html'))
    
    try:
        # Wysyłanie emaila
        with smtplib.SMTP(
            host=current_app.config['MAIL_SERVER'],
            port=current_app.config['MAIL_PORT']
        ) as server:
            if current_app.config['MAIL_USE_TLS']:
                server.starttls()
            
            if current_app.config['MAIL_USERNAME'] and current_app.config['MAIL_PASSWORD']:
                server.login(
                    current_app.config['MAIL_USERNAME'],
                    current_app.config['MAIL_PASSWORD']
                )
            
            server.send_message(msg)
            return True
    except Exception as e:
        current_app.logger.error(f"Błąd podczas wysyłania emaila: {str(e)}")
        return False

def generate_verification_token(user_id, expires_in=86400):
    """
    Generuje token weryfikacyjny dla użytkownika
    """
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(seconds=expires_in),
        'type': 'email_verification'
    }
    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )

def verify_token(token):
    """
    Weryfikuje token weryfikacyjny
    """
    try:
        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )
        if payload.get('type') != 'email_verification':
            return None
        return payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
