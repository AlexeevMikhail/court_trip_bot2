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


# ... (start_trip, handle_org_selection, handle_custom_org_input — без изменений) ...


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
    logger.info("end_trip: user %s ending trip at %s", user_id, now)

    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    logger.info("SQLite update rowcount: %d", cur.rowcount)
    if cur.rowcount == 0:
        conn.commit()
        conn.close()
        logger.warning("No in_progress trip found for user %s", user_id)
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
    logger.info("Fetched from DB org %s, start_dt %s", org_name, start_dt)

    if isinstance(start_dt, str):
        try:
            start_dt = datetime.fromisoformat(start_dt)
        except ValueError:
            start_dt = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")

    # 🔧 ДОБАВЛЕНО: Приведение start_dt к рабочему времени
    adjusted_start = start_dt if get_debug_mode() else adjust_to_work_hours(start_dt)
    logger.info("Adjusted start time for sheet: %s", adjusted_start)

    duration = now - adjusted_start
    logger.info("Calculated duration: %s", duration)

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        logger.info(
            "Calling end_trip_in_sheet for %s, org %s, start %s, end %s, duration %s",
            full_name, org_name, adjusted_start, now, duration
        )
        end_trip_in_sheet(full_name, org_name, adjusted_start, now, duration)
        logger.info("end_trip_in_sheet succeeded")
    except Exception as e:
        logger.error("end_trip_in_sheet failed: %s", e)

    time_str = now.strftime("%H:%M")
    await target.reply_text(
        f"🏁 Поездка в *{org_name}* завершена в *{time_str}*",
        parse_mode="Markdown"
    )
