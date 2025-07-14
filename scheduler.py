from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.database import close_expired_trips
import pytz

# Используем pytz‑зону, чтобы APScheduler не ругался на отсутствие normalize()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=MOSCOW_TZ)

    # Пн–Чт в 18:00 (московское время)
    scheduler.add_job(
        close_expired_trips,
        trigger=CronTrigger(day_of_week='mon-thu', hour=18, minute=0, timezone=MOSCOW_TZ),
        id='close_trips_mon_thu',
        replace_existing=True,
    )
    print("📆 Задача автозакрытия поездок Пн–Чт в 18:00 добавлена.")

    # Пт в 16:45 (московское время)
    scheduler.add_job(
        close_expired_trips,
        trigger=CronTrigger(day_of_week='fri', hour=16, minute=45, timezone=MOSCOW_TZ),
        id='close_trips_fri',
        replace_existing=True,
    )
    print("📆 Задача автозакрытия поездок Пт в 16:45 добавлена.")

    scheduler.start()
    print("✅ Планировщик успешно запущен.")
