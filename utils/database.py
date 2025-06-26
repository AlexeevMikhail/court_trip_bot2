import sqlite3
from datetime import datetime, time

DB_PATH = 'court_tracking.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            organization_id TEXT,
            organization_name TEXT,
            start_datetime DATETIME,
            end_datetime DATETIME,
            status TEXT,
            FOREIGN KEY (user_id) REFERENCES employees (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vacations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            start_date DATE,
            end_date DATE,
            FOREIGN KEY (user_id) REFERENCES employees (user_id)
        )
    ''')

    conn.commit()
    conn.close()

def is_registered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM employees WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_trip_start(user_id: int, org_id: str, org_name: str):
    now = adjust_to_work_hours(datetime.now())
    if not now:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверка на существующую активную поездку
    cursor.execute("SELECT 1 FROM trips WHERE user_id = ? AND status = 'in_progress'", (user_id,))
    if cursor.fetchone():
        conn.close()
        return False

    cursor.execute('''
        INSERT INTO trips (user_id, organization_id, organization_name, start_datetime, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, org_id, org_name, now, 'in_progress'))

    conn.commit()
    conn.close()
    return True

WORKDAY_START = time(9, 0)
WORKDAY_END = time(18, 0)

def is_workday(date: datetime.date) -> bool:
    return date.weekday() < 5

def adjust_to_work_hours(dt: datetime) -> datetime | None:
    if not is_workday(dt.date()):
        return None
    if dt.time() < WORKDAY_START:
        return datetime.combine(dt.date(), WORKDAY_START)
    elif dt.time() > WORKDAY_END:
        return datetime.combine(dt.date(), WORKDAY_END)
    return dt
