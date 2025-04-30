CREATE TABLE patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    pesel TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    visit_date DATE NOT NULL,
    visit_time TIME NOT NULL
);
