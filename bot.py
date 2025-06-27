from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from handlers.commands import register_command, trip_command, return_command, report_command
from handlers.callbacks import organization_callback
from handlers.menu import handle_main_menu
from utils.database import init_db
from dotenv import load_dotenv
import os
from keep_alive import keep_alive  # Важно для поддержания работы

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    # Регистрация обработчиков
    app.add_handler(register_command)
    app.add_handler(trip_command)
    app.add_handler(return_command)
    app.add_handler(report_command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    app.add_handler(organization_callback)

    print("🟢 Бот запущен в режиме polling...")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()  # Активируем Flask-сервер
    main()