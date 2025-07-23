import sqlite3
from datetime import datetime, date, time, timedelta

DB_PATH = 'court_tracking.db'
WORKDAY_START = time(9, 0)
WORKDAY_END   = time(18, 0)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # таблица пользователей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            user_id   INTEGER PRIMARY KEY,
            full_name TEXT      NOT NULL
        )
    ''')
    # таблица поездок
    cur.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER,
            organization_id   TEXT,
            organization_name TEXT,
            start_datetime    DATETIME,
            end_datetime      DATETIME,
            status            TEXT,
            FOREIGN KEY (user_id) REFERENCES employees(user_id)
        )
    ''')
    # глобальный флаг режима
    cur.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    # по умолчанию — рабочий режим
    cur.execute('''
        INSERT OR IGNORE INTO config (key, value)
        VALUES ('DEBUG_MODE', 'false')
    ''')
    conn.commit()
    conn.close()

def get_now() -> datetime:
    """Текущее время без секунд/микр."""
    return datetime.now().replace(second=0, microsecond=0)

def get_debug_mode() -> bool:
    """True = тестовый режим, False = рабочий."""
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT value FROM config WHERE key = 'DEBUG_MODE'"
    ).fetchone()
    conn.close()
    return bool(row and row[0].lower() == 'true')

def is_registered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    ok   = conn.execute(
        "SELECT 1 FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone() is not None
    conn.close()
    return ok

def adjust_to_work_hours(dt: datetime) -> datetime | None:
    """
    Приводим в рамки 09:00–18:00 (без учёта пятницы, там 16:45):
    - до 09:00 → 09:00
    - после 18:00 → None
    """
    if dt.weekday() >= 5:
        return None
    if dt.time() < WORKDAY_START:
        return datetime.combine(dt.date(), WORKDAY_START)
    if dt.time() <= WORKDAY_END:
        return dt
    return None

def save_trip_start(user_id: int, org_id: str, org_name: str) -> bool:
    """
    Сохраняет поездку. Если DEBUG_MODE=false — применяем рабочие часы.
    """
    now = get_now()

    # глобальный тестовый режим?
    if not get_debug_mode():
        now = adjust_to_work_hours(now)
        if not now:
            return False

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # нет ли уже in_progress
    cur.execute(
        "SELECT 1 FROM trips WHERE user_id = ? AND status = 'in_progress'",
        (user_id,)
    )
    if cur.fetchone():
        conn.close()
        return False

    cur.execute('''
        INSERT INTO trips
            (user_id, organization_id, organization_name, start_datetime, status)
        VALUES (?, ?, ?, ?, 'in_progress')
    ''', (user_id, org_id, org_name, now))
    conn.commit()
    conn.close()
    return True

def end_trip(user_id: int) -> bool:
    """Завершает in_progress поездку."""
    now = get_now()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute('''
        UPDATE trips
        SET end_datetime = ?, status = 'completed'
        WHERE user_id = ? AND status = 'in_progress'
    ''', (now, user_id))
    updated = cur.rowcount
    conn.commit()
    conn.close()
    return updated > 0

def close_expired_trips():
    """Автозакрытие по расписанию (Job из scheduler.py)."""
    now = get_now()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT id, start_datetime FROM trips WHERE status = 'in_progress'")
    rows = cur.fetchall()
    count = 0
    for trip_id, start_str in rows:
        start_dt = datetime.fromisoformat(start_str).replace(second=0, microsecond=0)
        end_dt   = start_dt + timedelta(minutes=1) if now <= start_dt else now
        cur.execute(
            "UPDATE trips SET end_datetime = ?, status = 'completed' WHERE id = ?",
            (end_dt, trip_id)
        )
        count += 1
    conn.commit()
    conn.close()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Авто-завершено {count} поездок.")
