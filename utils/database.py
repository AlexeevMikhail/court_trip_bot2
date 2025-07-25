import sqlite3
import os
from datetime import datetime, date, time, timedelta
from dotenv import load_dotenv

load_dotenv()  # to pick up DEBUG_MODE from .env

DB_PATH = 'court_tracking.db'
WORKDAY_START    = time(9, 0)
WORKDAY_END_WD   = time(18, 0)
WORKDAY_END_FRI  = time(16, 45)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            user_id    INTEGER PRIMARY KEY,
            full_name  TEXT      NOT NULL
        )
    ''')
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
    cur.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    # default to “working” mode
    cur.execute('''
        INSERT OR IGNORE INTO config (key, value)
        VALUES ('DEBUG_MODE', 'false')
    ''')
    conn.commit()
    conn.close()

def get_now() -> datetime:
    return datetime.now().replace(second=0, microsecond=0)

def get_debug_mode() -> bool:
    # 1) check env var
    env = os.getenv("DEBUG_MODE")
    if env is not None:
        return env.lower() in ("1","true","yes")
    # 2) fallback to DB
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT value FROM config WHERE key='DEBUG_MODE'"
    ).fetchone()
    conn.close()
    return bool(row and row[0].lower() == 'true')

def is_registered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    exists = conn.execute(
        "SELECT 1 FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone() is not None
    conn.close()
    return exists

def adjust_to_work_hours(dt: datetime) -> datetime | None:
    wd = dt.weekday()
    if wd >= 5:  # Sat/Sun
        return None
    start = WORKDAY_START
    end   = WORKDAY_END_FRI if wd == 4 else WORKDAY_END_WD
    if dt.time() < start:
        return datetime.combine(dt.date(), start)
    if dt.time() <= end:
        return dt
    return None

def save_trip_start(user_id: int, org_id: str, org_name: str) -> bool:
    now   = get_now()
    debug = get_debug_mode()
    if not debug:
        now = adjust_to_work_hours(now)
        if not now:
            return False

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
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

def end_trip_local(user_id: int) -> tuple[bool, datetime]:
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
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute('''
        SELECT organization_name, start_datetime
        FROM trips
        WHERE user_id = ? AND status = 'completed'
        ORDER BY start_datetime DESC LIMIT 1
    ''', (user_id,))
    org, start = cur.fetchone()
    conn.close()
    if isinstance(start, str):
        try:
            start = datetime.fromisoformat(start)
        except:
            start = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    return org, start

def close_expired_trips():
    now   = get_now()
    debug = get_debug_mode()
    conn  = sqlite3.connect(DB_PATH)
    cur   = conn.cursor()
    cur.execute("SELECT id, start_datetime FROM trips WHERE status = 'in_progress'")
    rows  = cur.fetchall()
    cnt   = 0
    for tid, s in rows:
        sd = datetime.fromisoformat(s)
        if not debug:
            wd = sd.weekday()
            end = WORKDAY_END_FRI if wd == 4 else WORKDAY_END_WD
            boundary = datetime.combine(sd.date(), end)
            ed = boundary if now >= boundary else now
        else:
            ed = now
        cur.execute(
            "UPDATE trips SET end_datetime = ?, status = 'completed' WHERE id = ?",
            (ed, tid)
        )
        cnt += 1
    conn.commit()
    conn.close()
    print(f"[db ] [{now.strftime('%Y-%m-%d %H:%M')}] Auto‑closed {cnt} trips.")
