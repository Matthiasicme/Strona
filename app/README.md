# System Rejestracji Pacjentów - Backend

Backend systemu rejestracji pacjentów do gabinetu stomatologicznego.

## Wymagania systemowe

- Python 3.8+
- PostgreSQL 12+
- pip (Python package manager)

## Konfiguracja środowiska

1. Sklonuj repozytorium:
   ```bash
   git clone <repo-url>
   cd telemedycyna/backend
   ```

2. Utwórz i aktywuj wirtualne środowisko:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Na Windows: venv\Scripts\activate
   ```

3. Zainstaluj zależności:
   ```bash
   pip install -r requirements.txt
   ```

4. Skonfiguruj zmienne środowiskowe:
   - Skopiuj plik `.env.example` do `.env`
   - Zaktualizuj wartości w pliku `.env` zgodnie ze swoją konfiguracją

5. Zainicjuj bazę danych:
   ```bash
   flask db upgrade
   ```

## Uruchomienie serwera deweloperskiego

```bash
flask run --debug
```

Serwer będzie dostępny pod adresem: http://localhost:5000

## Rejestracja pacjenta

### 1. Wysyłanie formularza rejestracyjnego

**Endpoint:** `POST /api/auth/register/pacjent`

**Przykładowe dane:**
```json
{
  "imie": "Jan",
  "nazwisko": "Kowalski",
  "email": "jan.kowalski@example.com",
  "haslo": "SilneHaslo123!",
  "telefon": "+48123456789",
  "data_urodzenia": "1990-01-01",
  "adres": "ul. Przykładowa 123",
  "kod_pocztowy": "00-001",
  "miasto": "Warszawa",
  "kraj": "Polska",
  "pesel": "90010112345"
}
```

**Odpowiedź sukcesu (201):**
```json
{
  "status": "success",
  "message": "Konto zostało utworzone pomyślnie. Sprawdź swoją skrzynkę email, aby zweryfikować konto.",
  "id": 1,
  "email_verification_sent": true
}
```

### 2. Weryfikacja adresu email

Po rejestracji użytkownik otrzyma email z linkiem weryfikacyjnym. Kliknięcie w link spowoduje:
1. Weryfikację tokenu
2. Aktywację konta użytkownika
3. Przekierowanie na stronę sukcesu

**Przykładowy link weryfikacyjny:**
```
http://localhost:5000/api/auth/verify-email?token=<verification_token>&user_id=<user_id>
```

## Środowiska

- **Development**: `FLASK_ENV=development`
  - Włączony tryb debugowania
  - Szczegółowe logi
  - Automatyczne przeładowywanie kodu

- **Produkcja**: `FLASK_ENV=production`
  - Wyłączony tryb debugowania
  - Optymalizacje wydajnościowe
  - Bezpieczne ustawienia

## Testowanie

Aby uruchomić testy:

```bash
pytest
```

## Wdrażanie

1. Upewnij się, że wszystkie testy przechodzą
2. Zaktualizuj wersję w `setup.py`
3. Zbuduj i wypchnij nową wersję
4. Zaktualizuj środowisko produkcyjne

## Licencja

[MIT](LICENSE)
