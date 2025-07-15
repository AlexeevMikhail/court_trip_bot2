from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
from core.sheets import get_trip_dataframe  # 👈 Чтение из Google Sheets

ADMIN_IDS = [414634622, 1745732977]

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 У вас нет прав для получения отчёта.",
            parse_mode="Markdown"
        )
        return

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

    df = get_trip_dataframe()
    if df.empty:
        await update.message.reply_text("📭 Нет данных для отчёта.")
        return

    df["Дата"] = pd.to_datetime(df["Дата"], format="%d.%m.%Y", errors="coerce")
    if start_date:
        df = df[df["Дата"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["Дата"] <= pd.to_datetime(end_date)]

    if df.empty:
        await update.message.reply_text("📭 Нет данных за указанный период.")
        return

    def calc_duration(row):
        s = row["Начало поездки"]
        e = row["Конец поездки"]
        if not s or not e or s == "-" or e == "-":
            return "-"
        try:
            dt_s = datetime.strptime(s[-5:], "%H:%M")
            dt_e = datetime.strptime(e[-5:], "%H:%M")
        except:
            return "-"
        delta = dt_e - dt_s
        if delta.total_seconds() < 0:
            delta += timedelta(days=1)
        return f"{delta.seconds // 3600:02}:{(delta.seconds % 3600) // 60:02}"

    df["Продолжительность"] = df.apply(calc_duration, axis=1)

    final = df[[
        "ФИО",
        "Организация",
        "Дата",
        "Начало поездки",
        "Конец поездки",
        "Продолжительность"
    ]]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        final.to_excel(writer, sheet_name="Отчёт", index=False)
        ws = writer.sheets["Отчёт"]
        for idx, col in enumerate(final.columns):
            width = max(final[col].astype(str).map(len).max(), len(col)) + 2
            ws.set_column(idx, idx, width)
    output.seek(0)

    now = datetime.now()
    fname = f"отчет по поездкам {now.strftime('%d.%m.%Y_%H.%M')}.xlsx"
    await update.message.reply_document(document=output, filename=fname)
    await update.message.reply_text("📄 Отчёт сформирован и отправлен.")
