import sqlite3
from datetime import datetime

conn = sqlite3.connect("court_tracking.db")
cursor = conn.cursor()

cursor.execute('''
    SELECT id, user_id, organization_name, start_datetime, end_datetime, status
    FROM trips
    WHERE status = 'completed'
      AND (date(start_datetime) = '2025-06-30' OR date(end_datetime) = '2025-06-30')
    ORDER BY start_datetime
''')

rows = cursor.fetchall()
conn.close()

print("📋 Поездки, связанные с 30.06.2025:")
for row in rows:
    id_, user_id, org, start, end, status = row
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None
    delta = end_dt - start_dt if start_dt and end_dt else None

    print(f"ID: {id_} | Пользователь: {user_id} | {org}")
    print(f"    Старт: {start_dt}")
    print(f"    Конец: {end_dt}")
    if delta:
        print(f"    ⏱ Разница: {delta} {'❗' if delta.total_seconds() < 0 else ''}")
    else:
        print("    ⏱ Разница: нет данных")
    print("-" * 50)
