import re
from datetime import datetime, date

def validate_email(email):
    """
    Walidacja adresu email
    """
    if not email:
        return False
    
    # Podstawowy wzorzec dla adresu email
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    
    return bool(re.match(pattern, email))


def validate_password(password, min_length=8, require_special=True):
    """
    Walidacja hasła
    """
    if not password:
        return False
    
    # Sprawdzenie długości
    if len(password) < min_length:
        return False
    
    # Sprawdzenie czy zawiera wielką literę
    if not re.search(r'[A-Z]', password):
        return False
    
    # Sprawdzenie czy zawiera małą literę
    if not re.search(r'[a-z]', password):
        return False
    
    # Sprawdzenie czy zawiera cyfrę
    if not re.search(r'[0-9]', password):
        return False
    
    # Sprawdzenie czy zawiera znak specjalny
    if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    
    return True


def validate_pesel(pesel):
    """
    Walidacja numeru PESEL
    """
    if not pesel:
        return False
    
    # Sprawdzenie czy PESEL składa się z 11 cyfr
    if not pesel.isdigit() or len(pesel) != 11:
        return False
    
    # Sprawdzenie sumy kontrolnej
    weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3, 1]
    control_sum = sum(int(pesel[i]) * weights[i] for i in range(11))
    
    return control_sum % 10 == 0


def validate_date(date_str, format_str='%Y-%m-%d'):
    """
    Walidacja daty
    """
    if not date_str:
        return False
    
    try:
        datetime.strptime(date_str, format_str)
        return True
    except ValueError:
        return False


def validate_time(time_str, format_str='%H:%M'):
    """
    Walidacja czasu
    """
    if not time_str:
        return False
    
    try:
        datetime.strptime(time_str, format_str)
        return True
    except ValueError:
        return False


def validate_age(birth_date, min_age=0, max_age=150):
    """
    Walidacja wieku
    """
    if not birth_date:
        return False
    
    if isinstance(birth_date, str):
        try:
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
        except ValueError:
            return False
    
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    
    return min_age <= age <= max_age


def validate_phone(phone):
    """
    Walidacja numeru telefonu
    """
    if not phone:
        return False
    
    # Usunięcie białych znaków i innych separatorów
    cleaned_phone = re.sub(r'[\s\-\+\.\(\)]', '', phone)
    
    # Numer powinien mieć między 9 a 15 cyfr
    if len(cleaned_phone) < 9 or len(cleaned_phone) > 15:
        return False
    
    # Sprawdzenie czy składa się tylko z cyfr
    if not cleaned_phone.isdigit():
        return False
    
    return True


def validate_postal_code(postal_code, country='PL'):
    """
    Walidacja kodu pocztowego
    """
    if not postal_code:
        return False
    
    # Usunięcie białych znaków
    cleaned_postal_code = postal_code.strip()
    
    if country == 'PL':
        # Polski kod pocztowy: 00-000
        return bool(re.match(r'^\d{2}-\d{3}$', cleaned_postal_code))
    else:
        # Ogólny wzorzec dla kodów pocztowych
        return bool(re.match(r'^[A-Za-z0-9\s-]+$', cleaned_postal_code))


def validate_not_empty(value):
    """
    Sprawdzenie czy wartość nie jest pusta
    """
    if value is None:
        return False
    
    if isinstance(value, str) and value.strip() == '':
        return False
    
    return True


def validate_length(value, min_length=1, max_length=None):
    """
    Walidacja długości tekstu
    """
    if not validate_not_empty(value):
        return False
    
    if not isinstance(value, str):
        value = str(value)
    
    if len(value) < min_length:
        return False
    
    if max_length is not None and len(value) > max_length:
        return False
    
    return True


def validate_decimal(value, min_value=None, max_value=None):
    """
    Walidacja liczby dziesiętnej
    """
    if value is None:
        return False
    
    try:
        decimal_value = float(value)
    except (ValueError, TypeError):
        return False
    
    if min_value is not None and decimal_value < min_value:
        return False
    
    if max_value is not None and decimal_value > max_value:
        return False
    
    return True