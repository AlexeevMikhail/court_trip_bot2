# core/trip.py

import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.database import (
    is_registered,
    save_trip_start,
    get_now,
    get_debug_mode,
    adjust_to_work_hours,
)
from core.sheets import add_trip, end_trip_in_sheet

logger = logging.getLogger(__name__)

# Список организаций
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
    print(f"[LOG] start_trip called for user {user_id}")
    logger.info("start_trip: user %s", user_id)
    if not is_registered(user_id):
        print(f"[LOG] User {user_id} not registered")
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
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    org_id = query.data.split("_", 1)[1]
    print(f"[LOG] handle_org_selection: user {user_id} selected org {org_id}")
    logger.info("handle_org_selection: user %s selected org %s", user_id, org_id)

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        print(f"[LOG] Awaiting custom org name for user {user_id}")
        return await query.edit_message_text("✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS.get(org_id, org_id)
    success = save_trip_start(user_id, org_id, org_name)
    if not success:
        print(f"[LOG] save_trip_start failed for user {user_id}")
        return await query.edit_message_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    raw = get_now()
    print(f"[LOG] Raw time: {raw}")
    start_dt = raw if get_debug_mode() else adjust_to_work_hours(raw)
    print(f"[LOG] Adjusted start time: {start_dt}")
    time_str = start_dt.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        print(f"[LOG] add_trip → {full_name}, {org_name}, {start_dt}")
        add_trip(full_name, org_name, start_dt)
        print("[LOG] add_trip succeeded")
    except Exception as e:
        print(f"[LOG] add_trip failed: {e}")

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
    print(f"[LOG] handle_custom_org_input: user {user_id}, org {org_name}")
    logger.info("handle_custom_org_input: user %s custom org %s", user_id, org_name)

    success = save_trip_start(user_id, "other", org_name)
    if not success:
        print(f"[LOG] save_trip_start failed for custom org user {user_id}")
        return await update.message.reply_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    raw = get_now()
    print(f"[LOG] Raw custom time: {raw}")
    start_dt = raw if get_debug_mode() else adjust_to_work_hours(raw)
    print(f"[LOG] Adjusted custom start time: {start_dt}")
    time_str = start_dt.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        print(f"[LOG] add_trip custom → {full_name}, {org_name}, {start_dt}")
        add_trip(full_name, org_name, start_dt)
        print("[LOG] add_trip succeeded custom")
    except Exception as e:
        print(f"[LOG] add_trip failed custom: {e}")

    await update.message.reply_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        target = query
        user_id = query.from_user.id
    else:
        target = update.message
        user_id = update.message.from_user.id

    now = get_now()
    print(f"[LOG] end_trip called by user {user_id} at {now}")
    logger.info("end_trip: user %s ending trip at %s", user_id, now)

    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    print(f"[LOG] SQLite update rows: {cur.rowcount}")
    logger.info("SQLite update rowcount: %d", cur.rowcount)
    if cur.rowcount == 0:
        conn.commit()
        conn.close()
        print(f"[LOG] No in_progress trip for user {user_id}")
        return await target.reply_text("⚠️ У вас нет активной поездки.")
    conn.commit()

    cur.execute(
        "SELECT organization_name, start_datetime "
        "FROM trips WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()
    conn.close()
    print(f"[LOG] Fetched from DB → org: {org_name}, start_dt: {start_dt}")

    if isinstance(start_dt, str):
        try:
            start_dt = datetime.fromisoformat(start_dt)
        except ValueError:
            start_dt = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
    print(f"[LOG] Raw start_dt for matching: {start_dt}")
    if not get_debug_mode():
        start_dt = adjust_to_work_hours(start_dt)
        print(f"[LOG] Adjusted start_dt for matching: {start_dt}")

    duration = now - start_dt
    print(f"[LOG] Calculated duration: {duration}")
    logger.info("Calculated duration: %s", duration)

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[LOG] full_name for sheets: {full_name}")

    try:
        print(f"[LOG] Calling end_trip_in_sheet → {full_name}, {org_name}, {start_dt}, {now}, {duration}")
        end_trip_in_sheet(full_name, org_name, start_dt, now, duration)
        print("[LOG] end_trip_in_sheet succeeded")
        logger.info("end_trip_in_sheet succeeded")
    except Exception as e:
        print(f"[LOG] end_trip_in_sheet failed: {e}")
        logger.error("end_trip_in_sheet failed: %s", e)

    time_str = now.strftime("%H:%M")
    await target.reply_text(
        f"🏁 Поездка в *{org_name}* завершена в *{time_str}*",
        parse_mode="Markdown"
    )
