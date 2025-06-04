"""
Skrypt inicjalizujący bazę danych z przykładowymi danymi.
Uruchom: python -m app.init_db
"""
import os
import sys
from datetime import datetime, timedelta
import random
import string

# Add the parent directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import the app and models
from app import create_app, db
from models.pacjent import Pacjent
from models.lekarz import Lekarz
from models.usluga import Usluga
from models.termin import Termin
from models.wizyta import Wizyta, WizytaUsluga
from models.platnosc import Platnosc, MetodaPlatnosci

def generate_random_string(length=8):
    """Generuje losowy ciąg znaków o podanej długości."""
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))

def generate_random_pesel():
    """Generuje losowy numer PESEL."""
    # Prosta implementacja generująca losowy 11-cyfrowy numer
    return ''.join(str(random.randint(0, 9)) for _ in range(11))

def generate_random_phone():
    """Generuje losowy numer telefonu."""
    return f"+48{random.randint(100000000, 999999999)}"

def generate_random_date(start_date, end_date):
    """Generuje losową datę z podanego zakresu."""
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + timedelta(days=random_number_of_days)

def create_sample_data():
    """Tworzy przykładowe dane w bazie danych."""
    # Czyszczenie istniejących danych
    print("Czyszczenie istniejących danych...")
    meta = db.metadata
    for table in reversed(meta.sorted_tables):
        print(f'Usuwanie danych z tabeli {table}')
        db.session.execute(table.delete())
    db.session.commit()
    
    print("Tworzenie przykładowych danych...")
    
    # Lista specjalizacji lekarskich
    specjalizacje = [
        'Stomatolog ogólny', 'Ortodonta', 'Chirurg stomatologiczny',
        'Periodontolog', 'Protetyk', 'Endodonta', 'Stomatolog dziecięcy'
    ]
    
    # Lista miast i ulic do generowania adresów
    miasta = ['Warszawa', 'Kraków', 'Wrocław', 'Poznań', 'Gdańsk', 'Szczecin', 'Bydgoszcz', 'Lublin', 'Białystok', 'Katowice']
    ulice = ['Mazowiecka', 'Krakowskie Przedmieście', 'Nowy Świat', 'Marszałkowska', 'Jagiellońska', 
             'Grunwaldzka', 'Piłsudskiego', 'Słowackiego', 'Mickiewicza', 'Sienkiewicza']
    
    # Tworzenie przykładowych lekarzy (10 lekarzy)
    lekarze = []
    for i in range(1, 11):
        imie = random.choice(['Anna', 'Piotr', 'Magdalena', 'Marek', 'Agnieszka', 'Krzysztof', 'Ewa', 'Tomasz', 'Joanna', 'Michał'])
        nazwisko = random.choice(['Nowak', 'Kowalski', 'Wiśniewska', 'Wójcik', 'Kowalczyk', 'Kamińska', 'Lewandowska', 'Zielińska', 'Szymańska', 'Woźniak'])
        
        lekarz = {
            'imie': imie,
            'nazwisko': nazwisko,
            'email': f"{imie[0].lower()}.{nazwisko.lower()}{i}@przychodnia.pl",
            'haslo': 'Lekarz123!',
            'telefon': generate_random_phone(),
            'specjalizacja': random.choice(specjalizacje),
            'opis': f"Specjalista {random.choice(specjalizacje).lower()} z {random.randint(3, 20)}-letnim doświadczeniem. "
                   f"Absolwent{'ka' if imie[-1] == 'a' else ''} {random.choice(['Uniwersytetu Medycznego w Warszawie', 'Collegium Medicum UJ', 'Gdańskiego Uniwersytetu Medycznego', 'Śląskiego Uniwersytetu Medycznego'])}.",
            'aktywny': random.choice([True, True, True, False])  # 75% szans na aktywnego lekarza
        }
        lekarze.append(lekarz)

    # Tworzenie przykładowych usług (15 usług)
    uslugi = [
        {'nazwa': 'Konsultacja stomatologiczna', 'cena': 150.00, 'czas_trwania': 30},
        {'nazwa': 'Leczenie próchnicy (1 ząb)', 'cena': 200.00, 'czas_trwania': 45},
        {'nazwa': 'Wybielanie zębów - 1 łuk', 'cena': 500.00, 'czas_trwania': 60},
        {'nazwa': 'Wybielanie zębów - 2 łuki', 'cena': 800.00, 'czas_trwania': 90},
        {'nazwa': 'Leczenie kanałowe (1 kanał)', 'cena': 800.00, 'czas_trwania': 60},
        {'nazwa': 'Leczenie kanałowe (2-3 kanały)', 'cena': 1200.00, 'czas_trwania': 90},
        {'nazwa': 'Ekstrakcja zęba prosta', 'cena': 250.00, 'czas_trwania': 30},
        {'nazwa': 'Ekstrakcja zęba chirurgiczna', 'cena': 450.00, 'czas_trwania': 60},
        {'nazwa': 'Leczenie ortodontyczne - konsultacja', 'cena': 250.00, 'czas_trwania': 60},
        {'nazwa': 'Zakładanie aparatu stałego', 'cena': 2500.00, 'czas_trwania': 120},
        {'nazwa': 'Wizyta kontrolna aparatu', 'cena': 200.00, 'czas_trwania': 30},
        {'nazwa': 'Skaling naddziąsłowy', 'cena': 200.00, 'czas_trwania': 45},
        {'nazwa': 'Piaskowanie zębów', 'cena': 150.00, 'czas_trwania': 30},
        {'nazwa': 'Lakierowanie zębów', 'cena': 120.00, 'czas_trwania': 20},
        {'nazwa': 'Leczenie nadwrażliwości (1 ząb)', 'cena': 100.00, 'czas_trwania': 15},
        {'nazwa': 'Konsultacja protetyczna', 'cena': 200.00, 'czas_trwania': 45},
        {'nazwa': 'Korona porcelanowa', 'cena': 2000.00, 'czas_trwania': 60},
        {'nazwa': 'Most porcelanowy (na 1 ząb)', 'cena': 2500.00, 'czas_trwania': 90}
    ]

    # Tworzenie przykładowych pacjentów (50 pacjentów)
    pacjenci = []
    imiona_mezczyzn = ['Jan', 'Piotr', 'Andrzej', 'Krzysztof', 'Stanisław', 'Tomasz', 'Paweł', 'Marcin', 'Michał', 'Marek']
    imiona_kobiet = ['Anna', 'Maria', 'Katarzyna', 'Małgorzata', 'Agnieszka', 'Krystyna', 'Barbara', 'Ewa', 'Elżbieta', 'Zofia']
    nazwiska = ['Nowak', 'Kowalski', 'Wiśniewski', 'Wójcik', 'Kowalczyk', 'Kamiński', 'Lewandowski', 'Zieliński', 'Szymański', 'Woźniak']
    
    for i in range(1, 51):
        if random.choice([True, False]):  # 50% szans na kobietę
            imie = random.choice(imiona_kobiet)
            plec = 'K'
        else:
            imie = random.choice(imiona_mezczyzn)
            plec = 'M'
            
        nazwisko = random.choice(nazwiska)
        data_urodzenia = generate_random_date(datetime(1950, 1, 1), datetime(2010, 12, 31))
        pesel = generate_random_pesel()
        
        pacjent = {
            'imie': imie,
            'nazwisko': nazwisko,
            'email': f"{imie[0].lower()}.{nazwisko.lower()}{i}@example.com",
            'haslo': 'Haslo123!',
            'telefon': generate_random_phone(),
            'data_urodzenia': data_urodzenia.strftime('%Y-%m-%d'),
            'adres': f"ul. {random.choice(ulice)} {random.randint(1, 200)}/{random.randint(1, 50) if random.random() > 0.7 else ''}".strip(),
            'kod_pocztowy': f"{random.randint(10, 99)}-{random.randint(100, 999)}",
            'miasto': random.choice(miasta),
            'kraj': 'Polska',
            'pesel': pesel,
            'aktywny': random.choice([True, True, True, False]),  # 75% szans na aktywnego pacjenta
            'email_zweryfikowany': random.choice([True, True, False])  # 66% szans na zweryfikowany email
        }
        pacjenci.append(pacjent)
    
    # Funkcja do tworzenia obiektów w bazie danych z obsługą duplikatów
    def create_objects(model_class, data_list, unique_fields=[], **kwargs):
        """Tworzy obiekty w bazie danych z obsługą duplikatów."""
        objects = []
        for data in data_list:
            try:
                # Sprawdź, czy obiekt już istnieje
                if unique_fields:
                    filter_conditions = {field: data[field] for field in unique_fields}
                    existing = model_class.query.filter_by(**filter_conditions).first()
                    if existing:
                        objects.append(existing)
                        continue
                
                # Jeśli nie istnieje, utwórz nowy obiekt
                obj = model_class(**{**data, **kwargs})
                if hasattr(obj, 'set_password') and 'haslo' in data:
                    obj.set_password(data['haslo'])
                db.session.add(obj)
                objects.append(obj)
            except Exception as e:
                print(f"Błąd podczas tworzenia obiektu {model_class.__name__}: {e}")
                db.session.rollback()
        
        try:
            db.session.commit()
        except Exception as e:
            print(f"Błąd podczas zatwierdzania zmian w bazie danych: {e}")
            db.session.rollback()
            raise
            
        return objects
    
    # Tworzenie lekarzy w bazie danych
    print("Tworzenie lekarzy...")
    db_lekarze = create_objects(Lekarz, lekarze, ['email'])
    
    # Tworzenie usług w bazie danych
    print("Tworzenie usług...")
    db_uslugi = create_objects(Usluga, uslugi, ['nazwa'])
    
    # Tworzenie pacjentów w bazie danych
    print("Tworzenie pacjentów...")
    db_pacjenci = create_objects(Pacjent, pacjenci, ['email', 'pesel'])
    
    # Generowanie dostępnych terminów dla każdego lekarza na najbliższe 30 dni
    print("Generowanie dostępnych terminów...")
    dzisiaj = datetime.now()
    for lekarz in db_lekarze:
        # Każdy lekarz ma różną dostępność w tygodniu
        dni_tygodnia = random.sample(range(7), random.randint(3, 6))  # 3-6 dni w tygodniu
        godziny_pracy = range(8, 16)  # Godziny pracy 8:00-16:00
        
        for dni_dodatnie in range(30):  # Następne 30 dni
            data = dzisiaj + timedelta(days=dni_dodatnie)
            if data.weekday() in dni_tygodnia:  # Tylko w wybrane dni tygodnia
                # Losowa liczba dostępnych terminów w ciągu dnia (1-5)
                liczba_terminow = random.randint(1, 5)
                godziny = sorted(random.sample(godziny_pracy, min(liczba_terminow, len(godziny_pracy))))
                
                for godzina in godziny:
                    # Losowa minuta (0, 15, 30, 45)
                    minuta = random.choice([0, 15, 30, 45])
                    czas_od = datetime(data.year, data.month, data.day, godzina, minuta)
                    czas_do = czas_od + timedelta(minutes=30)  # Standardowy czas wizyty 30 minut
                    
                    termin = Termin(
                        data=data.date(),
                        godzina_od=czas_od.time(),
                        godzina_do=czas_do.time(),
                        lekarz_id=lekarz.id,
                        dostepny=True
                    )
                    db.session.add(termin)
    
    db.session.commit()
    
    # Generowanie wizyt dla pacjentów
    print("Generowanie wizyt...")
    statusy_wizyt = ['ZAPLANOWANA', 'ZAKOŃCZONA', 'ANULOWANA', 'NIESTAWIL_SIE']
    
    for pacjent in db_pacjenci:
        # Każdy pacjent ma od 0 do 10 wizyt
        liczba_wizyt = random.randint(0, 10)
        for _ in range(liczba_wizyt):
            # Wybierz losowego lekarza
            lekarz = random.choice(db_lekarze)
            
            # Znajdź dostępny termin dla tego lekarza
            termin = Termin.query.filter_by(lekarz_id=lekarz.id, dostepny=True).order_by(db.func.random()).first()
            
            if not termin:
                continue  # Brak dostępnych terminów dla tego lekarza
            
            # Oznacz termin jako zajęty
            termin.dostepny = False
            
            # Losowy status wizyty
            status = random.choices(
                statusy_wizyt,
                weights=[0.6, 0.3, 0.05, 0.05],  # 60% zaplanowane, 30% zakończone, 5% anulowane, 5% nie stawił się
                k=1
            )[0]
            
            # Losowa data wizyty (od 90 dni wstecz do 30 dni w przód)
            data_wizyty = dzisiaj + timedelta(days=random.randint(-90, 30))
            
            # Utwórz wizytę
            wizyta = Wizyta(
                pacjent_id=pacjent.id,
                lekarz_id=lekarz.id,
                termin_id=termin.id,
                status=status,
                opis=f"Konsultacja lekarska - {lekarz.specjalizacja}",
                data_utworzenia=data_wizyty - timedelta(days=random.randint(1, 30)),
                data_modyfikacji=datetime.utcnow()
            )
            
            # Dodaj losowe usługi do wizyty (1-3 usługi)
            liczba_uslug = random.randint(1, 3)
            wybrane_uslugi = random.sample(db_uslugi, min(liczba_uslug, len(db_uslugi)))
            
            for usluga in wybrane_uslugi:
                wizyta.uslugi.append(WizytaUsluga(usluga=usluga, ilosc=1))
            
            # Jeśli wizyta jest zakończona, utwórz płatność
            if status == 'ZAKOŃCZONA':
                kwota = sum(usluga.cena * wu.ilosc for wu in wizyta.uslugi for usluga in [wu.usluga])
                
                # Pobierz lub utwórz metodę płatności
                metoda_nazwa = random.choice(['KARTA', 'GOTÓWKA', 'PRZELEW'])
                metoda = MetodaPlatnosci.query.filter_by(nazwa=metoda_nazwa).first()
                if not metoda:
                    metoda = MetodaPlatnosci(nazwa=metoda_nazwa, aktywna=True)
                    db.session.add(metoda)
                    db.session.commit()
                
                # Utwórz płatność
                platnosc = Platnosc(
                    kwota=kwota,
                    status='ZAPŁACONA',
                    data_platnosci=data_wizyty + timedelta(minutes=30),
                    metoda_platnosci_id=metoda.id
                )
                db.session.add(platnosc)
                db.session.flush()  # Pobierz ID płatności
                
                # Przypisz płatność do wizyty
                wizyta.platnosc_id = platnosc.id
            
            db.session.add(wizyta)
    
    db.session.commit()
    
    print("\nPrzykładowe dane zostały pomyślnie załadowane do bazy danych.")
    print(f"- Utworzono {len(db_lekarze)} lekarzy")
    print(f"- Utworzono {len(db_uslugi)} usług")
    print(f"- Utworzono {len(db_pacjenci)} pacjentów")
    print(f"- Wygenerowano {Termin.query.count()} dostępnych terminów")
    print(f"- Utworzono {Wizyta.query.count()} wizyt")
    print(f"- Zarejestrowano {Platnosc.query.count()} płatności")

def init_database():
    """Inicjalizuje bazę danych i wypełnia ją danymi testowymi."""
    app = create_app()
    with app.app_context():
        print("Inicjalizacja bazy danych...")
        try:
            # Nie usuwamy i nie tworzymy tabel, ponieważ używamy migracji
            # db.drop_all()
            # db.create_all()
            
            # Sprawdź, czy baza jest już wypełniona danymi
            if Lekarz.query.count() == 0:
                print("Tworzenie przykładowych danych...")
                create_sample_data()
                print("Inicjalizacja zakończona pomyślnie.")
            else:
                print("Baza danych zawiera już dane. Pomijam inicjalizację.")
        except Exception as e:
            print(f"Błąd podczas inicjalizacji bazy danych: {e}")
            import traceback
            traceback.print_exc()
            return False
    return True

if __name__ == '__main__':
    init_database()
