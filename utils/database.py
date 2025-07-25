import sqlite3
from datetime import datetime, date, time, timedelta
import os
from dotenv import load_dotenv

load_dotenv()  # читаем DEBUG_MODE из .env, если задано

DB_PATH = 'court_tracking.db'

# рабочие часы
WORKDAY_START       = time(9, 0)
WORKDAY_END_WEEKDAY = time(18, 0)
WORKDAY_END_FRIDAY  = time(16, 45)

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
    # флаг режима (для совместимости, если хотите менять из БД)
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
    True  — тестовый режим (любое время дня),
    False — рабочий (09–18, в пт 09–16:45).
    Сначала смотрим DEBUG_MODE из .env, если нет — из таблицы config.
    """
    env = os.getenv("DEBUG_MODE")
    if env is not None:
        return env.lower() in ("1","true","yes")
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT value FROM config WHERE key='DEBUG_MODE'"
    ).fetchone()
    conn.close()
    return bool(row and row[0].lower() == 'true')

def adjust_to_work_hours(dt: datetime) -> datetime | None:
    """
    В рабочем режиме:
      - до 09:00 → 09:00
      - после 18:00 (16:45 в пт) → None
      - сб/вс → None
    """
    wd = dt.weekday()
    if wd >= 5:
        return None
    start = WORKDAY_START
    end   = WORKDAY_END_FRIDAY if wd == 4 else WORKDAY_END_WEEKDAY
    if dt.time() < start:
        return datetime.combine(dt.date(), start)
    if dt.time() <= end:
        return dt
    return None

def save_trip_start(user_id: int, org_id: str, org_name: str) -> datetime | None:
    """
    Сохраняет новую поездку.
    Возвращает реальное datetime, записанное в БД (скорректированное или текущее),
    или None, если не получилось.
    """
    raw_now = get_now()
    debug   = get_debug_mode()

    if not debug:
        real_now = adjust_to_work_hours(raw_now)
        if not real_now:
            return None
    else:
        real_now = raw_now

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # проверяем, нет ли уже in_progress
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
    ''', (user_id, org_id, org_name, real_now))
    conn.commit()
    conn.close()
    return real_now

def end_trip_local(user_id: int) -> tuple[bool, datetime]:
    """
    Завершает in_progress поездку в БД.
    Возвращает (успех, время окончания).
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
    return ok, now

def fetch_last_completed(user_id: int) -> tuple[str, datetime]:
    """
    Берёт последнюю только что закрытую поездку.
    """
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
            from datetime import datetime as _dt
            start_dt = _dt.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
    return org_name, start_dt

def close_expired_trips_and_log():
    """
    Auto‑закрытие и параллельно отправка в Google Sheets.
    """
    from core.sheets import end_trip_in_sheet
    now   = get_now()
    debug = get_debug_mode()
    conn  = sqlite3.connect(DB_PATH)
    cur   = conn.cursor()

    # забираем все незавершённые
    cur.execute("SELECT id, user_id, organization_name, start_datetime FROM trips WHERE status = 'in_progress'")
    rows = cur.fetchall()
    count = 0

    for trip_id, user_id, org_name, start_str in rows:
        # расчёт end_dt
        raw_start = datetime.fromisoformat(start_str) if isinstance(start_str, str) else start_str
        if not debug:
            wd = raw_start.weekday()
            boundary = datetime.combine(raw_start.date(),
                        WORKDAY_END_FRIDAY if wd == 4 else WORKDAY_END_WEEKDAY)
            end_dt = boundary if now >= boundary else now
        else:
            end_dt = now

        # обновляем БД
        cur.execute(
            "UPDATE trips SET end_datetime = ?, status = 'completed' WHERE id = ?",
            (end_dt, trip_id)
        )
        if cur.rowcount:
            count += 1
            # подтягиваем ФИО
            c2 = conn.cursor()
            full = c2.execute(
                "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            # расчёт длительности
            duration = end_dt - raw_start
            # и заливаем в Google
            try:
                end_trip_in_sheet(full, org_name, raw_start, end_dt, duration)
            except Exception as e:
                print(f"[scheduler] Error logging to Google: {e}")

    conn.commit()
    conn.close()
    print(f"[db ] [{now.strftime('%Y-%m-%d %H:%M')}] Авто‑завершено {count} поездок.")
