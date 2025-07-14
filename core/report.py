from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta, time
import sqlite3
import pandas as pd
from io import BytesIO

ADMIN_IDS = [414634622, 1745732977]

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 У вас нет прав для получения отчёта.",
            parse_mode="Markdown"
        )
        return

    # 1) Разбор аргументов: /report [start] [end]
    args = context.args
    start_date = end_date = None
    try:
        if len(args) >= 1:
            start_date = datetime.strptime(args[0], "%d.%m.%Y").date()
        if len(args) >= 2:
            end_date = datetime.strptime(args[1], "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text(
            "📌 Формат команды:\n/report ДД.MM.ГГГГ [ДД.MM.ГГГГ]",
            parse_mode="Markdown"
        )
        return

    # 2) Вытягиваем все поездки
    conn = sqlite3.connect("court_tracking.db")
    df = pd.read_sql("""
        SELECT e.full_name AS ФИО,
               t.organization_name AS Организация,
               t.start_datetime,
               t.end_datetime
        FROM trips t
        JOIN employees e ON t.user_id = e.user_id
        WHERE e.is_active = 1
        ORDER BY t.start_datetime
    """, conn)
    conn.close()

    if df.empty:
        await update.message.reply_text(
            "📭 Нет данных для отчёта.",
            parse_mode="Markdown"
        )
        return

    # 3) Фильтрация по дате через подстроку YYYY-MM-DD
    if start_date:
        iso = start_date.isoformat()
        df = df[df['start_datetime'].astype(str).str.contains(iso, na=False)]
    if end_date and start_date and end_date != start_date:
        days = pd.date_range(start_date, end_date).date
        mask = pd.Series(False, index=df.index)
        for d in days:
            mask |= df['start_datetime'].astype(str).str.contains(d.isoformat(), na=False)
        df = df[mask]

    if df.empty:
        await update.message.reply_text(
            "📭 Нет данных за указанный период.",
            parse_mode="Markdown"
        )
        return

    # 4) Формируем колонки

    # Дата: ДД.MM.ГГГГ
    df['Дата'] = (
        pd.to_datetime(df['start_datetime'].str.slice(0, 10),
                       format="%Y-%m-%d", errors="coerce")
          .dt.strftime("%d.%m.%Y")
    )

    # Начало поездки: ЧЧ:ММ
    df['Начало поездки'] = df['start_datetime'].astype(str).str.slice(11, 16)

    # Конец поездки: ЧЧ:ММ или '-'
    df['Конец поездки'] = (
        df['end_datetime'].astype(str).str.slice(11, 16).fillna("-")
    )

    # 5) Вычисляем продолжительность (чч:мм)
    def calc_duration(row):
        s = row['Начало поездки']
        e = row['Конец поездки']
        if s == "-" or e in (None, "-", ""):
            return "-"
        try:
            dt_s = datetime.strptime(s, "%H:%M")
            dt_e = datetime.strptime(e, "%H:%M")
        except ValueError:
            return "-"
        delta = dt_e - dt_s
        if delta.total_seconds() < 0:
            delta += timedelta(days=1)
        h = delta.seconds // 3600
        m = (delta.seconds % 3600) // 60
        return f"{h:02}:{m:02}"

    df['Продолжительность'] = df.apply(calc_duration, axis=1)

    # 6) Итоговый DataFrame
    final = df[[
        'ФИО',
        'Организация',
        'Дата',
        'Начало поездки',
        'Конец поездки',
        'Продолжительность'
    ]]

    # 7) Запись в Excel с авто‑шириной столбцов
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        final.to_excel(writer, sheet_name='Отчёт', index=False)
        ws = writer.sheets['Отчёт']
        for idx, col in enumerate(final.columns):
            width = max(final[col].astype(str).map(len).max(), len(col)) + 2
            ws.set_column(idx, idx, width)
    output.seek(0)

    # 8) Имя файла: «отчет по поездкам дд.мм.гггг_чч.мм»
    now = datetime.now()
    fname = f"отчет по поездкам {now.strftime('%d.%m.%Y_%H.%M')}.xlsx"

    # 9) Отправка
    await update.message.reply_document(
        document=output,
        filename=fname
    )
    await update.message.reply_text(
        "📄 Отчёт сформирован и отправлен.",
        parse_mode="Markdown"
    )
