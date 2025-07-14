from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from utils.database import is_registered, save_trip_start, get_now
import sqlite3

# Порядок важен — используем обычный словарь
ORGANIZATIONS = {
    # 1. Московские районные суды (по алфавиту русских названий)
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

    # 2. Мосгорсуд и кассация
    'msk_city': "Московский городской суд",
    'kassatsionny2': "Второй кассационный суд общей юрисдикции",

    # 3. Городские суды Московской области
    'domodedovo': "Домодедовский городской суд",
    'lyuberetsky': "Люберецкий городской суд",
    'vidnoye': "Видновский городской суд",

    # 4. Прочие организации (по алфавиту)
    'justice_peace': "Мировые судьи (судебный участок)",
    'fns': "ФНС",
    'gibdd': "ГИБДД",
    'notary': "Нотариус",
    'post': "Почта России",
    'rosreestr': "Росреестр",

    # 5. Другое
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
    time_now = get_now().strftime("%H:%M")

    if success:
        await update.message.reply_text(
            f"🚀 Поездка в *{custom_org}* начата в *{time_now}*\nХорошей дороги! 🚗",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Не удалось начать поездку. Возможно, вы уже в пути.")

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = get_now()

    conn = sqlite3.connect('court_tracking.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE trips 
        SET end_datetime = ?, status = 'completed'
        WHERE user_id = ? AND status = 'in_progress'
    ''', (now, user_id))

    if cursor.rowcount > 0:
        await update.message.reply_text(
            f"🏁 Вы успешно вернулись в офис!\nПоездка завершена в *{now.strftime('%H:%M')}*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "⚠️ *У вас нет активной поездки*",
            parse_mode="Markdown"
        )

    conn.commit()
    conn.close()

async def handle_trip_save(update: Update, context, org_id: str, org_name: str):
    user_id = update.effective_user.id
    success = save_trip_start(user_id, org_id, org_name)
    time_now = get_now().strftime('%H:%M')

    if success:
        await update.callback_query.edit_message_text(
            f"🚌 Поездка в *{org_name}* начата в *{time_now}*\nХорошей дороги! 🚗",
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            "❌ *Не удалось начать поездку.*\nВозможно, вы уже в пути.",
            parse_mode="Markdown"
        )
