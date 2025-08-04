# bot.py

import os
import time
import logging  # добавлено для настройки логирования
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from handlers.commands import (
    register_command,
    trip_command,
    return_command,
    report_command
)
from handlers.callbacks import (
    organization_callback,
    end_trip_callback,
    plan_org_callback
)
from handlers.menu import handle_main_menu
from keep_alive import keep_alive
from scheduler import start_scheduler

load_dotenv()
keep_alive()
# даём время на установку соединений
time.sleep(3)

# Настройка логирования — чтобы INFO и выше шли в bot.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("❌ BOT_TOKEN is missing")
    exit(1)

async def on_startup(app):
    # Убираем webhook, чтобы разрешить polling
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("🟢 Бот успешно запущен (вебхук удалён, polling готов)")

def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .job_queue(None)            # отключаем встроенный JobQueue PTB
        .post_init(on_startup)
        .build()
    )

    # Регистрация CommandHandler'ов
    app.add_handler(register_command)   # /register
    app.add_handler(trip_command)       # /trip
    app.add_handler(return_command)     # /return
    app.add_handler(report_command)     # /report

    # Роутинг по тексту из главного меню
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))

    # Обработчики inline-кнопок
    app.add_handler(organization_callback)   # выбор суда
    app.add_handler(end_trip_callback)       # inline callback "end_trip"
    app.add_handler(plan_org_callback)       # inline callback "plan_org_*"

    # Запускаем планировщик
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
