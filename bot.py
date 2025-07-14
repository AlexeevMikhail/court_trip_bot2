# bot.py
import os
import time
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from handlers.commands import register_command, trip_command, return_command, report_command
from handlers.callbacks import organization_callback
from handlers.menu import handle_main_menu
from dotenv import load_dotenv
from keep_alive import keep_alive
from scheduler import start_scheduler

# Загружаем переменные окружения из .env
load_dotenv()

# Принудительно устанавливаем часовой пояс на Moscow
os.environ.setdefault("TZ", "Europe/Moscow")
time.tzset()

# Запускаем встроенный веб-сервер для health-checks
keep_alive()
time.sleep(3)

# Получаем токен
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("❌ BOT_TOKEN is missing")
    exit(1)

async def on_startup(app):
    print("🟢 Бот успешно запущен")

def main():
    # Если нужно, здесь можно раскомментировать инициализацию БД:
    # from utils.database import init_db
    # init_db()

    # Собираем приложение без встроенного JobQueue (мы используем APScheduler)
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .job_queue(None)
        .post_init(on_startup)
        .build()
    )

    # Регистрируем хендлеры
    app.add_handler(register_command)
    app.add_handler(trip_command)
    app.add_handler(return_command)
    app.add_handler(report_command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    app.add_handler(organization_callback)

    # Запускаем APScheduler-задачи
    start_scheduler()

    print("⏳ Запуск polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("🛑 Бот остановлен вручную.")
    except Exception as e:
        print(f"🔴 Критическая ошибка: {e}")
        raise
