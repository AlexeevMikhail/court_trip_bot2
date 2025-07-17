# core/calendar.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime
import sqlite3
import pandas as pd
from io import BytesIO

from utils.database import is_registered
from core.sheets import add_plan, get_calendar_dataframe
from core.trip import ORGANIZATIONS  # используем тот же список судов

async def start_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_registered(user_id):
        return await update.message.reply_text("❌ Вы не зарегистрированы!\nИспользуйте /register")
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"plan_org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🗓 *Планирование поездки*. Выберите организацию:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_plan_org(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    org_id = query.data.split("_", 2)[2]
    org_name = ORGANIZATIONS.get(org_id, org_id)
    context.user_data["plan_org_name"] = org_name
    context.user_data["awaiting_plan_datetime"] = True
    await query.edit_message_text(
        "✏️ Введите дату и время в формате `ДД.MM.ГГГГ ЧЧ:ММ` "
        "или только `ДД.MM.ГГГГ` (для «Весь день»):",
        parse_mode="Markdown"
    )

async def handle_plan_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_plan_datetime"):
        return
    text = update.message.text.strip()
    try:
        parts = text.split()
        if len(parts) == 2:
            date_part, time_part = parts
            plan_date = datetime.strptime(date_part, "%d.%m.%Y").date()
            plan_time = datetime.strptime(time_part, "%H:%M").strftime("%H:%M")
        else:
            plan_date = datetime.strptime(text, "%d.%m.%Y").date()
            plan_time = "Весь день"
    except ValueError:
        return await update.message.reply_text(
            "❌ Неверный формат. Попробуйте: `ДД.MM.ГГГГ ЧЧ:ММ` или `ДД.MM.ГГГГ`.",
            parse_mode="Markdown"
        )

    user_id = update.message.from_user.id
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    org_name = context.user_data.get("plan_org_name")
    try:
        add_plan(full_name, org_name, plan_date, plan_time)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при записи в календарь: {e}")
        return await update.message.reply_text("❌ Не удалось записать в Календарь.")

    # сброс состояния
    context.user_data.pop("awaiting_plan_datetime", None)
    context.user_data.pop("plan_org_name", None)

    await update.message.reply_text(
        f"✅ Запланирована поездка в *{org_name}* "
        f"на *{plan_date.strftime('%d.%m.%Y')} {plan_time}*",
        parse_mode="Markdown"
    )

async def show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_registered(user_id):
        return await update.message.reply_text("❌ Вы не зарегистрированы!")
    df = get_calendar_dataframe()
    if df.empty:
        return await update.message.reply_text("📭 Календарь пуст.")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Календарь", index=False)
        ws = writer.sheets["Календарь"]
        for i, col in enumerate(df.columns):
            width = max(df[col].astype(str).map(len).max(), len(col)) + 2
            ws.set_column(i, i, width)
    buf.seek(0)
    await update.message.reply_document(document=buf, filename="Календарь.xlsx")
