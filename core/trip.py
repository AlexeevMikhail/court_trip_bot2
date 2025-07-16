# core/trip.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip  # интеграция с Google Sheets
import sqlite3

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
            "Отправьте команду: `/register Иванов Иван`",
            parse_mode="Markdown"
        )
        return

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"org_{org_id}")]
        for org_id, name in ORGANIZATIONS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚗 *Куда вы отправляетесь?*\n"
        "Пожалуйста, выберите организацию ниже:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_custom_org_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    custom_org = update.message.text.strip()

    if not custom_org:
        await update.message.reply_text("❌ Название организации не может быть пустым.")
        return
    if not is_registered(user_id):
        await update.message.reply_text("❌ Вы не зарегистрированы.")
        return

    success = save_trip_start(user_id, "other", custom_org)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if success:
        # получаем имя
        conn = sqlite3.connect("court_tracking.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT full_name FROM employees WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        full_name = row[0] if row else "Неизвестный пользователь"

        try:
            add_trip(full_name, custom_org, now)
        except Exception as e:
            print(f"[Google Sheets] Ошибка при добавлении поездки: {e}")

        # выводим сообщение и кнопку Завершить
        await update.message.reply_text(
            f"🚀 Поездка в *{custom_org}* начата в *{time_now}*\nХорошей дороги! 🚗",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏁 Завершить поездку", callback_data="end_trip")]]
            )
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось начать поездку. Возможно, вы уже в пути."
        )

async def handle_trip_save(update: Update, context, org_id: str, org_name: str):
    # то же, что handle_custom_org_input, только для готовых org_id
    user_id = update.effective_user.id
    success = save_trip_start(user_id, org_id, org_name)
    now = get_now()
    time_now = now.strftime("%H:%M")

    if success:
        conn = sqlite3.connect("court_tracking.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT full_name FROM employees WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        full_name = row[0] if row else "Неизвестный пользователь"

        try:
            add_trip(full_name, org_name, now)
        except Exception as e:
            print(f"[Google Sheets] Ошибка при добавлении поездки: {e}")

        await update.callback_query.edit_message_text(
            f"🚌 Поездка в *{org_name}* начата в *{time_now}*\nХорошей дороги! 🚗",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏁 Завершить поездку", callback_data="end_trip")]]
            )
        )
    else:
        await update.callback_query.edit_message_text(
            "❌ *Не удалось начать поездку.*\nВозможно, вы уже в пути.",
            parse_mode="Markdown"
        )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = get_now()

    # обновляем БД
    conn = sqlite3.connect('court_tracking.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE trips SET end_datetime = ?, status = 'completed' "
        "WHERE user_id = ? AND status = 'in_progress'",
        (now, user_id)
    )

    if cursor.rowcount > 0:
        text = f"🏁 Поездка завершена в *{now.strftime('%H:%M')}*"
    else:
        text = "⚠️ *У вас нет активной поездки*"

    conn.commit()
    conn.close()

    # отправляем результат
    await update.effective_message.reply_text(text, parse_mode="Markdown")
