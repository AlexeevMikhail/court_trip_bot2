from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from utils.database import close_expired_trips

def start_scheduler():
    moscow_tz = pytz.timezone("Europe/Moscow")
    scheduler = AsyncIOScheduler(timezone=moscow_tz)

    # Пн–Чт в 18:00 по МСК
    scheduler.add_job(
        close_expired_trips,
        trigger=CronTrigger(day_of_week='mon-thu', hour=18, minute=0, timezone=moscow_tz)
    )

    # Пт в 16:45 по МСК
    scheduler.add_job(
        close_expired_trips,
        trigger=CronTrigger(day_of_week='fri', hour=16, minute=45, timezone=moscow_tz)
    )

    scheduler.start()
    print("✅ Планировщик успешно запущен.")
