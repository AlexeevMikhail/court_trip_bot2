from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.database import close_expired_trips

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="Europe/Paris")
    # Пн–Чт в 18:00
    scheduler.add_job(
        close_expired_trips,
        trigger="cron",
        day_of_week="mon-thu",
        hour=18, minute=0
    )
    # Пт 16:45
    scheduler.add_job(
        close_expired_trips,
        trigger="cron",
        day_of_week="fri",
        hour=16, minute=45
    )
    scheduler.start()
    print("✅ Планировщик успешно запущен.")
