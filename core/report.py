from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import sqlite3
import pandas as pd
from io import BytesIO

ADMIN_IDS = [414634622]  # Замените на актуальные ID

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 *У вас нет прав для получения отчёта.*",
            parse_mode="Markdown"
        )
        return

    try:
        start_date = datetime.strptime(context.args[0], '%d.%m.%Y').date() if context.args else None
        end_date = datetime.strptime(context.args[1], '%d.%m.%Y').date() if len(context.args) > 1 else None
    except (ValueError, IndexError):
        await update.message.reply_text(
            "📌 *Используйте формат:*\n`/report ДД.ММ.ГГГГ ДД.ММ.ГГГГ`",
            parse_mode="Markdown"
        )
        return

    conn = sqlite3.connect("court_tracking.db")
    query = '''
        SELECT e.full_name, t.organization_name, t.start_datetime, t.end_datetime
        FROM employees e
        JOIN trips t ON e.user_id = t.user_id
        WHERE e.is_active = 1
    '''
    params = []
    if start_date:
        query += " AND date(t.start_datetime) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(t.start_datetime) <= ?"
        params.append(end_date)

    df = pd.read_sql(query, conn, params=params)
    conn.close()

    if df.empty:
        await update.message.reply_text(
            "📭 *Нет данных за указанный период.*",
            parse_mode="Markdown"
        )
        return

    df["Продолжительность (часы)"] = (
        pd.to_datetime(df["end_datetime"]) - pd.to_datetime(df["start_datetime"])
    ).dt.total_seconds() / 3600
    df["Дата"] = pd.to_datetime(df["start_datetime"]).dt.date

    # Переименование столбцов на русский язык
    df.rename(columns={
        "full_name": "ФИО",
        "organization_name": "Организация",
        "start_datetime": "Начало поездки",
        "end_datetime": "Конец поездки"
    }, inplace=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Отчёт", index=False)

    output.seek(0)
    await update.message.reply_document(
        document=output,
        filename=f"Отчёт_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )

    await update.message.reply_text(
        "📄 *Отчёт сформирован и отправлен.*",
        parse_mode="Markdown"
    )
