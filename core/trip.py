# core/trip.py

import sqlite3
from datetime import timedelta
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
    print(f"[trip] start_trip called by user {user_id}")
    if not is_registered(user_id):
        print(f"[trip] user {user_id} not registered")
        return await update.message.reply_text(
            "❌ Вы не зарегистрированы!\nОтправьте /register Иванов Иван"
        )

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    print(f"[trip] sending organization keyboard to user {user_id}")
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

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        print(f"[trip] user {user_id} will input custom organization")
        return await query.edit_message_text(✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS.get(org_id, org_id)
    print(f"[trip] user {user_id} selected organization '{org_name}'")

    # Сохраняем старт поездки
    if not save_trip_start(user_id, org_id, org_name):
        print(f"[trip] save_trip_start returned False for user {user_id}")
        return await query.edit_message_text("❌ У вас уже есть незавершённая поездка.")
    now = get_now()
    time_str = now.strftime("%H:%M")
    print(f"[trip] save_trip_start succeeded, now={now}")

    # Получаем ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[trip] fetched full_name='{full_name}'")

    # Запись старта в Google Sheets
    try:
        print(f"[trip] calling add_trip({full_name}, {org_name}, {now})")
        add_trip(full_name, org_name, now)
        print(f"[trip] add_trip succeeded")
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
    context.user_data.pop("awaiting_custom_org")
    org_name = update.message.text.strip()
    print(f"[trip] handle_custom_org_input: user={user_id}, org_name='{org_name}'")

    if not save_trip_start(user_id, "other", org_name):
        print(f"[trip] save_trip_start(False) for custom org by user {user_id}")
        return await update.message.reply_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_str = now.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[trip] fetched full_name='{full_name}' for custom org")

    try:
        print(f"[trip] calling add_trip({full_name}, {org_name}, {now}) for custom org")
        add_trip(full_name, org_name, now)
        print(f"[trip] add_trip succeeded for custom org")
    except Exception as e:
        print(f"[trip][ERROR] add_trip(custom org) failed: {e}")

    await update.message.reply_text(
        f"🚀 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )


async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Поддержка callback_query и message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        target = query
        print(f"[trip] end_trip (callback) triggered by user {user_id}")
    else:
        user_id = update.message.from_user.id
        target = update.message
        print(f"[trip] end_trip (message) triggered by user {user_id}")

    now = get_now()
    print(f"[trip] current time: {now}")
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    # Обновляем статус
    print(f"[trip] executing UPDATE trips SET end_datetime, status for user {user_id}")
    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    updated = cur.rowcount
    conn.commit()
    print(f"[trip] UPDATE affected rows: {updated}")

    if updated == 0:
        conn.close()
        print(f"[trip] no active trip found for user {user_id}")
        return await target.reply_text("⚠️ У вас нет активной поездки.")

    # Читаем организацию и время старта
    cur.execute(
        "SELECT organization_name, start_datetime FROM trips "
        "WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()
    print(f"[trip] fetched org_name='{org_name}', start_dt={start_dt}")

    # Читаем ФИО
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[trip] fetched full_name='{full_name}' from employees")

    # Логируем заголовки и записи в листе «Поездки»
    try:
        print("[trip] calling end_trip_in_sheet...")
        await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)
        print("[trip] end_trip_in_sheet succeeded")
    except Exception as e:
        print(f"[trip][ERROR] end_trip_in_sheet failed: {e}")

    # Окончательное сообщение
    time_str = now.strftime("%H:%M")
    msg = f"🏁 Поездка в *{org_name}* завершена в *{time_str}*"
    print(f"[trip] sending completion message: {msg}")
    await target.reply_text(msg, parse_mode="Markdown")
