import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE = os.path.join('database', 'vaccination.db')

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

# ================= USERS =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# ================= CENTRES =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS centres (
    centre_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    contact TEXT,
    avg_service_time INTEGER DEFAULT 3,
    staff_on_duty INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# ================= SLOTS =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS slots (
    slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    capacity INTEGER DEFAULT 0,
    vaccine TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (centre_id) REFERENCES centres(centre_id)
)
""")

# ================= BOOKINGS =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    status TEXT DEFAULT 'upcoming',
    booked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (slot_id) REFERENCES slots(slot_id)
)
""")

# ================= STAFF =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

# ================= RECORDS =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER UNIQUE NOT NULL,
    staff_id INTEGER NOT NULL,
    vaccine TEXT,
    batch_no TEXT,
    started_at DATETIME,
    finished_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id)
)
""")

# ================= INSERT ADMIN =================
admin_password = generate_password_hash("admin123")

cursor.execute("""
INSERT OR IGNORE INTO users (name, email, phone, password_hash, role)
VALUES (?, ?, ?, ?, ?)
""", (
    "System Admin",
    "admin@vaxcare.com",
    "9999999999",
    admin_password,
    "admin"
))

# ================= INSERT STAFF =================
staff_password = generate_password_hash("staff123")

cursor.execute("""
INSERT OR IGNORE INTO staff (name, email, password)
VALUES (?, ?, ?)
""", (
    "Nurse A",
    "nurse1@vaxcare.com",
    staff_password
))

conn.commit()
conn.close()

print("Database initialized successfully!")