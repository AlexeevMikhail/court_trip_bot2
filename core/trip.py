# core/trip.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import sqlite3
from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip, end_trip_in_sheet  # ← добавили импорт

# Словарь организаций
ORGANIZATIONS = {
    'kuzminsky': "Кузьминский районный суд",
    'lefortovsky': "Лефортовский районный суд",
    'lyublinsky': "Люблинский районный суд",
    'meshchansky': "Мещанский районный суд",
    'nagatinsky': "Нагатинский районный суд",
    'perovsky': "Перовский районный суд",
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
    user_id = update.effective_user.id
    if not is_registered(user_id):
        await update.message.reply_text(
            "❌ Вы не зарегистрированы!\n"
            "Отправьте команду: /register Иванов Иван",
            parse_mode="Markdown"
        )
        return

    # Собираем inline‑кнопки
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    await update.message.reply_text(
        "🚗 *Куда вы отправляетесь?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Аналогично start, но для пользовательского ввода
    user_id = update.effective_user.id
    custom_org = update.message.text.strip()
    if not custom_org or not is_registered(user_id):
        await update.message.reply_text("❌ Проверьте регистрацию и название организации.")
        return

    success = save_trip_start(user_id, "other", custom_org)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if not success:
        await update.message.reply_text("❌ Уже в поездке.")
        return

    # Получаем полное имя
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()
    cur.execute("SELECT full_name FROM employees WHERE user_id = ?", (user_id,))
    full_name = cur.fetchone()[0]
    conn.close()

    # Записываем в Google Sheets начало поездки
    try:
        add_trip(full_name, custom_org, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка добавления старта: {e}")

    # Отправляем кнопку завершения
    await update.message.reply_text(
        f"🚀 Поездка в *{custom_org}* начата в *{time_now}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏦 Возврат", callback_data="return_trip")]]
        )
    )

async def handle_trip_save(update: Update, context, org_id: str, org_name: str):
    # Обработчик для готовых организаций
    user_id = update.effective_user.id
    success = save_trip_start(user_id, org_id, org_name)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if not success:
        return await update.callback_query.edit_message_text(
            "❌ Уже в поездке.", parse_mode="Markdown"
        )

    # Получаем имя из БД
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()
    cur.execute("SELECT full_name FROM employees WHERE user_id = ?", (user_id,))
    full_name = cur.fetchone()[0]
    conn.close()

    try:
        add_trip(full_name, org_name, now)  # запись старта в Google Sheets
    except Exception as e:
        print(f"[Google Sheets] Ошибка добавления старта: {e}")

    await update.callback_query.edit_message_text(
        f"🚌 Поездка в *{org_name}* начата в *{time_time}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏦 Возврат", callback_data="return_trip")]]
        )
    )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /return и кнопка «Возврат»."""
    user_id = update.effective_user.id
    now = get_now()

    # Обновляем SQLite
    conn = sqlite3.connect("court_tracking.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )
    updated = cur.rowcount
    conn.commit()

    # Достаём полные данные поездки для Sheets
    if updated:
        cur.execute(
            "SELECT full_name, org_name, start_datetime FROM trips "
            "WHERE user_id = ? AND status = 'completed' "
            "ORDER BY start_datetime DESC LIMIT 1",
            (user_id,)
        )
        full_name, org_name, start_dt = cur.fetchone()
    conn.close()

    # Если поездка найдена — пишем в Google Sheets
    if updated:
        duration = now - start_dt
        try:
            await end_trip_in_sheet(full_name, org_name, start_dt, now, duration)
        except Exception as e:
            print(f"[Google Sheets] Ошибка при закрытии поездки: {e}")

        await update.effective_message.reply_text(
            f"🏁 Поездка в *{org_name}* завершена в *{now.strftime('%H:%M')}*",
            parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(
            "⚠️ У вас нет активной поездки.", parse_mode="Markdown"
        )
