import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.database import (
    is_registered,
    save_trip_start,
    get_now,
    end_trip_local,
    fetch_last_completed
)
from core.sheets import add_trip, end_trip_in_sheet

ORGANIZATIONS = {
    'kuzminsky':       "Кузьминский районный суд",
    'lefortovsky':     "Лефортовский районный суд",
    'lyublinsky':      "Люблинский районный суд",
    'meshchansky':     "Мещанский районный суд",
    'nagatinsky':      "Нагатинский районный суд",
    'perovsky':        "Перовский районный суд",
    'shcherbinsky':    "Щербинский районный суд",
    'tverskoy':        "Тверской районный суд",
    'cheromushkinsky': "Черёмушкинский районный суд",
    'chertanovsky':    "Чертановский районный суд",
    'msk_city':        "Московский городской суд",
    'kassatsionny2':   "Второй кассационный суд общей юрисдикции",
    'domodedovo':      "Домодедовский городской суд",
    'lyuberetsky':     "Люберецкий городской суд",
    'vidnoye':         "Видновский городской суд",
    'justice_peace':   "Мировые судьи (судебный участок)",
    'fns':             "ФНС",
    'gibdd':           "ГИБДД",
    'notary':          "Нотариус",
    'post':            "Почта России",
    'rosreestr':       "Росреестр",
    'other':           "Другая организация (ввести вручную)"
}


async def start_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_registered(user_id):
        return await update.message.reply_text(
            "❌ Вы не зарегистрированы!\nОтправьте /register Иванов Иван"
        )
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    await update.message.reply_text(
        "🚗 *Куда вы отправляетесь?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_org_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    org_id  = query.data.split("_", 1)[1]

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        return await query.edit_message_text("✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS.get(org_id, org_id)
    dt = save_trip_start(user_id, org_id, org_name)
    if not dt:
        return await query.edit_message_text(
            "❌ У вас уже есть незавершённая поездка или вне рабочего времени."
        )

    time_str = dt.strftime("%H:%M")

    # ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # Google Sheets
    try:
        add_trip(full_name, org_name, dt)
    except Exception as e:
        print(f"[trip][ERROR] add_trip failed: {e}")

    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not context.user_data.get("awaiting_custom_org"):
        return
    context.user_data.pop("awaiting_custom_org", None)
    org_name = update.message.text.strip()

    dt = save_trip_start(user_id, "other", org_name)
    if not dt:
        return await update.message.reply_text(
            "❌ У вас уже есть незавершённая поездка или вне рабочего времени."
        )

    time_str = dt.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        add_trip(full_name, org_name, dt)
    except Exception as e:
        print(f"[trip][ERROR] add_trip(custom) failed: {e}")

    await update.message.reply_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query   = update.callback_query
        await query.answer()
        target  = query
        user_id = query.from_user.id
    else:
        target  = update.message
        user_id = update.message.from_user.id

    ok, end_dt = end_trip_local(user_id)
    if not ok:
        return await target.reply_text("⚠️ У вас нет активной поездки.")

    org_name, start_dt = fetch_last_completed(user_id)
    duration = end_dt - start_dt
    time_str = end_dt.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        await end_trip_in_sheet(full_name, org_name, start_dt, end_dt, duration)
    except Exception as e:
        print(f"[trip][ERROR] end_trip_in_sheet failed: {e}")

    await target.reply_text(
        f"🏁 Поездка в *{org_name}* завершена в *{time_str}*",
        parse_mode="Markdown"
    )
