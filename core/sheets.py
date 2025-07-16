# core/sheets.py

import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. Загружаем .env
load_dotenv()
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON")
SPREADSHEET_ID     = os.getenv("SPREADSHEET_ID")

if not GOOGLE_SHEETS_JSON or not SPREADSHEET_ID:
    raise ValueError("Не заданы GOOGLE_SHEETS_JSON или SPREADSHEET_ID в .env")

# 2. Авторизация в Google API
creds_dict = json.loads(GOOGLE_SHEETS_JSON)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds  = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

def _open_sheet(name: str = None):
    """
    Открывает нужный лист: если name указан — по названию, иначе первая вкладка.
    """
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    if name:
        return spreadsheet.worksheet(name)
    return spreadsheet.sheet1

def add_user(full_name: str, user_id: int):
    """
    Добавляет нового пользователя в Google Sheets.
    Запись идёт в лист 'Пользователи' (если такого нет — в первую вкладку).
    Столбцы: A=ФИО, B=Telegram user_id.
    """
    try:
        sheet = _open_sheet("Пользователи")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()  # fallback на первую вкладку
    row = [full_name, str(user_id)]
    sheet.append_row(row, value_input_option="USER_ENTERED")

def add_trip(full_name: str, org_name: str, start_dt: datetime):
    """
    Добавляет строку с началом поездки в лист 'Поездки' или первую вкладку.
    Столбцы:
      A: ФИО
      B: Организация
      C: Дата
      D: Начало поездки (HH:MM)
      E: Конец поездки  (оставляем пустым)
      F: Продолжительность (оставляем пустым)
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    date_str  = start_dt.strftime("%d.%m.%Y")
    start_str = start_dt.strftime("%H:%M")
    sheet.append_row([full_name, org_name, date_str, start_str, "", ""],
                     value_input_option="USER_ENTERED")

async def end_trip_in_sheet(
    full_name: str,
    org_name:   str,
    start_dt:   datetime,
    end_dt:     datetime,
    duration:   timedelta
):
    """
    Обновляет в листе 'Поездки' (или первой вкладке) время конца и длительность поездки.
    Ищем последнюю пустую строку для данного full_name/org_name и заполняем:
    E: end_dt.strftime("%H:%M")
    F: формат duration (H:MM или H:MM:SS)
    """
    try:
        sheet = _open_sheet("Поездки")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()

    all_values = sheet.get_all_values()
    for idx in range(len(all_values)-1, 0, -1):
        row = all_values[idx]
        if row[0] == full_name and row[1] == org_name and row[4] == "":
            end_str = end_dt.strftime("%H:%M")
            total_seconds = int(duration.total_seconds())
            hours   = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            dur_str = f"{hours}:{minutes:02d}" + (f":{seconds:02d}" if seconds else "")
            sheet.update_cell(idx+1, 5, end_str)   # колонка E
            sheet.update_cell(idx+1, 6, dur_str)   # колонка F
            return
    print(f"[Google Sheets] Не найдена открытая поездка для {full_name}, {org_name}")
