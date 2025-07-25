# core/trip.py

import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip, end_trip_in_sheet

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
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    org_id = query.data.split("_", 1)[1]

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        return await query.edit_message_text("✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS.get(org_id, org_id)
    success = save_trip_start(user_id, org_id, org_name)
    if not success:
        return await query.edit_message_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    now = get_now()
    time_str = now.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        await add_trip(full_name, org_name, now)  # если add_trip стал async, иначе без await
    except:
        # если add_trip – sync, то используем просто add_trip(...)
        pass

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

    success = save_trip_start(user_id, "other", org_name)
    if not success:
        return await update.message.reply_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    now = get_now()
    time_str = now.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        await add_trip(full_name, org_name, now)
    except:
        pass

    await update.message.reply_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # поддержка и для 콜бэка, и для текста
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        target = query
        user_id = query.from_user.id
    else:
        target = update.message
        user_id = update.message.from_user.id

    now = get_now()

    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    if cur.rowcount == 0:
        conn.commit()
        conn.close()
        return await target.reply_text("⚠️ У вас нет активной поездки.")
    conn.commit()

    # читаем только что закрытую
    cur.execute(
        "SELECT organization_name, start_datetime "
        "FROM trips WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()
    conn.close()

    if isinstance(start_dt, str):
        try:
            start_dt = datetime.fromisoformat(start_dt)
        except ValueError:
            start_dt = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")

    # достаём ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    duration = now - start_dt

    # записываем в Google Sheets
    try:
        await end_trip_in_sheet(full_name, org_name, start_dt, now, duration)
    except Exception as e:
        print(f"[trip][ERROR] end_trip_in_sheet failed: {e}")

    time_str = now.strftime("%H:%M")
    await target.reply_text(
        f"🏁 Поездка в *{org_name}* завершена в *{time_str}*",
        parse_mode="Markdown"
    )
