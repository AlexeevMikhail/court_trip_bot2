import os
import json
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Подгружаем .env
load_dotenv()
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON")
SPREADSHEET_ID     = os.getenv("SPREADSHEET_ID")
if not GOOGLE_SHEETS_JSON or not SPREADSHEET_ID:
    raise ValueError("Не заданы GOOGLE_SHEETS_JSON или SPREADSHEET_ID в .env")

# Авторизация в Google Sheets
creds_dict = json.loads(GOOGLE_SHEETS_JSON)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds  = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

def _open_sheet(name: str = None):
    ss = client.open_by_key(SPREADSHEET_ID)
    return ss.worksheet(name) if name else ss.sheet1

def add_user(full_name: str, user_id: int):
    try:
        sheet = _open_sheet("Пользователи")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    sheet.append_row([full_name, str(user_id)], value_input_option="USER_ENTERED")

def add_trip(full_name: str, org_name: str, start_dt: datetime):
    sheet = _open_sheet("Поездки")
    date_str  = start_dt.strftime("%d.%m.%Y")
    time_str  = start_dt.strftime("%H:%M")
    sheet.append_row([full_name, org_name, date_str, time_str, "", ""],
                     value_input_option="USER_ENTERED")
    print(f"[sheets] add_trip: {full_name}, {org_name}, {date_str} {time_str}")

def end_trip_in_sheet(
    full_name: str,
    org_name:   str,
    start_dt:   datetime,
    end_dt:     datetime,
    duration:   timedelta
):
    """
    Находит последнюю незавершённую поездку и дополняет её:
      E: время окончания, F: продолжительность
    """
    sheet = _open_sheet("Поездки")
    records = sheet.get_all_records()
    date_str  = start_dt.strftime("%d.%m.%Y")
    start_str = start_dt.strftime("%H:%M")

    for idx, row in enumerate(records, start=2):
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

            sheet.update_cell(idx, 5, end_str)
            sheet.update_cell(idx, 6, dur_str)
            print(f"[sheets] end_trip_in_sheet: updated row {idx} → end={end_str}, dur={dur_str}")
            return

    print(f"[sheets] WARN: Не найдена открытая поездка для "
          f"{full_name}, {org_name} ({date_str} {start_str})")

def add_plan(full_name: str, org_name: str, plan_date: datetime.date, plan_time: str):
    sheet = _open_sheet("Календарь")
    date_str = plan_date.strftime("%d.%m.%Y")
    rows = sheet.get_all_values()
    for idx, row in enumerate(rows[1:], start=2):
        try:
            cell_date = datetime.strptime(row[0], "%d.%m.%Y").date()
        except:
            continue
        if cell_date > plan_date:
            sheet.insert_row([date_str, full_name, org_name, plan_time], idx)
            return
    sheet.append_row([date_str, full_name, org_name, plan_time], value_input_option="USER_ENTERED")

def get_trip_dataframe() -> pd.DataFrame:
    sheet = _open_sheet("Поездки")
    return pd.DataFrame(sheet.get_all_records())

def get_calendar_dataframe() -> pd.DataFrame:
    sheet = _open_sheet("Календарь")
    return pd.DataFrame(sheet.get_all_records())
