# core/sheets.py

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
    """
    Открывает вкладку по названию или первую, если name=None.
    """
    ss = client.open_by_key(SPREADSHEET_ID)
    return ss.worksheet(name) if name else ss.sheet1


def add_user(full_name: str, user_id: int):
    """
    Регистрирует нового пользователя в листе 'Пользователи'.
    Столбцы: A=ФИО, B=Telegram user_id.
    """
    try:
        sheet = _open_sheet("Пользователи")
    except gspread.exceptions.WorksheetNotFound:
        sheet = _open_sheet()
    sheet.append_row([full_name, str(user_id)], value_input_option="USER_ENTERED")


def add_trip(full_name: str, org_name: str, start_dt: datetime):
    """
    Добавляет в лист 'Поездки' строку со стартом поездки.
    """
    sheet = _open_sheet("Поездки")
    date_str = start_dt.strftime("%d.%m.%Y")
    time_str = start_dt.strftime("%H:%M")
    sheet.append_row(
        [full_name, org_name, date_str, time_str, "", ""],
        value_input_option="USER_ENTERED"
    )
    print(f"[sheets] add_trip: {full_name}, {org_name}, {date_str} {time_str}")


async def end_trip_in_sheet(
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

    # читаем весь лист
    all_values = sheet.get_all_values()
    if not all_values:
        print("[sheets][WARN] лист 'Поездки' пуст")
        return

    header = all_values[0]
    # находим индексы нужных колонок
    try:
        idx_name  = header.index("ФИО")
        idx_org   = header.index("Организация")
        idx_date  = header.index("Дата")
        idx_start = header.index("Начало поездки")
        idx_end   = header.index("Конец поездки")
        idx_dur   = header.index("Продолжительность")
    except ValueError as e:
        print(f"[sheets][ERROR] Не найден заголовок колонки: {e}")
        return

    date_str  = start_dt.strftime("%d.%m.%Y")
    start_str = start_dt.strftime("%H:%M")
    end_str   = end_dt.strftime("%H:%M")
    secs = int(duration.total_seconds())
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    dur_str = f"{h:02d}:{m:02d}" + (f":{s:02d}" if s else "")

    # ищем подходящую строку
    for row_idx, row in enumerate(all_values[1:], start=2):
        if (row[idx_name]  == full_name
            and row[idx_org]   == org_name
            and row[idx_date]  == date_str
            and row[idx_start] == start_str
            and not row[idx_end]
        ):
            # обновляем ячейки
            sheet.update_cell(row_idx, idx_end+1, end_str)
            sheet.update_cell(row_idx, idx_dur+1, dur_str)
            print(f"[sheets] end_trip_in_sheet: row {row_idx} → end={end_str}, dur={dur_str}")
            return

    print(f"[sheets][WARN] Не найдена открытая поездка для "
          f"{full_name}, {org_name} ({date_str} {start_str})")


def add_plan(full_name: str, org_name: str, plan_date: datetime.date, plan_time: str):
    """
    Добавляет строку в лист 'Календарь' и вставляет её по дате.
    """
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
    sheet.append_row([date_str, full_name, org_name, plan_time],
                     value_input_option="USER_ENTERED")


def get_trip_dataframe() -> pd.DataFrame:
    """
    Возвращает DataFrame со всеми записями листа 'Поездки'.
    """
    sheet = _open_sheet("Поездки")
    return pd.DataFrame(sheet.get_all_records())


def get_calendar_dataframe() -> pd.DataFrame:
    """
    Возвращает DataFrame со всеми записями листа 'Календарь'.
    """
    sheet = _open_sheet("Календарь")
    return pd.DataFrame(sheet.get_all_records())
