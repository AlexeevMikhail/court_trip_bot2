# export_full_history.py

import sqlite3
import pandas as pd
from datetime import datetime, time
from io import BytesIO

DB_PATH = "court_tracking.db"

def export_full_history():
    # 1) Загружаем всю историю поездок
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT
            e.full_name AS ФИО,
            t.organization_name AS Организация,
            t.start_datetime,
            t.end_datetime,
            t.status
        FROM trips t
        JOIN employees e ON t.user_id = e.user_id
        WHERE e.is_active = 1
        ORDER BY t.start_datetime
    """, conn)
    conn.close()

    if df.empty:
        print("⚠️ Нет данных в истории поездок.")
        return

    # 2) Парсим start_datetime и end_datetime (до секунд)
    df['start_dt'] = pd.to_datetime(
        df['start_datetime'].astype(str).str.slice(0, 19),
        format="%Y-%m-%d %H:%M:%S",
        errors='coerce'
    )
    df['end_dt'] = pd.to_datetime(
        df['end_datetime'].astype(str).str.slice(0, 19),
        format="%Y-%m-%d %H:%M:%S",
        errors='coerce'
    )

    # 3) Сдвиг начала до 09:00, если раньше
    WORK_START = time(9, 0)
    def fix_start(dt):
        if pd.isna(dt):
            return dt
        return dt.replace(hour=9, minute=0) if dt.time() < WORK_START else dt

    df['Начало поездки'] = df['start_dt'].apply(fix_start)

    # 4) Для завершённых поездок — показываем фактическое окончание,
    #    для незавершённых — ставим пустую строку
    df['Конец поездки'] = df['end_dt'].dt.strftime("%H:%M").fillna("-")

    # 5) Продолжительность (если end_dt есть)
    df['Продолжительность'] = (
        df['end_dt'] - df['Начало поездки']
    ).apply(lambda td: (
        f"{int(td.total_seconds()//3600):02}:{int((td.total_seconds()%3600)//60):02}"
        if pd.notnull(td) and td.total_seconds() >= 0 else "-"
    ))

    # 6) Колонка «Дата» из start_dt
    df['Дата'] = df['start_dt'].dt.strftime("%d.%m.%Y")

    # 7) Окончательная табличка
    report_df = df[[
        'ФИО',
        'Организация',
        'Дата',
        'Начало поездки',
        'Конец поездки',
        'Продолжительность'
    ]]

    # 8) Экспортим во Excel с автошириной
    output_file = f"FullHistory_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        report_df.to_excel(writer, sheet_name='История', index=False)
        wb = writer.book
        ws = writer.sheets['История']
        for idx, col in enumerate(report_df.columns):
            max_len = max(report_df[col].astype(str).map(len).max(), len(col)) + 2
            ws.set_column(idx, idx, max_len)
    print(f"✅ История экспортирована в {output_file}")

if __name__ == "__main__":
    export_full_history()
