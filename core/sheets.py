import gspread
import pandas as pd
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ИД таблицы и имена листов
SPREADSHEET_ID = "10YnZvLU6g-k9a8YvC8tp5xv1sfYC-j0C71z83Add4dQ"
SHEET_USERS = "Пользователи"
SHEET_TRIPS = "Поездки"

# Авторизация через переменную окружения
def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    json_str = os.environ.get("GOOGLE_SHEETS_KEY_FILE")
    if not json_str:
        raise Exception("Переменная окружения GOOGLE_SHEETS_KEY_FILE не найдена")

    info = json.loads(json_str)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
    return gspread.authorize(creds)

# Добавление пользователя
def add_user(user_id: int, full_name: str, username: str):
    client = get_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_USERS)
    users = sheet.col_values(1)
    if str(user_id) not in users:
        sheet.append_row([str(user_id), full_name, username or ""])

# Добавление поездки
def add_trip(full_name: str, org: str, start_time: datetime, end_time: datetime | None = None):
    client = get_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_TRIPS)

    date_str = start_time.strftime('%d.%m.%Y')
    start_str = start_time.strftime('%d.%m.%Y %H:%M')
    end_str = end_time.strftime('%d.%m.%Y %H:%M') if end_time else ''
    duration = ''
    if end_time:
        diff = end_time - start_time
        duration = f"{diff.seconds // 3600:02}:{(diff.seconds % 3600) // 60:02}"

    sheet.append_row([full_name, org, date_str, start_str, end_str, duration])

# Получение отчёта в виде DataFrame
def get_trip_dataframe():
    client = get_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_TRIPS)
    data = sheet.get_all_records()
    return pd.DataFrame(data)
