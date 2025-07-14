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

load_dotenv()
keep_alive()
time.sleep(3)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("❌ BOT_TOKEN is missing")
    exit(1)

async def on_startup(app):
    # Убираем webhook, чтобы разрешить polling
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("🟢 Бот успешно запущен (вебхук удалён, polling готов)")

def main():
    # init_db() — отключено, если не используете БД на данный момент

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .job_queue(None)            # отключаем встроенный JobQueue PTB
        .post_init(on_startup)
        .build()
    )

    # регистрируем все ваши хэндлеры
    app.add_handler(register_command)
    app.add_handler(trip_command)
    app.add_handler(return_command)
    app.add_handler(report_command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    app.add_handler(organization_callback)

    start_scheduler()

    print("⏳ Запуск polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message","callback_query"])

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("🛑 Бот остановлен вручную.")
    except Exception as e:
        print(f"🔴 Критическая ошибка: {e}")
        raise
