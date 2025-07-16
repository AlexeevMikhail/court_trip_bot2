# core/report.py

from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import pandas as pd
from io import BytesIO
from core.sheets import get_trip_dataframe

# ID админов, которые могут делать отчёт
ADMIN_IDS = [414634622, 1745732977]

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text("🚫 У вас нет прав для отчёта.")

    args = context.args
    # парсим даты, если указаны
    start_date = end_date = None
    try:
        if len(args) >= 1:
            start_date = datetime.strptime(args[0], "%d.%m.%Y")
        if len(args) >= 2:
            end_date = datetime.strptime(args[1], "%d.%m.%Y")
    except ValueError:
        return await update.message.reply_text("📌 Формат: /report ДД.MM.ГГГГ [ДД.MM.ГГГГ]")

    df = get_trip_dataframe()
    if df.empty:
        return await update.message.reply_text("📭 Данных нет.")

    # приводим колонку «Дата» к datetime
    df["Дата"] = pd.to_datetime(df["Дата"], dayfirst=True, format="%d.%m.%Y", errors="coerce")
    if start_date:
        df = df[df["Дата"] >= start_date]
    if end_date:
        df = df[df["Дата"] <= end_date]

    if df.empty:
        return await update.message.reply_text("📭 Данных за указанный период нет.")

    # рассчитываем продолжительность, если её не было
    def calc_duration(r):
        s, e = r["Начало поездки"], r["Конец поездки"]
        try:
            ts = datetime.strptime(s, "%H:%M")
            te = datetime.strptime(e, "%H:%M")
        except:
            return "-"
        delta = te - ts
        if delta.total_seconds() < 0:
            delta += pd.Timedelta(days=1)
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, _   = divmod(rem, 60)
        return f"{h:02d}:{m:02d}"

    df["Продолжительность"] = df.apply(calc_duration, axis=1)

    # формируем файл Excel
    final = df[["ФИО","Организация","Дата","Начало поездки","Конец поездки","Продолжительность"]]
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        final.to_excel(w, index=False, sheet_name="Отчёт")
        ws = w.sheets["Отчёт"]
        for i, col in enumerate(final.columns):
            width = max(final[col].astype(str).map(len).max(), len(col)) + 2
            ws.set_column(i, i, width)
    buf.seek(0)

    fname = f"report_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx"
    await update.message.reply_document(document=buf, filename=fname)
    await update.message.reply_text("📄 Готово.")
