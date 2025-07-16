# core/sheets.py

import os
import json
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. Загружаем .env
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
    Открывает лист по имени (если указан) или первую вкладку.
    """
    ss = client.open_by_key(SPREADSHEET_ID)
    return ss.worksheet(name) if name else ss.sheet1

def add_user(full_name: str, user_id: int):
    """
    Добавляет нового пользователя в лист 'Пользователи'.
    Столбцы: A=ФИО, B=Telegram user_id.
    """
    try:
        sheet = _open_sheet("Пользователи")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    sheet.append_row([full_name, str(user_id)], value_input_option="USER_ENTERED")

def add_trip(full_name: str, org_name: str, start_dt: datetime):
    """
    Добавляет новую строку в лист 'Поездки' с данными о начале поездки.
    Структура столбцов:
    A: ФИО, B: Организация, C: Дата, D: Начало поездки, E: Конец поездки (пусто), F: Продолжительность (пусто)
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    row = [
        full_name,
        org_name,
        start_dt.strftime("%d.%m.%Y"),
        start_dt.strftime("%H:%M"),
        "",
        ""
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")

async def end_trip_in_sheet(
    full_name: str,
    org_name:   str,
    start_dt:   datetime,
    end_dt:     datetime,
    duration:   timedelta
):
    """
    Закрывает последнюю активную поездку в листе 'Поездки',
    заполняя время конца и продолжительность.
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()

    all_values = sheet.get_all_values()
    # Ищем снизу вверх первую пустую строку для этой поездки
    for idx in range(len(all_values)-1, 0, -1):
        row = all_values[idx]
        if row[0] == full_name and row[1] == org_name and row[4] == "":
            end_str = end_dt.strftime("%H:%M")
            total_seconds = int(duration.total_seconds())
            hours   = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            dur_str = f"{hours}:{minutes:02d}" + (f":{seconds:02d}" if seconds else "")
            # Обновляем ячейки (строки и столбцы считаются с 1)
            sheet.update_cell(idx+1, 5, end_str)  # колонка E
            sheet.update_cell(idx+1, 6, dur_str)  # колонка F
            return
    print(f"[Google Sheets] Не найдена открытая поездка для {full_name}, {org_name}")

def get_trip_dataframe() -> pd.DataFrame:
    """
    Возвращает pandas.DataFrame со всеми записями из листа 'Поездки'.
    Фильтрация по датам делается в core/report.py.
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    records = sheet.get_all_records()  # список словарей по заголовкам
    return pd.DataFrame(records)
