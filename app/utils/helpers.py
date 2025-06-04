from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from functools import wraps
import re

def handle_error_response(status_code, message):
    """
    Standardowa odpowiedź dla błędów
    """
    return jsonify({
        'status': 'error',
        'message': message
    }), status_code


def role_required(*roles):
    """
    Dekorator do sprawdzania roli użytkownika
    Przykład użycia:
    @role_required('admin', 'lekarz')
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            identity = get_jwt_identity()
            
            if not identity or 'role' not in identity:
                return handle_error_response(401, "Brak uprawnień - nieprawidłowy token")
            
            user_role = identity['role']
            
            if user_role not in roles:
                return handle_error_response(403, f"Brak uprawnień - wymagana rola: {', '.join(roles)}")
            
            return fn(*args, **kwargs)
        return decorator
    return wrapper


def sanitize_input(input_str):
    """
    Sanityzacja wejścia użytkownika
    """
    if input_str is None:
        return None
    
    # Usunięcie potencjalnie niebezpiecznych znaków
    sanitized = re.sub(r'[<>&\'";()]', '', input_str)
    return sanitized


def validate_phone_number(phone):
    """
    Walidacja numeru telefonu
    """
    if not phone:
        return False
    
    # Usunięcie białych znaków i innych separatorów
    cleaned_phone = re.sub(r'[\s\-\+\.\(\)]', '', phone)
    
    # Sprawdzenie czy numer ma odpowiednią długość i składa się tylko z cyfr
    if not cleaned_phone.isdigit():
        return False
    
    # Numer powinien mieć między 9 a 15 cyfr
    if len(cleaned_phone) < 9 or len(cleaned_phone) > 15:
        return False
    
    return True


def format_date(date_obj, format_str='%Y-%m-%d'):
    """
    Formatowanie daty
    """
    if not date_obj:
        return None
    
    return date_obj.strftime(format_str)


def format_time(time_obj, format_str='%H:%M'):
    """
    Formatowanie czasu
    """
    if not time_obj:
        return None
    
    return time_obj.strftime(format_str)


def format_datetime(datetime_obj, format_str='%Y-%m-%d %H:%M:%S'):
    """
    Formatowanie daty i czasu
    """
    if not datetime_obj:
        return None
    
    return datetime_obj.strftime(format_str)


def format_decimal(decimal_val, precision=2):
    """
    Formatowanie liczby dziesiętnej
    """
    if decimal_val is None:
        return None
    
    return round(float(decimal_val), precision)


def get_page_info(page, per_page, total_count):
    """
    Informacje o paginacji
    """
    total_pages = (total_count + per_page - 1) // per_page
    
    return {
        'page': page,
        'per_page': per_page,
        'total_count': total_count,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_prev': page > 1
    }


def generate_pagination_links(request, page, per_page, total_pages):
    """
    Generowanie linków do paginacji
    """
    base_url = request.base_url
    
    links = {}
    
    # Link do bieżącej strony
    links['self'] = f"{base_url}?page={page}&per_page={per_page}"
    
    # Link do pierwszej strony
    links['first'] = f"{base_url}?page=1&per_page={per_page}"
    
    # Link do ostatniej strony
    links['last'] = f"{base_url}?page={total_pages}&per_page={per_page}"
    
    # Link do następnej strony
    if page < total_pages:
        links['next'] = f"{base_url}?page={page + 1}&per_page={per_page}"
    
    # Link do poprzedniej strony
    if page > 1:
        links['prev'] = f"{base_url}?page={page - 1}&per_page={per_page}"
    
    return links