import sqlite3

DB_PATH = "court_tracking.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Удаляем все поездки
cursor.execute("DELETE FROM trips")
conn.commit()
conn.close()

print("🧹 Все поездки успешно удалены. Сотрудники сохранены.")
