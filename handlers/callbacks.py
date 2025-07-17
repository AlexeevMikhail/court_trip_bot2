# handlers/callbacks.py

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from core.trip import (
    start_trip,
    handle_org_selection,      # функция обработки выбора организации
    handle_custom_org_input,
    end_trip,
    ORGANIZATIONS
)
from core.calendar import handle_plan_org  # импорт для планирования

async def handle_organization_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    org_id = query.data.split("_", 1)[1]
    org_name = ORGANIZATIONS.get(org_id, "Неизвестная организация")

    if org_id == "other":
        # при выборе «Другая организация» ждём ввод текста
        context.user_data["awaiting_custom_org"] = True
        await query.edit_message_text("✏️ Введите название организации вручную:")
    else:
        # для всех остальных — обрабатываем выбор через core.trip
        await handle_org_selection(update, context)

async def handle_end_trip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await end_trip(update, context)

async def handle_plan_org_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_plan_org(update, context)

# Регистрируем inline‑хендлеры
organization_callback = CallbackQueryHandler(
    handle_organization_callback,
    pattern=r"^org_"
)
end_trip_callback = CallbackQueryHandler(
    handle_end_trip_callback,
    pattern=r"^end_trip$"
)
plan_org_callback = CallbackQueryHandler(
    handle_plan_org_callback,
    pattern=r"^plan_org_"
)
