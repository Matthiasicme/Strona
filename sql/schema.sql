-- Tworzenie schematu bazy danych dla systemu rejestracji pacjenta stomatologicznego

-- Tabela pacjentów
CREATE TABLE pacjent (
    id SERIAL PRIMARY KEY,
    imie VARCHAR(50) NOT NULL,
    nazwisko VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    haslo VARCHAR(100) NOT NULL,
    telefon VARCHAR(20) NOT NULL,
    data_utworzenia TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabela lekarzy (stomatologów)
CREATE TABLE lekarz (
    id SERIAL PRIMARY KEY,
    imie VARCHAR(50) NOT NULL,
    nazwisko VARCHAR(50) NOT NULL,
    specjalizacja VARCHAR(100) NOT NULL,
    opis TEXT,
    aktywny BOOLEAN NOT NULL DEFAULT TRUE,
    data_utworzenia TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabela terminów (sloty czasowe)
CREATE TABLE termin (
    id SERIAL PRIMARY KEY,
    data DATE NOT NULL,
    godzina_od TIME NOT NULL,
    godzina_do TIME NOT NULL,
    dostepny BOOLEAN NOT NULL DEFAULT TRUE,
    lekarz_id INTEGER REFERENCES lekarz(id) ON DELETE CASCADE,
    CONSTRAINT uq_termin_lekarz UNIQUE (data, godzina_od, lekarz_id)
);

-- Tabela metod płatności
CREATE TABLE metoda_platnosci (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(50) NOT NULL,
    aktywna BOOLEAN NOT NULL DEFAULT TRUE
);

-- Tabela płatności
CREATE TABLE platnosc (
    id SERIAL PRIMARY KEY,
    kwota DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'OCZEKUJĄCA',
    metoda_platnosci_id INTEGER REFERENCES metoda_platnosci(id),
    data_platnosci TIMESTAMP,
    data_utworzenia TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_status CHECK (status IN ('OCZEKUJĄCA', 'ZATWIERDZONA', 'ODRZUCONA', 'ANULOWANA'))
);

-- Tabela wizyt
CREATE TABLE wizyta (
    id SERIAL PRIMARY KEY,
    pacjent_id INTEGER NOT NULL REFERENCES pacjent(id) ON DELETE CASCADE,
    lekarz_id INTEGER NOT NULL REFERENCES lekarz(id) ON DELETE CASCADE,
    termin_id INTEGER NOT NULL REFERENCES termin(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'ZAPLANOWANA',
    platnosc_id INTEGER REFERENCES platnosc(id),
    opis TEXT,
    data_utworzenia TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_modyfikacji TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_wizyta_status CHECK (status IN ('ZAPLANOWANA', 'POTWIERDZONA', 'ZAKOŃCZONA', 'ANULOWANA'))
);

-- Tabela powiadomień email
CREATE TABLE email (
    id SERIAL PRIMARY KEY,
    wizyta_id INTEGER NOT NULL REFERENCES wizyta(id) ON DELETE CASCADE,
    temat VARCHAR(255) NOT NULL,
    tresc TEXT NOT NULL,
    data_wyslania TIMESTAMP
);

-- Tabela powiadomień SMS
CREATE TABLE sms (
    id SERIAL PRIMARY KEY,
    wizyta_id INTEGER NOT NULL REFERENCES wizyta(id) ON DELETE CASCADE,
    tresc VARCHAR(160) NOT NULL,
    data_wyslania TIMESTAMP
);

-- Tabela podsumowań wizyt
CREATE TABLE podsumowanie (
    id SERIAL PRIMARY KEY,
    wizyta_id INTEGER NOT NULL REFERENCES wizyta(id) ON DELETE CASCADE,
    szczegoly TEXT NOT NULL,
    zalecenia TEXT,
    nastepna_wizyta_zalecana BOOLEAN DEFAULT FALSE,
    data_utworzenia TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabela usług stomatologicznych
CREATE TABLE usluga (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(100) NOT NULL,
    opis TEXT,
    cena DECIMAL(10, 2) NOT NULL,
    czas_trwania INTEGER NOT NULL, -- w minutach
    aktywna BOOLEAN NOT NULL DEFAULT TRUE
);

-- Tabela łącząca wizyty z usługami
CREATE TABLE wizyta_usluga (
    wizyta_id INTEGER NOT NULL REFERENCES wizyta(id) ON DELETE CASCADE,
    usluga_id INTEGER NOT NULL REFERENCES usluga(id) ON DELETE CASCADE,
    ilosc INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (wizyta_id, usluga_id)
);

-- Tabela historii leczenia zębów pacjenta (diagram dentystyczny)
CREATE TABLE diagram_dentystyczny (
    id SERIAL PRIMARY KEY,
    pacjent_id INTEGER NOT NULL REFERENCES pacjent(id) ON DELETE CASCADE,
    numer_zeba INTEGER NOT NULL CHECK (numer_zeba BETWEEN 11 AND 48),
    status VARCHAR(50) NOT NULL,
    opis TEXT,
    data_modyfikacji TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_pacjent_zab UNIQUE (pacjent_id, numer_zeba)
);

-- Indeksy poprawiające wydajność
CREATE INDEX idx_wizyta_pacjent ON wizyta(pacjent_id);
CREATE INDEX idx_wizyta_lekarz ON wizyta(lekarz_id);
CREATE INDEX idx_wizyta_termin ON wizyta(termin_id);
CREATE INDEX idx_wizyta_status ON wizyta(status);
CREATE INDEX idx_termin_lekarz ON termin(lekarz_id);
CREATE INDEX idx_termin_data ON termin(data);
CREATE INDEX idx_diagram_pacjent ON diagram_dentystyczny(pacjent_id);

-- Zmodyfikowane fragmenty schematu:
CREATE TABLE integracja (
    id SERIAL PRIMARY KEY,
    nazwa VARCHAR(50) NOT NULL, -- np. "ZnanyLekarz"
    ostatnia_synchronizacja TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'AKTYWNA'
);

CREATE TABLE historia_medyczna (
    id SERIAL PRIMARY KEY,
    pacjent_id INTEGER NOT NULL REFERENCES pacjent(id),
    data_wpisu TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    opis TEXT NOT NULL,
    zalecenia TEXT
);