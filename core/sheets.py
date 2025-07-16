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
    Открывает вкладку по названию или первую, если name=None.
    """
    ss = client.open_by_key(SPREADSHEET_ID)
    return ss.worksheet(name) if name else ss.sheet1

def add_trip(full_name: str, org_name: str, start_dt: datetime):
    """
    Добавляет в лист 'Поездки' строку со стартом поездки.
    """
    sheet = _open_sheet("Поездки")
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
    Находит в листе 'Поездки' последнюю незавершённую поездку
    (совпадают ФИО, организация, дата и время старта) и дописывает:
      E: время окончания (HH:MM)
      F: длительность (H:MM или H:MM:SS)
    """
    sheet = _open_sheet("Поездки")
    records = sheet.get_all_records()  # список словарей по заголовкам

    # Строка заголовков:
    # 'ФИО','Организация','Дата','Начало поездки','Конец поездки','Продолжительность'
    date_str  = start_dt.strftime("%d.%m.%Y")
    start_str = start_dt.strftime("%H:%M")

    for idx, row in enumerate(records, start=2):  # реальные номера строк в таблице
        if (row.get("ФИО") == full_name
            and row.get("Организация") == org_name
            and row.get("Дата") == date_str
            and row.get("Начало поездки") == start_str
            and not row.get("Конец поездки")):

            end_str = end_dt.strftime("%H:%M")
            secs = int(duration.total_seconds())
            h, rem = divmod(secs, 3600)
            m, s   = divmod(rem, 60)
            dur_str = f"{h}:{m:02d}" + (f":{s:02d}" if s else "")

            sheet.update_cell(idx, 5, end_str)   # колонка E
            sheet.update_cell(idx, 6, dur_str)   # колонка F
            return

    # Если мы сюда попали — ничего не нашли, логируем
    print(f"[Google Sheets] Не найдена открытая поездка для "
          f"{full_name}, {org_name} ({date_str} {start_str})")

def get_trip_dataframe() -> pd.DataFrame:
    """
    Возвращает DataFrame со всеми строками из листа 'Поездки'.
    Фильтрация по датам делается в core/report.py.
    """
    sheet = _open_sheet("Поездки")
    records = sheet.get_all_records()
    return pd.DataFrame(records)
