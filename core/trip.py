# core/trip.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import sqlite3
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
    """
    /trip или кнопка «🚀 Поездка»: показываем inline‑кнопки со списком судов.
    """
    msg = update.message
    user_id = msg.from_user.id
    if not is_registered(user_id):
        return await msg.reply_text(
            "❌ Вы не зарегистрированы!\n"
            "Отправьте команду /register Иванов Иван"
        )

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    await msg.reply_text(
        "🚗 *Куда вы отправляетесь?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_org_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатываем нажатие inline‑кнопки org_<id>.
    Если id=='other' — просим ввести текст.
    Иначе сохраняем старт поездки.
    """
    query = update.callback_query
    await query.answer()
    org_id = query.data.split("_", 1)[1]

    # Случай «Другая организация»
    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        return await query.edit_message_text("✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS[org_id]
    user_id = query.from_user.id

    # 1) Локальный статус
    if not save_trip_start(user_id, org_id, org_name):
        return await query.edit_message_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_str = now.strftime("%H:%M")

    # 2) ФИО из SQLite
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # 3) Запись старта в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка записи старта: {e}")

    # 4) Оповещаем
    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатываем текстовый ввод после «Другая организация».
    Сохраняем поездку со введённым org_name.
    """
    if not context.user_data.get("awaiting_custom_org"):
        return
    context.user_data.pop("awaiting_custom_org")

    user_id = update.message.from_user.id
    org_name = update.message.text.strip()

    if not save_trip_start(user_id, "other", org_name):
        return await update.message.reply_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_str = now.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка записи старта: {e}")

    await update.message.reply_text(
        f"🚀 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /return или кнопка «🏦 Возврат»: завершаем поездку,
    пишем конец и длительность в Google Sheets и сообщаем в чат.
    """
    # Поддерживаем callback_query и обычное сообщение
    if update.callback_query:
        await update.callback_query.answer()
        user_id = update.callback_query.from_user.id
        target = update.callback_query
    else:
        user_id = update.message.from_user.id
        target = update.message

    now = get_now()
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    # 1) Обновляем статус
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

    # 2) Достаём org_name и старт
    cur.execute(
        "SELECT organization_name, start_datetime FROM trips "
        "WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()

    # 3) Достаём ФИО
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # 4) Записываем конец и длительность
    try:
        await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)
    except Exception as e:
        print(f"[Google Sheets] Ошибка записи окончания: {e}")

    # 5) Сообщаем
    time_str = now.strftime("%H:%M")
    await target.reply_text(
        f"🏁 Поездка в *{org_name}* завершена в *{time_str}*",
        parse_mode="Markdown"
    )
