from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from handlers.commands import register_command, trip_command, return_command, report_command
from handlers.callbacks import organization_callback
from handlers.menu import handle_main_menu
from utils.database import init_db
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(register_command)
    app.add_handler(trip_command)
    app.add_handler(return_command)
    app.add_handler(report_command)

    # Кнопки и текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))

    # Callback
    app.add_handler(organization_callback)

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
