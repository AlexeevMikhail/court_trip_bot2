from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from utils.database import close_expired_trips_and_log

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=MOSCOW_TZ)

    scheduler.add_job(
        close_expired_trips_and_log,
        trigger=CronTrigger(day_of_week='mon-thu', hour=18, minute=0, timezone=MOSCOW_TZ),
        id='close_trips_mon_thu', replace_existing=True
    )
    print("📆 Задача автозавершения Пн–Чт в 18:00 добавлена.")

    scheduler.add_job(
        close_expired_trips_and_log,
        trigger=CronTrigger(day_of_week='fri', hour=16, minute=45, timezone=MOSCOW_TZ),
        id='close_trips_fri', replace_existing=True
    )
    print("📆 Задача автозавершения Пт в 16:45 добавлена.")

    scheduler.start()
    print("✅ Планировщик запущён.")
