import sqlite3
import os
from datetime import datetime, date, time, timedelta
from dotenv import load_dotenv
from core.sheets import end_trip_in_sheet  # <-- теперь доступна синхронно

load_dotenv()

DB_PATH = 'court_tracking.db'
WORKDAY_START      = time(9, 0)
WORKDAY_END_WEEK   = time(18, 0)
WORKDAY_END_FRIDAY = time(16, 45)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # таблица пользователей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            user_id    INTEGER PRIMARY KEY,
            full_name  TEXT      NOT NULL
        )
    ''')
    # таблица поездок
    cur.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER,
            organization_id   TEXT,
            organization_name TEXT,
            start_datetime    DATETIME,
            end_datetime      DATETIME,
            status            TEXT,
            FOREIGN KEY(user_id) REFERENCES employees(user_id)
        )
    ''')
    # таблица конфигурации
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
    env = os.getenv("DEBUG_MODE")
    if env is not None:
        return env.lower() in ("1", "true", "yes")
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT value FROM config WHERE key='DEBUG_MODE'"
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
    wd = dt.weekday()  # 0–4 = Пн–Пт
    if wd >= 5:
        return None
    start = WORKDAY_START
    end   = WORKDAY_END_FRIDAY if wd == 4 else WORKDAY_END_WEEK
    if dt.time() < start:
        return datetime.combine(dt.date(), start)
    if dt.time() <= end:
        return dt
    return None

def save_trip_start(user_id: int, org_id: str, org_name: str) -> bool:
    raw = get_now()
    debug = get_debug_mode()
    now = raw if debug else adjust_to_work_hours(raw)
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

def end_trip_local(user_id: int) -> tuple[bool, datetime|None]:
    now = get_now()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute('''
        UPDATE trips
        SET end_datetime = ?, status = 'completed'
        WHERE user_id = ? AND status = 'in_progress'
    ''', (now, user_id))
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok, (now if ok else None)

def fetch_last_completed(user_id: int) -> tuple[str, datetime]:
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute('''
        SELECT organization_name, start_datetime
        FROM trips
        WHERE user_id = ? AND status = 'completed'
        ORDER BY start_datetime DESC LIMIT 1
    ''', (user_id,))
    org_name, start_dt = cur.fetchone()
    conn.close()
    if isinstance(start_dt, str):
        try:
            start_dt = datetime.fromisoformat(start_dt)
        except:
            start_dt = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
    return org_name, start_dt

def close_expired_trips():
    """
    Авто‑закрытие по расписанию — доводим in_progress
    до границы рабочего дня (или до now, если в DEBUG).
    После этого сразу дополняем строку в Google Sheets.
    """
    now   = get_now()
    debug = get_debug_mode()
    conn  = sqlite3.connect(DB_PATH)
    cur   = conn.cursor()

    # теперь сразу берём user_id и org_name вместе с id
    cur.execute("""
        SELECT id, user_id, organization_name, start_datetime
        FROM trips
        WHERE status = 'in_progress'
    """)
    rows = cur.fetchall()
    cnt = 0

    for trip_id, user_id, org_name, start_str in rows:
        # парсим время старта
        try:
            sd = datetime.fromisoformat(start_str)
        except ValueError:
            sd = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")

        # вычисляем конец
        if not debug:
            wd   = sd.weekday()
            endt = WORKDAY_END_FRIDAY if wd == 4 else WORKDAY_END_WEEK
            boundary = datetime.combine(sd.date(), endt)
            end_dt = boundary if now >= boundary else now
        else:
            end_dt = now

        # обновляем БД
        cur.execute(
            "UPDATE trips SET end_datetime = ?, status = 'completed' WHERE id = ?",
            (end_dt, trip_id)
        )
        if cur.rowcount > 0:
            # достаём ФИО
            user_cur = conn.cursor()
            user_cur.execute(
                "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
            )
            full_name = user_cur.fetchone()[0]

            # длительность
            duration = end_dt - sd

            # дополняем Google Sheets
            try:
                end_trip_in_sheet(full_name, org_name, sd, end_dt, duration)
            except Exception as e:
                print(f"[db][ERROR] end_trip_in_sheet failed for trip {trip_id}: {e}")

            cnt += 1

    conn.commit()
    conn.close()
    print(f"[db ] [{now.strftime('%Y-%m-%d %H:%M')}] Авто‑закрыто {cnt} поездок.")
