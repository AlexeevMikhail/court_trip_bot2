# core/trip.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip, end_trip_in_sheet   # ← добавили end_trip_in_sheet
import sqlite3

# Словарь организаций
ORGANIZATIONS = {
    'kuzminsky': "Кузьминский районный суд",
    'lefortovsky': "Лефортовский районный суд",
    'lyublinsky': "Люблинский районный суд",
    'meshchansky': "Мещанский районный суд",
    'nagatinsky': "Нагатинский районный суд",
    'perovsky': "Перовский районский суд",
    'shcherbinsky': "Щербинский районный суд",
    'tverskoy': "Тверской районный суд",
    'cheremushkinsky': "Черемушкинский районный суд",
    'chertanovsky': "Чертановский районный суд",
    'msk_city': "Московский городской суд",
    'kassatsionny2': "Второй кассационный суд общей юрисдикции",
    'domodedovo': "Домодедовский городской суд",
    'lyuberetsky': "Люберецкий городской суд",
    'vidnoye': "Видновский городской суд",
    'justice_peace': "Мировые судьи (судебный участок)",
    'fns': "ФНС",
    'gibdd': "ГИБДД",
    'notary': "Нотариус",
    'post': "Почта России",
    'rosreestr': "Росреестр",
    'other': "Другая организация (указать)"
}

async def start_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашиваем у пользователя организацию — показываем inline‑кнопки."""
    query = update.callback_query
    if query:
        await query.answer()
    else:
        # пришли сюда из меню
        pass

    user_id = (query or update.message).from_user.id
    if not is_registered(user_id):
        target = query or update.message
        return await target.reply_text("❌ Вы не зарегистрированы! Отправьте /register Иванов Иван")

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    await (query or update.message).reply_text(
        "🚗 *Куда вы отправляетесь?*\nВыберите организацию:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_trip_save(update: Update, context: ContextTypes.DEFAULT_TYPE, org_id: str, org_name: str):
    """Обрабатываем выбор готовой организации из inline‑кнопок."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    success = save_trip_start(user_id, org_id, org_name)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if not success:
        return await query.edit_message_text("❌ У вас уже есть незавершённая поездка.")

    # Получаем ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # Запись старта в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при добавлении старта: {e}")

    # Отвечаем и выводим кнопку завершения
    await query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_now}*\nХорошей дороги! 🚗",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏁 Завершить поездку", callback_data="end_trip")]]
        )
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем ручной ввод названия организации (если выбрали «Другая»)."""
    user_id = update.message.from_user.id
    org_name = update.message.text.strip()

    if not org_name or not is_registered(user_id):
        return await update.message.reply_text("❌ Некорректная организация или вы не зарегистрированы.")

    success = save_trip_start(user_id, "other", org_name)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if not success:
        return await update.message.reply_text("❌ У вас уже есть незавершённая поездка.")

    # Получаем ФИО
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # Запись старта в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при добавлении старта: {e}")

    await update.message.reply_text(
        f"🚀 Поездка в *{org_name}* начата в *{time_now}*",
        parse_mode="Markdown"
    )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем завершение поездки (inline‑кнопка или /return)."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.message.from_user.id

    now = get_now()
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    updated = cur.rowcount
    conn.commit()

    if updated:
        # Извлекаем данные последней завершённой поездки
        cur.execute(
            "SELECT full_name, org_name, start_datetime FROM trips "
            "WHERE user_id = ? AND status = 'completed' "
            "ORDER BY start_datetime DESC LIMIT 1",
            (user_id,)
        )
        full_name, org_name, start_dt = cur.fetchone()
        conn.close()

        # Запись окончания в Google Sheets
        try:
            await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)
        except Exception as e:
            print(f"[Google Sheets] Ошибка при записи окончания поездки: {e}")

        text = f"🏁 Поездка в *{org_name}* завершена в *{now.strftime('%H:%M')}*"
    else:
        conn.close()
        text = "⚠️ У вас нет активной поездки."

    # Отправляем результат
    if query:
        await query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")
