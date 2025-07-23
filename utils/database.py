import sqlite3
from datetime import datetime, date, time, timedelta

DEBUG_MODE = False  # False — рабочий режим, True — тестовый
DB_PATH = 'court_tracking.db'

def get_now() -> datetime:
    # Системное время, обрезанное до минут
    return datetime.now().replace(second=0, microsecond=0)

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
    res = cursor.fetchone()
    conn.close()
    return bool(res)

WORKDAY_START = time(9, 0)
WORKDAY_END   = time(18, 0)

def is_workday(d: date) -> bool:
    return d.weekday() < 5  # 0–4 → пн–пт

def adjust_to_work_hours(dt: datetime) -> datetime | None:
    if DEBUG_MODE:
        return dt
    if not is_workday(dt.date()):
        return None
    if dt.time() < WORKDAY_START:
        # в начале рабочего дня
        return datetime.combine(dt.date(), WORKDAY_START)
    if dt.time() <= WORKDAY_END:
        # в промежутке
        return dt
    # после рабочего дня — запрещено
    return None

def save_trip_start(user_id: int, org_id: str, org_name: str) -> bool:
    now = adjust_to_work_hours(get_now())
    if not now:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM trips WHERE user_id = ? AND status = 'in_progress'",
        (user_id,)
    )
    if cursor.fetchone():
        conn.close()
        return False

    cursor.execute('''
        INSERT INTO trips
            (user_id, organization_id, organization_name, start_datetime, status)
        VALUES (?, ?, ?, ?, 'in_progress')
    ''', (user_id, org_id, org_name, now))
    conn.commit()
    conn.close()
    return True

def end_trip(user_id: int) -> bool:
    now = get_now()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE trips
        SET end_datetime = ?, status = 'completed'
        WHERE user_id = ? AND status = 'in_progress'
    ''', (now, user_id))
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    return updated > 0

def close_expired_trips():
    now = get_now()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, start_datetime
        FROM trips
        WHERE status = 'in_progress'
    ''')
    rows = cursor.fetchall()
    count = 0
    for trip_id, start_str in rows:
        start_dt = datetime.fromisoformat(start_str).replace(second=0, microsecond=0)
        if now <= start_dt:
            end_dt = start_dt + timedelta(minutes=1)
        else:
            end_dt = now
        cursor.execute('''
            UPDATE trips
            SET end_datetime = ?, status = 'completed'
            WHERE id = ?
        ''', (end_dt, trip_id))
        count += 1
    conn.commit()
    conn.close()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Авто-завершено {count} поездок.")
