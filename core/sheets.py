import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# ID и названия листов
SPREADSHEET_ID = "10YnZvLU6g-k9a8YvC8tp5xv1sfYC-j0C71z83Add4dQ"
SHEET_USERS = "Пользователи"
SHEET_TRIPS = "Поездки"

# Авторизация через JSON из переменной окружения
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_data = os.environ["GOOGLE_SHEETS_JSON"]
    creds_dict = json.loads(json_data)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# Добавление пользователя
def add_user(user_id: int, full_name: str, username: str):
    try:
        client = get_client()
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_USERS)
        users = sheet.col_values(1)
        if str(user_id) not in users:
            sheet.append_row([str(user_id), full_name, username or ""])
    except Exception as e:
        print(f"[Google Sheets] Ошибка при добавлении пользователя: {e}")

# Добавление поездки
def add_trip(full_name: str, org: str, start_time: datetime, end_time: datetime | None = None):
    try:
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
    except Exception as e:
        print(f"[Google Sheets] Ошибка при добавлении поездки: {e}")

# Получение всех поездок в виде DataFrame
def get_trip_dataframe():
    try:
        client = get_client()
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_TRIPS)
        records = sheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        print(f"[Google Sheets] Ошибка при получении отчёта: {e}")
        return pd.DataFrame()
