# handlers/menu.py

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.trip import start_trip, end_trip, handle_custom_org_input
from core.register import register

# Основное меню кнопок (ReplyKeyboard)
main_menu_keyboard = [
    ["🚀 Поездка", "🏦 Возврат"],
    ["➕ Регистрация", "💼 Отчёт"]
]
main_menu_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Если ожидаем ввод названия (после выбора «Другая организация»)
    if context.user_data.get("awaiting_custom_org"):
        context.user_data["awaiting_custom_org"] = False
        return await handle_custom_org_input(update, context)

    if text == "🚀 Поездка":
        await start_trip(update, context)
    elif text == "🏦 Возврат":
        # Здесь end_trip вызывается напрямую, без inline‑callback
        await end_trip(update, context)
    elif text == "➕ Регистрация":
        await register(update, context)
    elif text == "💼 Отчёт":
        await update.message.reply_text(
            "Для отчёта используйте команду:\n/report ДД.MM.ГГГГ ДД.MM.ГГГГ"
        )
    else:
        # Любой другой текст — просто показываем меню
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=main_menu_markup
        )
