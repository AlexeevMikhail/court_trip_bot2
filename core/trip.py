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
    print(f"[trip] start_trip triggered by user {user_id}")
    if not is_registered(user_id):
        print(f"[trip] user {user_id} is NOT registered")
        return await update.message.reply_text(
            "❌ Вы не зарегистрированы!\nОтправьте /register Иванов Иван"
        )

    print(f"[trip] user {user_id} is registered — sending organization keyboard")
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
    print(f"[trip] handle_org_selection: user={user_id}, org_id={org_id}")

    # если «Другая организация»
    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        print(f"[trip] awaiting custom org from user {user_id}")
        return await query.edit_message_text(
            "✏️ Введите название организации вручную:"
        )

    org_name = ORGANIZATIONS.get(org_id, org_id)
    print(f"[trip] resolved org_name = '{org_name}'")

    # сохраняем старт (внутри save_trip_start уже учтены DEBUG_MODE и часы)
    success = save_trip_start(user_id, org_id, org_name)
    print(f"[trip] save_trip_start returned {success}")
    if not success:
        # либо уже in_progress, либо вне рабочего времени
        return await query.edit_message_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    now = get_now()
    time_str = now.strftime("%H:%M")
    print(f"[trip] trip start time (get_now) = {now!r}")

    # берём ФИО из БД
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[trip] full_name fetched = '{full_name}'")

    # пишем в Google Sheets
    try:
        print(f"[trip] calling add_trip({full_name}, {org_name}, {now!r})")
        add_trip(full_name, org_name, now)
        print("[trip] add_trip succeeded")
    except Exception as e:
        print(f"[trip][ERROR] add_trip failed: {e}")

    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    print(f"[trip] handle_custom_org_input triggered by user {user_id}")
    if not context.user_data.get("awaiting_custom_org"):
        print("[trip] unexpected custom input, ignoring")
        return
    context.user_data.pop("awaiting_custom_org", None)

    org_name = update.message.text.strip()
    print(f"[trip] custom org_name = '{org_name}'")

    success = save_trip_start(user_id, "other", org_name)
    print(f"[trip] save_trip_start(custom) returned {success}")
    if not success:
        return await update.message.reply_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    now = get_now()
    time_str = now.strftime("%H:%M")
    print(f"[trip] custom-trip start time = {now!r}")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[trip] full_name fetched = '{full_name}'")

    try:
        print(f"[trip] calling add_trip(custom) with ({full_name}, {org_name}, {now!r})")
        add_trip(full_name, org_name, now)
        print("[trip] add_trip(custom) succeeded")
    except Exception as e:
        print(f"[trip][ERROR] add_trip(custom org) failed: {e}")

    await update.message.reply_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Поддержка callback_query и текстового «Возврат»
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        target = query
        user_id = query.from_user.id
        print(f"[trip] end_trip (callback) triggered by user {user_id}")
    else:
        target = update.message
        user_id = update.message.from_user.id
        print(f"[trip] end_trip (message) triggered by user {user_id}")

    now = get_now()
    print(f"[trip] end_trip get_now = {now!r}")

    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    # помечаем завершённой текущую
    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    updated = cur.rowcount
    print(f"[trip] UPDATE trips rowcount = {updated}")
    if updated == 0:
        conn.commit()
        conn.close()
        print(f"[trip] no in_progress trip found for user {user_id}")
        return await target.reply_text("⚠️ У вас нет активной поездки.")
    conn.commit()

    # забираем только что закрытую поездку
    cur.execute(
        "SELECT organization_name, start_datetime "
        "FROM trips "
        "WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()
    print(f"[trip] fetched org_name = '{org_name}', start_dt raw = {start_dt!r}")

    # парсим строку, если надо
    if isinstance(start_dt, str):
        try:
            start_dt = datetime.fromisoformat(start_dt)
        except ValueError:
            start_dt = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
        print(f"[trip] parsed start_dt = {start_dt!r}")

    # ФИО
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[trip] full_name fetched = '{full_name}'")

    # длительность
    duration = now - start_dt
    print(f"[trip] computed duration = {duration!r}")

    # пишем в Google Sheets
    try:
        print(f"[trip] calling end_trip_in_sheet({full_name}, {org_name}, {start_dt!r}, {now!r}, {duration!r})")
        await end_trip_in_sheet(full_name, org_name, start_dt, now, duration)
        print("[trip] end_trip_in_sheet succeeded")
    except Exception as e:
        print(f"[trip][ERROR] end_trip_in_sheet failed: {e}")

    # уведомляем юзера
    time_str = now.strftime("%H:%M")
    await target.reply_text(
        f"🏁 Поездка в *{org_name}* завершена в *{time_str}*",
        parse_mode="Markdown"
    )
