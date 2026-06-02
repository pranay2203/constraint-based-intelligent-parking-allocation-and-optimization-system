import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "parking.db"
)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# SUPER ADMINS

cursor.execute("""
CREATE TABLE IF NOT EXISTS super_admins(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE,
    password TEXT
)
""")

# ADMIN CODES

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin_codes(
    code TEXT PRIMARY KEY,
    super_admin_email TEXT,
    zone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ADMINS

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE,
    password TEXT,
    zone TEXT,
    code TEXT
)
""")

# PARKING SLOTS

cursor.execute("""
CREATE TABLE IF NOT EXISTS parking_slots(
    slot TEXT PRIMARY KEY,
    vehicle_type TEXT,
    occupied INTEGER,
    zone TEXT,
    distance INTEGER,
    priority_reserved INTEGER,
    charging INTEGER
)
""")

# VEHICLE LOGS

cursor.execute("""
CREATE TABLE IF NOT EXISTS vehicle_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_no TEXT,
    vehicle_type TEXT,
    priority TEXT,
    slot TEXT,
    zone TEXT,
    entry_time TEXT,
    exit_time TEXT,
    status TEXT
)
""")

conn.commit()
conn.close()

print("Database Initialized Successfully")