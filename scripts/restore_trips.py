import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "court_tracking.db"
EXCEL_PATH = "Отчёт_20250630_2249.xlsx"

# Загрузка Excel
df = pd.read_excel(EXCEL_PATH)

# Преобразуем дата + время в datetime
df["start_datetime"] = df.apply(
    lambda row: datetime.strptime(f"{row['Дата']} {row['Начало поездки']}", "%d.%m.%Y %H:%M"),
    axis=1
)
df["end_datetime"] = df.apply(
    lambda row: datetime.strptime(f"{row['Дата']} {row['Конец поездки']}", "%d.%m.%Y %H:%M"),
    axis=1
)

# Подключение к БД
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

restored = 0
not_found = []

for _, row in df.iterrows():
    full_name = row["ФИО"]
    org = row["Организация"]
    start = row["start_datetime"]
    end = row["end_datetime"]

    # Получаем user_id по ФИО
    cursor.execute("SELECT user_id FROM employees WHERE full_name = ?", (full_name,))
    result = cursor.fetchone()

    if result:
        user_id = result[0]

        # Вставка поездки, если такой записи ещё нет
        cursor.execute('''
            INSERT OR IGNORE INTO trips (user_id, organization_name, start_datetime, end_datetime)
            VALUES (?, ?, ?, ?)
        ''', (user_id, org, start.isoformat(), end.isoformat()))
        restored += 1
    else:
        not_found.append(full_name)

conn.commit()
conn.close()

print(f"✅ Восстановлено поездок: {restored}")
if not_found:
    print("❗ Не найдены в employees (ФИО):")
    for name in set(not_found):
        print(f" - {name}")
