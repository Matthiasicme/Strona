import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Podstawowa konfiguracja
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-secret-key'
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Konfiguracja bazy danych
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://dental_admin:dentalpass123@localhost:5432/dental_registration'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Konfiguracja JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Konfiguracja e-mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Konfiguracja SMS
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    SMS_API_SECRET = os.environ.get('SMS_API_SECRET')
    SMS_SENDER_ID = os.environ.get('SMS_SENDER_ID')
    
    # Konfiguracja platformy płatności
    PAYMENT_API_KEY = os.environ.get('PAYMENT_API_KEY')
    PAYMENT_API_SECRET = os.environ.get('PAYMENT_API_SECRET')
    
    # Konfiguracja integracji z ZnanyLekarz
    ZNANYLEKARZ_API_KEY = os.environ.get('ZNANYLEKARZ_API_KEY')
    ZNANYLEKARZ_API_SECRET = os.environ.get('ZNANYLEKARZ_API_SECRET')
    
    # Konfiguracja integracji z NFZ
    NFZ_API_KEY = os.environ.get('NFZ_API_KEY')
    NFZ_API_SECRET = os.environ.get('NFZ_API_SECRET')
    
    # Konfiguracja URL frontendu (do linków weryfikacyjnych)
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5000')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://dental_admin:dentalpass123@localhost:5432/dental_registration_test'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=10)


class ProductionConfig(Config):
    DEBUG = False
    # W środowisku produkcyjnym używać bezpieczniejszych ustawień
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_CSRF_PROTECT = True


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}