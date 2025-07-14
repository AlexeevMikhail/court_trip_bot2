import sqlite3

conn = sqlite3.connect("court_tracking.db")
cursor = conn.cursor()

cursor.execute('''
    UPDATE trips
    SET end_datetime = '2025-06-30T09:50:00+03:00'
    WHERE id = 23
''')

conn.commit()
conn.close()

print("✅ Запись ID 23 исправлена: end_datetime → 09:50")
