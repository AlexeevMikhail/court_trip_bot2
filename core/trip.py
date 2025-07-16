# trip.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from utils.database import is_registered, save_trip_start, get_now
from core.sheets import add_trip, end_trip_in_sheet   # ← дописали
import sqlite3

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
            "❌ Вы не зарегистрированы!\n"
            "Отправьте команду: `/register Иванов Иван`",
            parse_mode="Markdown"
        )

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

async def handle_trip_save(update: Update, context, org_id: str, org_name: str):
    """Обработка выбора готовой организации (inline‑кнопки)."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    success = save_trip_start(user_id, org_id, org_name)
    now = get_now()
    time_now = now.strftime('%H:%M')

    if success:
        # в SQLite уже сохранено, теперь пишем старт в Sheets
        add_trip(
            full_name := sqlite3.connect("court_tracking.db")
                               .execute("SELECT full_name FROM employees WHERE user_id=?", (user_id,))
                               .fetchone()[0],
            org_name,
            now
        )
        await query.edit_message_text(
            f"🚌 Поездка в *{org_name}* начата в *{time_now}*\nХорошей дороги! 🚗",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ *Не удалось начать поездку.*\nВозможно, вы уже в пути.",
            parse_mode="Markdown"
        )

async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия ‘Завершить поездку’."""
    query = update.callback_query
    if query:
        await query.answer()
        target = query
        user_id = query.from_user.id
    else:
        target = update.message
        user_id = update.message.from_user.id

    now = get_now()

    conn = sqlite3.connect('court_tracking.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE trips 
        SET end_datetime = ?, status = 'completed'
        WHERE user_id = ? AND status = 'in_progress'
    ''', (now, user_id))
    updated = cur.rowcount
    conn.commit()

    if updated:
        # достаём данные, чтобы записать в Sheets
        cur.execute('''
            SELECT full_name, org_name, start_datetime 
            FROM trips 
            WHERE user_id=? AND status='completed'
            ORDER BY start_datetime DESC LIMIT 1
        ''', (user_id,))
        full_name, org_name, start_dt = cur.fetchone()
        conn.close()

        # ЗАПИСЫВАЕМ В SHEETS окончание и длительность
        await end_trip_in_sheet(full_name, org_name, start_dt, now, now - start_dt)

        await target.reply_text(
            f"🏁 Вы успешно вернулись в офис!\n"
            f"Поездка завершена в *{now.strftime('%H:%M')}*",
            parse_mode="Markdown"
        )
    else:
        conn.close()
        await target.reply_text(
            "⚠️ *У вас нет активной поездки*",
            parse_mode="Markdown"
        )
