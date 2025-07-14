import sqlite3
from datetime import datetime

DB_PATH = "court_tracking.db"

def delete_trips_on_date(target_date_str: str):
    """
    Удаляет из таблицы trips все поездки, у которых дата старта равна target_date.
    Формат target_date_str: 'YYYY-MM-DD'
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM trips
        WHERE date(start_datetime) = ?
    """, (target_date_str,))

    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"✅ Удалено {deleted} поездок за {target_date_str}")

if __name__ == "__main__":
    # Указываем дату 1 июля 2025 в формате ISO
    delete_trips_on_date("2025-07-01")
