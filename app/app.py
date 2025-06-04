from flask import Flask, render_template, flash, redirect, url_for, jsonify, request, session, current_app
from datetime import datetime, time
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, get_jwt_identity
from flask_cors import CORS
from flask_mail import Mail
from flask_swagger_ui import get_swaggerui_blueprint
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sys
import re
from config import Config

# Add the parent directory to the path to allow absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Inicjalizacja rozszerzeń
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'login'  # Specify the login view for redirects
login_manager.login_message = 'Proszę się zalogować, aby uzyskać dostęp do tej strony.'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(config_class)
    
    # Inicjalizacja rozszerzeń z aplikacją
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    CORS(app)
    
    # Configure session protection
    app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookies over HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Protection against CSRF
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session timeout
    
    # Rejestracja blueprintów (routes)
    from routes.auth_routes import auth_bp
    from routes.pacjent_routes import pacjent_bp
    from routes.lekarz_routes import lekarz_bp
    from routes.wizyta_routes import wizyta_bp
    from routes.platnosc_routes import platnosc_bp
    from routes.admin_routes import admin_bp
    from routes.integracja_routes import integracja_bp
    from routes.termin_routes import termin_bp
    from routes.api_routes import api_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(pacjent_bp, url_prefix='/api/pacjenci')
    app.register_blueprint(lekarz_bp, url_prefix='/api/lekarze')
    app.register_blueprint(wizyta_bp, url_prefix='/api/wizyty')
    app.register_blueprint(platnosc_bp, url_prefix='/api/platnosci')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(integracja_bp, url_prefix='/api/integracje')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(termin_bp, url_prefix='')
    
    @login_manager.user_loader
    def load_user(user_id):
        from models.pacjent import Pacjent
        return Pacjent.query.get(int(user_id))
    
    # Web routes
    # Custom filter for date formatting
    @app.template_filter('strftime')
    def _jinja2_filter_datetime(date, fmt=None):
        if fmt:
            return date.strftime(fmt)
        return date.strftime('%Y-%m-%d %H:%M')
    
    @app.route('/')
    def home():
        from datetime import datetime
        return render_template('index.html', now=datetime.utcnow())
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('home'))
            
        if request.method == 'POST':
            from models.pacjent import Pacjent
            from models.log_systemowy import LogSystemowy
            email = request.form.get('email')
            password = request.form.get('password')
            user = Pacjent.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                if not user.aktywny:
                    flash('Twoje konto jest nieaktywne. Skontaktuj się z administratorem.', 'danger')
                    return redirect(url_for('login'))
                    
                login_user(user, remember=True)
                next_page = request.args.get('next')
                
                # Log successful login
                log = LogSystemowy(
                    typ="INFO",
                    akcja="LOGOWANIE",
                    opis=f"Użytkownik zalogował się: {email}",
                    uzytkownik_id=user.id,
                    rola_uzytkownika="pacjent",
                    ip_adres=request.remote_addr
                )
                db.session.add(log)
                db.session.commit()
                
                return redirect(next_page or url_for('home'))
            else:
                # Log failed login attempt
                log = LogSystemowy(
                    typ="WARNING",
                    akcja="NIEPOWODZENIE_LOGOWANIA",
                    opis=f"Nieudana próba logowania dla: {email}",
                    ip_adres=request.remote_addr
                )
                db.session.add(log)
                db.session.commit()
                
                flash('Nieprawidłowy email lub hasło', 'danger')
        
        return render_template('login.html', now=datetime.utcnow())
    
    @app.route('/logout')
    @login_required
    def logout():
        from models.log_systemowy import LogSystemowy
        # Log the logout
        log = LogSystemowy(
            typ="INFO",
            akcja="WYLOGOWANIE",
            opis=f"Użytkownik wylogował się: {current_user.email}",
            uzytkownik_id=current_user.id,
            rola_uzytkownika="pacjent",
            ip_adres=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        logout_user()
        return redirect(url_for('login'))
    
    # Add this line to create a named endpoint that matches the template
    app.add_url_rule('/', 'index', home)

    @app.route('/appointments')
    @login_required
    def appointments():
        from datetime import datetime
        return render_template('appointments.html', now=datetime.utcnow())
    
    @app.route('/api/appointments')
    def get_appointments():
        # Import models
        from models.wizyta import Wizyta, Termin
        from models.lekarz import Lekarz
        from models.pacjent import Pacjent
        
        # Get query parameters for filtering
        start = request.args.get('start')
        end = request.args.get('end')
        
        # Base query
        query = db.session.query(Wizyta).join(Termin, Wizyta.termin_id == Termin.id)
        
        # Apply date filters if provided
        if start and end:
            query = query.filter(Termin.data.between(start, end))
        
        # Get appointments with related data
        wizyty = query.options(
            db.joinedload(Wizyta.termin),
            db.joinedload(Wizyta.lekarz_rel),
            db.joinedload(Wizyta.pacjent_rel)
        ).all()
        
        # Format events for FullCalendar
        events = []
        for wizyta in wizyty:
            if wizyta.termin and wizyta.pacjent and wizyta.lekarz:
                event = {
                    'id': wizyta.id,
                    'title': f"{wizyta.pacjent.imie} {wizyta.pacjent.nazwisko} - dr {wizyta.lekarz.imie} {wizyta.lekarz.nazwisko}",
                    'start': f"{wizyta.termin.data}T{wizyta.termin.godzina_od.strftime('%H:%M:%S')}",
                    'end': f"{wizyta.termin.data}T{wizyta.termin.godzina_do.strftime('%H:%M:%S')}",
                    'status': wizyta.status,
                    'pacjent': f"{wizyta.pacjent.imie} {wizyta.pacjent.nazwisko}",
                    'lekarz': f"dr {wizyta.lekarz.imie} {wizyta.lekarz.nazwisko}",
                    'uslugi': [usluga_rel.usluga.nazwa for usluga_rel in wizyta.uslugi]
                }
                events.append(event)
        
        return jsonify(events)

    @app.route('/success')
    def success():
        email = request.args.get('email', '')
        return render_template('success.html', email=email)
        
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'GET':
            return render_template('register.html', now=datetime.utcnow())
            
        if request.method == 'POST':
            from models.pacjent import Pacjent
            from models.log_systemowy import LogSystemowy
            
            # Get form data
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Basic validation
            if not all([email, password, confirm_password]):
                flash('Wszystkie pola są wymagane', 'danger')
                return redirect(url_for('register'))
                
            if password != confirm_password:
                flash('Hasła nie są identyczne', 'danger')
                return redirect(url_for('register'))
                
            # Email validation
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                flash('Nieprawidłowy format adresu email', 'danger')
                return redirect(url_for('register'))
                
            # Password validation
            if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
                flash('Hasło nie spełnia wymagań bezpieczeństwa', 'danger')
                return redirect(url_for('register'))
            
            # Check if email already exists
            if Pacjent.query.filter_by(email=email).first():
                flash('Ten adres email jest już zarejestrowany', 'danger')
                return redirect(url_for('register'))
                
            try:
                new_user = Pacjent(
                    imie=request.form.get('first_name', '').strip(),
                    nazwisko=request.form.get('last_name', '').strip(),
                    email=email.lower().strip(),
                    haslo=password,
                    telefon=request.form.get('phone', '').strip()
                )
                db.session.add(new_user)
                db.session.flush()  # Get the ID for logging
                
                # Log the registration
                log = LogSystemowy(
                    typ="INFO",
                    akcja="REJESTRACJA_PACJENTA",
                    opis=f"Nowy użytkownik zarejestrował się: {email}",
                    uzytkownik_id=new_user.id,
                    rola_uzytkownika="pacjent",
                    ip_adres=request.remote_addr
                )
                db.session.add(log)
                db.session.commit()
                
                # Redirect to success page with email parameter
                return redirect(url_for('success', email=email))
                
                # This flash message won't be shown due to the redirect
                flash('Rejestracja zakończona powodzeniem!', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Registration error: {str(e)}')
                flash('Wystąpił błąd podczas rejestracji. Spróbuj ponownie.', 'danger')
                
        return render_template('register_user.html', now=datetime.utcnow())

    
    # Konfiguracja Swagger UI
    SWAGGER_URL = '/api/docs'
    API_URL = '/static/swagger.json'
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={
            'app_name': "Dental Registration API"
        }
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
    
    # Obsługa błędów
    from utils.helpers import handle_error_response
    
    @app.errorhandler(400)
    def bad_request(e):
        return handle_error_response(400, str(e))
    
    @app.errorhandler(401)
    def unauthorized(e):
        return handle_error_response(401, str(e))
    
    @app.errorhandler(403)
    def forbidden(e):
        return handle_error_response(403, str(e))
    
    @app.errorhandler(404)
    def not_found(e):
        return handle_error_response(404, str(e))
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return handle_error_response(500, str(e))
    
    return app