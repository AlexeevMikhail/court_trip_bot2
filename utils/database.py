import sqlite3
from datetime import datetime, date, time, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = 'court_tracking.db'

# рабочие часы
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
    """
    True = тестовый режим (любой час),
    False = рабочий (09–18, в пт 09–16:45).
    Сначала проверяем переменную окружения, потом — config.
    """
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
    """
    Если не в тестовом режиме:
      - до 09:00 → ставим 09:00
      - после 18:00 (16:45 в пт) → запрещаем (None)
      - сб/вс → запрещаем (None)
    """
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

def save_trip_start(user_id: int, org_id: str, org_name: str) -> datetime | None:
    """
    Сохраняет новую поездку.
    В тестовом режиме — сохраняем сейчас.
    В рабочем — сначала корректируем время, возвращаем его.
    """
    raw = get_now()
    debug = get_debug_mode()
    if not debug:
        adj = adjust_to_work_hours(raw)
        if not adj:
            return None
        now = adj
    else:
        now = raw

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # нет ли уже незавершённой?
    cur.execute(
        "SELECT 1 FROM trips WHERE user_id = ? AND status = 'in_progress'",
        (user_id,)
    )
    if cur.fetchone():
        conn.close()
        return None

    cur.execute('''
        INSERT INTO trips
          (user_id, organization_id, organization_name, start_datetime, status)
        VALUES (?, ?, ?, ?, 'in_progress')
    ''', (user_id, org_id, org_name, now))
    conn.commit()
    conn.close()
    return now

def end_trip_local(user_id: int) -> tuple[bool, datetime | None]:
    """
    Завершает in_progress поездку в БД.
    Возвращает (успех, время завершения).
    """
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
    """
    Берёт последнюю только что закрытую поездку (org_name, start_dt).
    """
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute('''
        SELECT organization_name, start_datetime
        FROM trips
        WHERE user_id = ? AND status = 'completed'
        ORDER BY start_datetime DESC LIMIT 1
    ''', (user_id,))
    org, st = cur.fetchone()
    conn.close()
    if isinstance(st, str):
        try:
            st = datetime.fromisoformat(st)
        except:
            st = datetime.strptime(st, "%Y-%m-%d %H:%M:%S")
    return org, st

def close_expired_trips():
    """
    Авто‑закрытие поездок (Job из scheduler.py).
    """
    now   = get_now()
    debug = get_debug_mode()
    conn  = sqlite3.connect(DB_PATH)
    cur   = conn.cursor()
    cur.execute("SELECT id, start_datetime FROM trips WHERE status = 'in_progress'")
    rows = cur.fetchall()
    cnt = 0
    for trip_id, start_str in rows:
        sd = datetime.fromisoformat(start_str)
        if not debug:
            wd = sd.weekday()
            end = WORKDAY_END_FRIDAY if wd == 4 else WORKDAY_END_WEEK
            boundary = datetime.combine(sd.date(), end)
            end_dt = boundary if now >= boundary else now
        else:
            end_dt = now
        cur.execute(
            "UPDATE trips SET end_datetime = ?, status = 'completed' WHERE id = ?",
            (end_dt, trip_id)
        )
        cnt += 1
    conn.commit()
    conn.close()
    print(f"[db ] [{now.strftime('%Y-%m-%d %H:%M')}] Авто‑закрыто {cnt} поездок.")
