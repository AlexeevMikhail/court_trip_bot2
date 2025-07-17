# core/trip.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import sqlite3
from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip, end_trip_in_sheet

# Список организаций для выбора
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
    Вызывается командой /trip или кнопкой "Поездка" в меню.
    Показывает inline‑кнопки со списком организаций.
    """
    user_id = update.message.from_user.id
    if not is_registered(user_id):
        return await update.message.reply_text(
            "❌ Вы не зарегистрированы!\n"
            "Отправьте команду /register Иванов Иван"
        )

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚗 *Куда вы отправляетесь?*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_organization_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор организации из inline‑меню.
    Для org_id 'other' просит ввести вручную.
    Иначе сохраняет старт поездки.
    """
    query = update.callback_query
    await query.answer()
    org_id = query.data.split("_", 1)[1]

    if org_id == "other":
        context.user_data["awaiting_custom_org"] = True
        return await query.edit_message_text("✏️ Введите название организации вручную:")

    org_name = ORGANIZATIONS.get(org_id, org_id)
    user_id = query.from_user.id

    # 1) Сохраняем в SQLite
    if not save_trip_start(user_id, org_id, org_name):
        return await query.edit_message_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_str = now.strftime("%H:%M")

    # 2) Получаем ФИО из таблицы employees
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # 3) Записываем старт в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при записи старта: {e}")

    # 4) Сообщаем пользователю
    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает текстовый ввод организации после выбора "Другая организация".
    Сохраняет старт поездки по введённому имени.
    """
    if not context.user_data.get("awaiting_custom_org"):
        return  # не ожидали ввода — игнорируем

    context.user_data["awaiting_custom_org"] = False
    user_id = update.message.from_user.id
    org_name = update.message.text.strip()

    # 1) Сохраняем
    if not save_trip_start(user_id, "other", org_name):
        return await update.message.reply_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_str = now.strftime("%H:%M")

    # 2) Получаем ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # 3) Запись в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при записи старта: {e}")

    # 4) Сообщаем
    await update.message.reply_text(
        f"🚀 Поездка в *{org_name}* начата в *{time_str}*",
        parse_mode="Markdown"
    )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Вызывается кнопкой "Возврат" в меню или командой /return.
    Сохраняет в SQLite время окончания и статус,
    затем записывает время конца и длительность в Google Sheets.
    """
    # поддерживаем как callback_query, так и message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        target = query
    else:
        user_id = update.message.from_user.id
        target = update.message

    now = get_now()
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()

    # 1) Помечаем поездку завершённой
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

    # 2) Извлекаем org_name и время старта
    cur.execute(
        "SELECT org_name, start_datetime FROM trips "
        "WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()

    # 3) Получаем ФИО
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # 4) Записываем конец и длительность в Google Sheets
    try:
        await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при записи окончания: {e}")

    # 5) Сообщаем пользователю
    time_str = now.strftime("%H:%M")
    text = f"🏁 Поездка в *{org_name}* завершена в *{time_str}*"
    if isinstance(target, Update) or hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, parse_mode="Markdown")
    else:
        await target.reply_text(text, parse_mode="Markdown")
