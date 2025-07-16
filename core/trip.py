# core/trip.py

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import sqlite3
from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip, end_trip_in_sheet

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
        return await update.message.reply_text(
            "❌ Вы не зарегистрированы!\nОтправьте /register Иванов Иван"
        )

    # Формируем клавиатуру из списка организаций
    buttons = [[name] for name in ORGANIZATIONS.values()]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    await update.message.reply_text(
        "🚗 Куда вы отправляетесь?\nВыберите организацию из меню:",
        reply_markup=markup
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ручного ввода организации (для 'Другой')."""
    user_id = update.effective_user.id
    org_name = update.message.text.strip()
    if not org_name or not is_registered(user_id):
        return await update.message.reply_text("❌ Некорректная организация или вы не зарегистрированы.")

    success = save_trip_start(user_id, "other", org_name)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if not success:
        return await update.message.reply_text("❌ У вас уже есть незавершённая поездка.")

    # Получаем ФИО из БД
    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    # Запись в Google Sheets
    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка добавления старта: {e}")

    await update.message.reply_text(
        f"🚀 Поездка в *{org_name}* начата в _{time_now}_",
        parse_mode="Markdown"
    )

async def handle_trip_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора предустановленной организации."""
    org_name = update.message.text
    user_id = update.effective_user.id

    if org_name not in ORGANIZATIONS.values():
        return await update.message.reply_text("❌ Пожалуйста, выберите организацию из меню.")

    success = save_trip_start(user_id, org_name, org_name)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if not success:
        return await update.message.reply_text("❌ У вас уже есть незавершённая поездка.")

    conn = sqlite3.connect("court_tracking.db")
    full_name = conn.execute(
        "SELECT full_name FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()

    try:
        add_trip(full_name, org_name, now)
    except Exception as e:
        print(f"[Google Sheets] Ошибка добавления старта: {e}")

    await update.message.reply_text(
        f"🚌 Поездка в *{org_name}* начата в _{time_now}_",
        parse_mode="Markdown"
    )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение поездки (через кнопку меню или команду /return)."""
    user_id = update.effective_user.id
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
        cur.execute(
            "SELECT full_name, org_name, start_datetime FROM trips "
            "WHERE user_id = ? AND status = 'completed' "
            "ORDER BY start_datetime DESC LIMIT 1",
            (user_id,)
        )
        full_name, org_name, start_dt = cur.fetchone()
        conn.close()

        # Фиксируем окончание в Google Sheets
        try:
            await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)
        except Exception as e:
            print(f"[Google Sheets] Ошибка при закрытии поездки: {e}")

        await update.message.reply_text(
            f"🏁 Поездка в *{org_name}* завершена в _{now.strftime('%H:%M')}_",
            parse_mode="Markdown"
        )
    else:
        conn.close()
        await update.message.reply_text("⚠️ У вас нет активной поездки.")
