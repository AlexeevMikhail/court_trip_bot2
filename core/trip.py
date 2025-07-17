# core/trip.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import sqlite3
from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip, end_trip_in_sheet

# Словарь организаций
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
    Начало поездки: показывает inline‑кнопки со списком судов.
    """
    query = update.callback_query
    target = query or update.message
    if query:
        await query.answer()
    user_id = target.from_user.id

    if not is_registered(user_id):
        return await target.reply_text(
            "❌ Вы не зарегистрированы! Отправьте /register Иванов Иван"
        )

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    await target.reply_text(
        "🚗 *Куда вы отправляетесь?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_trip_save(update: Update, context: ContextTypes.DEFAULT_TYPE, org_id: str, org_name: str):
    """
    Сохранение начала поездки после выбора inline‑кнопки.
    Записывает в SQLite и Google Sheets.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Сохраняем старт в локальной БД
    if not save_trip_start(user_id, org_id, org_name):
        return await query.edit_message_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_str = now.strftime("%H:%M")

    # Получаем ФИО из employees
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # Записываем старт в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка записи старта: {e}")

    # Сообщаем пользователю
    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*.",
        parse_mode="Markdown"
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ручного ввода названия организации (для org_id='other').
    """
    # Ожидаемая подсказка выставляется в callbacks
    if not context.user_data.get("awaiting_custom_org"):
        return

    context.user_data.pop("awaiting_custom_org", None)
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
        print(f"[Google Sheets] Ошибка записи старта: {e}")

    await update.message.reply_text(
        f"🚀 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Завершение поездки: помечает в SQLite и записывает конец + длительность в Google Sheets.
    Может вызываться как callback_query или как текстовая команда/кнопка меню.
    """
    query = update.callback_query
    target = query or update.message
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.message.from_user.id

    now = get_now()
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    # Обновляем запись путешествия
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

    # Получаем данные поездки
    cur.execute(
        "SELECT org_name, start_datetime FROM trips "
        "WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()

    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # Записываем окончание и длительность
    try:
        await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)
    except Exception as e:
        print(f"[Google Sheets] Ошибка записи окончания: {e}")

    time_str = now.strftime("%H:%M")
    text = f"🏁 Поездка в *{org_name}* завершена в *{time_str}*"

    if query:
        await query.edit_message_text(text, parse_mode="Markdown")
    else:
        await target.reply_text(text, parse_mode="Markdown")
