import sqlite3
import pandas as pd

DB_PATH = "court_tracking.db"
TARGET_DATE = "2025-07-01"  # формат YYYY-MM-DD

def export_trips_on_date(target_date: str):
    # Подключаемся к БД
    conn = sqlite3.connect(DB_PATH)
    # Читаем в DataFrame
    df = pd.read_sql("""
        SELECT 
            t.id,
            t.user_id,
            e.full_name AS user_name,
            t.organization_name,
            t.start_datetime,
            t.end_datetime,
            t.status
        FROM trips t
        JOIN employees e ON t.user_id = e.user_id
        WHERE date(t.start_datetime) = ?
    """, conn, params=(target_date,))
    conn.close()

    if df.empty:
        print(f"⚠️ Нет поездок за {target_date}")
        return

    # Сохраняем в Excel
    output_file = f"trips_{target_date.replace('-', '')}.xlsx"
    df.to_excel(output_file, index=False)
    print(f"✅ Экспортировано {len(df)} поездок в {output_file}")

if __name__ == "__main__":
    export_trips_on_date(TARGET_DATE)
