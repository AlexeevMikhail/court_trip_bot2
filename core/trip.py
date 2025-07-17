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
    """Показываем inline‑кнопки для выбора организации."""
    query = update.callback_query
    target = query or update.message
    if query:
        await query.answer()

    user_id = target.from_user.id
    if not is_registered(user_id):
        return await target.reply_text(
            "❌ Вы не зарегистрированы!\nОтправьте /register Иванов Иван"
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
    """Сохраняем старт поездки в SQLite и Google Sheets."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # 1) Локальный статус поездки
    if not save_trip_start(user_id, org_id, org_name):
        return await query.edit_message_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_now = now.strftime("%H:%M")

    # 2) Читаем ФИО из таблицы employees
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # 3) Запись старта в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при записи старта: {e}")

    # 4) Предлагаем кнопку «Возврат»
    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_now}*.\nХорошей дороги! 🚗",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏦 Возврат", callback_data="end_trip")]]
        )
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод вручную для 'other'."""
    user_id = update.message.from_user.id
    org_name = update.message.text.strip()

    if not org_name or not is_registered(user_id):
        return await update.message.reply_text("❌ Некорректная организация или вы не зарегистрированы.")

    if not save_trip_start(user_id, "other", org_name):
        return await update.message.reply_text("❌ У вас уже есть незавершённая поездка.")

    now = get_now()
    time_now = now.strftime("%H:%M")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при записи старта: {e}")

    await update.message.reply_text(
        f"🚀 Поездка в *{org_name}* начата в *{time_now}*",
        parse_mode="Markdown"
    )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершаем поездку и пишем время конца + длительность в Google Sheets."""
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

    # 1) Пометить в SQLite
    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    if cur.rowcount == 0:
        conn.commit()
        conn.close()
        return await target.reply_text(
            "⚠️ У вас нет активной поездки.",
            parse_mode="Markdown"
        )
    conn.commit()

    # 2) Достать организацию и время старта
    cur.execute(
        "SELECT organization_name, start_datetime "
        "FROM trips WHERE user_id = ? AND status = 'completed' "
        "ORDER BY start_datetime DESC LIMIT 1",
        (user_id,)
    )
    org_name, start_dt = cur.fetchone()

    # 3) Достать ФИО
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # 4) Запись конца и длительности в Sheets
    try:
        await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при записи окончания: {e}")

    # 5) Ответ пользователю
    text = f"🏁 Поездка в *{org_name}* завершена в *{now.strftime('%H:%M')}*"
    if query:
        await query.edit_message_text(text, parse_mode="Markdown")
    else:
        await target.reply_text(text, parse_mode="Markdown")
