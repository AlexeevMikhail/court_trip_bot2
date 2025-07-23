# handlers/menu.py

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.callbacks import (
    organization_callback,
    end_trip_callback,
    plan_org_callback
)
from core.trip import start_trip, handle_custom_org_input, end_trip
from core.calendar import start_plan, handle_plan_datetime, show_calendar
from core.register import register
from core.report import generate_report, ADMIN_IDS
from utils.database import is_registered

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # 1) Если мы ждём ввод ФИО после нажатия «Регистрация»
    if context.user_data.get("awaiting_registration"):
        return await register(update, context)

    # 2) Состояния ожидания других вводов
    if context.user_data.get("awaiting_custom_org"):
        return await handle_custom_org_input(update, context)
    if context.user_data.get("awaiting_plan_datetime"):
        return await handle_plan_datetime(update, context)

    # 3) Обработка нажатий кнопок меню
    if text == "🚀 Поездка":
        return await start_trip(update, context)
    elif text == "🏦 Возврат":
        return await end_trip(update, context)
    elif text == "🗓 План":
        return await start_plan(update, context)
    elif text == "📅 Календарь":
        return await show_calendar(update, context)
    elif text == "➕ Регистрация":
        return await register(update, context)
    elif text == "💼 Отчет":
        return await generate_report(update, context)

    # 4) По умолчанию — рисуем клавиатуру динамически
    keyboard = [
        ["🚀 Поездка", "🏦 Возврат"],
        ["🗓 План",    "📅 Календарь"]
    ]
    bottom = []
    # Показываем «Регистрация» только если не в БД
    if not is_registered(user_id):
        bottom.append("➕ Регистрация")
    # Показываем «Отчет» только админам
    if user_id in ADMIN_IDS:
        bottom.append("💼 Отчет")
    if bottom:
        keyboard.append(bottom)

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return await update.message.reply_text(
        "Выберите действие из меню ниже:",
        reply_markup=reply_markup
    )
