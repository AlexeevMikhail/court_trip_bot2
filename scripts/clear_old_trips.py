import sqlite3
from datetime import datetime

# Открываем соединение
conn = sqlite3.connect("court_tracking.db")
cursor = conn.cursor()

# Удалим все поездки, начавшиеся ДО 30 июня 2025 включительно
cutoff = datetime(2025, 6, 30, 23, 59, 59)

cursor.execute(
    "DELETE FROM trips WHERE datetime(start_datetime) <= ?",
    (cutoff.isoformat(),)
)

deleted = cursor.rowcount
conn.commit()
conn.close()

print(f"✅ Удалено {deleted} поездок, начавшихся до и включая 30.06.2025")
