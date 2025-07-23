# core/trip.py

import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.database import is_registered, save_trip_start, get_now, get_debug_mode
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
    org_id  = query.data.split("_", 1)[1]

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        return await query.edit_message_text("✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS.get(org_id, org_id)

    # сохраняем поездку в БД (с учётом DEBUG_MODE и рамок рабочего дня)
    if not save_trip_start(user_id, org_id, org_name):
        return await query.edit_message_text(
            "❌ У вас уже есть незавершённая поездка или сейчас вне рабочего времени."
        )

    # после успешного save_trip_start — вытягиваем именно ту дату/время, что в БД
    conn = sqlite3.connect("court_tracking.db")
    row  = conn.execute(
        "SELECT start_datetime FROM trips WHERE user_id = ? AND status = 'in_progress' ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    start_dt = row[0]
    # если в БД хранится строка
    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt)

    time_str = start_dt.strftime("%H:%M")

    # получаем ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # пишем в Google Sheets
    try:
        add_trip(full_name, org_name, start_dt)
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

    if not save_trip_start(user_id, "other", org_name):
        return await update.message.reply_text(
            "❌ У вас уже есть незавершённая поездка или сейчас вне рабочего времени."
        )

    # вытаскиваем скорректированное время из БД
    conn = sqlite3.connect("court_tracking.db")
    row  = conn.execute(
        "SELECT start_datetime FROM trips WHERE user_id = ? AND status = 'in_progress' ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    start_dt = row[0]
    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt)

    time_str = start_dt.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        add_trip(full_name, org_name, start_dt)
    except Exception as e:
        print(f"[trip][ERROR] add_trip(custom) failed: {e}")

    await update.message.reply_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # обработка как callback_query, так и обычного сообщения
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        target = query
        user_id = query.from_user.id
    else:
        target = update.message
        user_id = update.message.from_user.id

    # пробуем завершить локально
    from utils.database import end_trip as end_local
    now = get_now()
    if not end_local(user_id):
        return await target.reply_text("⚠️ У вас нет активной поездки.")

    # дёргаем последнюю завершённую запись
    conn = sqlite3.connect("court_tracking.db")
    cur  = conn.cursor()
    cur.execute(
        "SELECT organization_name, start_datetime FROM trips "
        "WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()
    conn.close()

    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt)

    # считаем длительность
    duration = now - start_dt

    # ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

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
