# handlers/callbacks.py
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from core.trip import handle_trip_save, end_trip
from core.trip import ORGANIZATIONS
from core.trip import handle_custom_org_input

async def handle_organization_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    org_id = query.data.split("_", 1)[1]
    org_name = ORGANIZATIONS.get(org_id, "Неизвестная организация")

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        await query.edit_message_text(
            "✏️ Пожалуйста, введите название организации вручную:"
        )
    else:
        await handle_trip_save(update, context, org_id, org_name)

async def handle_end_trip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await end_trip(update, context)

organization_callback = CallbackQueryHandler(
    handle_organization_callback,
    pattern=r"^org_"
)
end_trip_callback = CallbackQueryHandler(
    handle_end_trip_callback,
    pattern=r"^end_trip$"
)
