# core/sheets.py

import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import pandas as pd

# Загружаем .env
load_dotenv()
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON")
SPREADSHEET_ID     = os.getenv("SPREADSHEET_ID")
if not GOOGLE_SHEETS_JSON or not SPREADSHEET_ID:
    raise RuntimeError("Нужно задать GOOGLE_SHEETS_JSON и SPREADSHEET_ID в .env")

# Авторизация
creds_dict = json.loads(GOOGLE_SHEETS_JSON)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds  = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

def _open_sheet(name=None):
    ss = client.open_by_key(SPREADSHEET_ID)
    return ss.worksheet(name) if name else ss.sheet1

def add_trip(full_name: str, org_name: str, start_dt):
    sheet = _open_sheet("Поездки")
    sheet.append_row([
        full_name,
        org_name,
        start_dt.strftime("%d.%m.%Y"),
        start_dt.strftime("%H:%M"),
        "",  # конец
        ""   # длительность
    ], value_input_option="USER_ENTERED")

async def end_trip_in_sheet(full_name: str, org_name: str, start_dt, end_dt, duration):
    sheet = _open_sheet("Поездки")
    data = sheet.get_all_values()
    # ищем последнюю пустую строку для этой поездки
    for i in range(len(data)-1, 0, -1):
        row = data[i]
        if row[0]==full_name and row[1]==org_name and row[4]=="":
            end_str = end_dt.strftime("%H:%M")
            secs = int(duration.total_seconds())
            h, rem = divmod(secs, 3600)
            m, s   = divmod(rem, 60)
            dur_str = f"{h}:{m:02d}" + (f":{s:02d}" if s else "")
            sheet.update_cell(i+1, 5, end_str)
            sheet.update_cell(i+1, 6, dur_str)
            return

def get_trip_dataframe() -> pd.DataFrame:
    """
    Читает ВСЕ поездки из листа 'Поездки' и возвращает DataFrame.
    Фильтрацию по датам делаем в core/report.py.
    """
    sheet = _open_sheet("Поездки")
    records = sheet.get_all_records()
    return pd.DataFrame(records)
