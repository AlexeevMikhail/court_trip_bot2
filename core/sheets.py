# core/sheets.py

import os
import json
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. Подгружаем .env
load_dotenv()
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON")
SPREADSHEET_ID     = os.getenv("SPREADSHEET_ID")

if not GOOGLE_SHEETS_JSON or not SPREADSHEET_ID:
    raise ValueError("Не заданы GOOGLE_SHEETS_JSON или SPREADSHEET_ID в .env")

# 2. Авторизация
creds_dict = json.loads(GOOGLE_SHEETS_JSON)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds  = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

def _open_sheet(name: str = None):
    """
    Открывает лист по имени (если указано) или первую вкладку.
    """
    ss = client.open_by_key(SPREADSHEET_ID)
    return ss.worksheet(name) if name else ss.sheet1

def add_user(full_name: str, user_id: int):
    """
    Добавляет пользователя в лист 'Пользователи'.
    """
    try:
        sheet = _open_sheet("Пользователи")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    sheet.append_row([full_name, str(user_id)], value_input_option="USER_ENTERED")

def add_trip(full_name: str, org_name: str, start_dt: datetime):
    """
    Добавляет новую строку в лист 'Поездки' с началом поездки.
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    sheet.append_row([
        full_name,
        org_name,
        start_dt.strftime("%d.%m.%Y"),
        start_dt.strftime("%H:%M"),
        "",  # конец
        ""   # длительность
    ], value_input_option="USER_ENTERED")

async def end_trip_in_sheet(
        full_name: str,
        org_name:   str,
        start_dt:   datetime,
        end_dt:     datetime,
        duration:   timedelta
    ):
    """
    Находит последнюю открытую поездку в листе 'Поездки'
    и дописывает время конца и продолжительность.
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()

    all_values = sheet.get_all_values()
    # идём снизу вверх, пропуская заголовок
    for idx in range(len(all_values)-1, 0, -1):
        row = all_values[idx]
        if row[0]==full_name and row[1]==org_name and row[4]=="":
            end_str = end_dt.strftime("%H:%M")
            secs    = int(duration.total_seconds())
            h, m = divmod(secs, 3600)
            m, s = divmod(m, 60)
            dur_str = f"{h}:{m:02d}" + (f":{s:02d}" if s else "")
            sheet.update_cell(idx+1, 5, end_str)
            sheet.update_cell(idx+1, 6, dur_str)
            return
    print(f"[Google Sheets] Не найдена открытая поездка для {full_name}, {org_name}")
# core/sheets.py (продолжение)

def get_trip_dataframe(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Возвращает pandas.DataFrame со всеми поездками из листа 'Поездки'
    в диапазоне [start_date; end_date], где даты в формате 'ДД.MM.ГГГГ'.
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    records = sheet.get_all_records()  # список словарей по заголовкам столбцов

    df = pd.DataFrame(records)
    # Приводим колонки к нужным типам
    df["Дата"] = pd.to_datetime(df["Дата"], dayfirst=True, format="%d.%m.%Y")
    # Фильтр по дате
    start = pd.to_datetime(start_date, dayfirst=True, format="%d.%m.%Y")
    end   = pd.to_datetime(end_date,   dayfirst=True, format="%d.%m.%Y")
    mask  = (df["Дата"] >= start) & (df["Дата"] <= end)
    return df.loc[mask]
