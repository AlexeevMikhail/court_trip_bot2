import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.database import (
    is_registered,
    save_trip_start,
    end_trip_local,
    fetch_last_completed,
    get_now
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
    user_id = update.effective_user.id
    print(f"[trip] start_trip triggered by user {user_id}")
    if not is_registered(user_id):
        print(f"[trip] user {user_id} is NOT registered")
        return await update.message.reply_text(
            "❌ Вы не зарегистрированы! Отправьте /register Иванов Иван"
        )
    print(f"[trip] user {user_id} is registered — sending org list")
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
    org_id  = query.data.split("_",1)[1]
    print(f"[trip] handle_org_selection: user={user_id}, org_id={org_id}")

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        print(f"[trip] awaiting custom org from {user_id}")
        return await query.edit_message_text("✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS[org_id]
    ok = save_trip_start(user_id, org_id, org_name)
    print(f"[trip] save_trip_start → {ok}")
    if not ok:
        return await query.edit_message_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    now      = get_now()
    time_str = now.strftime("%H:%M")
    print(f"[trip] trip start at {now!r}")

    # берём ФИО
    conn       = sqlite3.connect("court_tracking.db")
    full_name  = conn.execute(
        "SELECT full_name FROM employees WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    conn.close()
    print(f"[trip] full_name = '{full_name}'")

    # Google Sheets
    try:
        print(f"[trip] add_trip({full_name}, {org_name}, {now!r})")
        add_trip(full_name, org_name, now)
        print("[trip] add_trip succeeded")
    except Exception as e:
        print(f"[trip][ERROR] add_trip failed: {e}")

    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.user_data.get("awaiting_custom_org"):
        return
    context.user_data.pop("awaiting_custom_org", None)

    org_name = update.message.text.strip()
    print(f"[trip] custom org = '{org_name}'")
    ok = save_trip_start(user_id, "other", org_name)
    print(f"[trip] save_trip_start(custom) → {ok}")
    if not ok:
        return await update.message.reply_text(
            "❌ У вас уже есть незавершённая поездка или вы вне рабочего времени."
        )

    now      = get_now()
    time_str = now.strftime("%H:%M")
    conn      = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        print(f"[trip] add_trip(custom) ({full_name}, {org_name}, {now!r})")
        add_trip(full_name, org_name, now)
        print("[trip] add_trip(custom) succeeded")
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
        print(f"[trip] end_trip(callback) by {user_id}")
    else:
        target  = update.message
        user_id = update.message.from_user.id
        print(f"[trip] end_trip(message) by {user_id}")

    ok, now = end_trip_local(user_id)
    print(f"[trip] end_trip_local → {ok}, at {now!r}")
    if not ok:
        return await target.reply_text("⚠️ У вас нет активной поездки.")

    org_name, start_dt = fetch_last_completed(user_id)
    print(f"[trip] fetched completed: org='{org_name}', start_dt={start_dt!r}")

    duration = now - start_dt
    print(f"[trip] duration = {duration}")

    # записываем в Google Sheets
    try:
        print(f"[trip] end_trip_in_sheet({user_id}, {org_name}, {start_dt!r}, {now!r}, {duration})")
        await end_trip_in_sheet(
            full_name := fetch_full_name(user_id),
            org_name,
            start_dt,
            now,
            duration
        )
        print("[trip] end_trip_in_sheet succeeded")
    except Exception as e:
        print(f"[trip][ERROR] end_trip_in_sheet failed: {e}")

    time_str = now.strftime("%H:%M")
    await target.reply_text(
        f"🏁 Поездка в *{org_name}* завершена в *{time_str}*",
        parse_mode="Markdown"
    )

def fetch_full_name(user_id: int) -> str:
    conn = sqlite3.connect("court_tracking.db")
    name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return name
