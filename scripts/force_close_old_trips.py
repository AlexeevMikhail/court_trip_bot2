import sqlite3
from datetime import datetime
import pytz

DB_PATH = 'court_tracking.db'
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Получаем текущее время в МСК
now = datetime.now(pytz.utc).astimezone(MOSCOW_TZ)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Закрываем все незавершённые поездки
cursor.execute('''
    UPDATE trips
    SET end_datetime = ?, status = 'completed'
    WHERE status = 'in_progress'
''', (now.isoformat(),))

affected = cursor.rowcount
conn.commit()
conn.close()

print(f"✅ Завершено {affected} незавершённых поездок на {now.strftime('%d.%m.%Y %H:%M')}.")

