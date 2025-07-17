# handlers/menu.py

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters

from handlers.callbacks import (
    organization_callback,
    end_trip_callback,
    plan_org_callback
)
from core.trip import start_trip, handle_custom_org_input, end_trip
from core.calendar import start_plan, handle_plan_datetime, show_calendar
from core.register import register
from core.report import generate_report

# Главное меню
main_menu_keyboard = [
    ["🚀 Поездка", "🏦 Возврат"],
    ["🗓 План",   "📅 Календарь"],
    ["➕ Регистрация", "/report"]
]
main_menu_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Обработка состояний ожидания ввода
    if context.user_data.get("awaiting_custom_org"):
        return await handle_custom_org_input(update, context)
    if context.user_data.get("awaiting_plan_datetime"):
        return await handle_plan_datetime(update, context)

    # Основное меню
    if text == "🚀 Поездка":
        await start_trip(update, context)

    elif text == "🏦 Возврат":
        await end_trip(update, context)

    elif text == "🗓 План":
        await start_plan(update, context)

    elif text == "📅 Календарь":
        await show_calendar(update, context)

    elif text == "➕ Регистрация":
        await register(update, context)

    elif text == "/report":
        # Команда отчёта может идти без параметров
        await update.message.reply_text(
            "Используйте: /report ДД.MM.ГГГГ [ДД.MM.ГГГГ]"
        )

    else:
        # На всё остальное — показываем меню
        await update.message.reply_text(
            "Выберите действие из меню ниже:",
            reply_markup=main_menu_markup
        )
