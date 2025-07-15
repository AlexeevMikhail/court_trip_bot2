import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import pandas as pd

# Пути и ID
SPREADSHEET_ID = "10YnZvLU6g-k9a8YvC8tp5xv1sfYC-j0C71z83Add4dQ"
SHEET_USERS = "Пользователи"
SHEET_TRIPS = "Поездки"

# Подключение
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("court-trip-bot-10ea471d3f51.json", scope)
    return gspread.authorize(creds)

# Добавление пользователя
def add_user(user_id: int, full_name: str, username: str):
    client = get_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_USERS)
    users = sheet.col_values(1)
    if str(user_id) not in users:
        sheet.append_row([str(user_id), full_name, username or ""])

# Добавление поездки
def add_trip(user_id: int, org: str):
    client = get_client()
    sheet_users = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_USERS)
    sheet_trips = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_TRIPS)

    # Найдём ФИО по user_id
    users = sheet_users.get_all_values()
    full_name = None
    for row in users[1:]:  # пропускаем заголовок
        if str(user_id) == row[0]:
            full_name = row[1]
            break
    if not full_name:
        return  # Пользователь не найден — не добавляем

    # Время в МСК
    msk = pytz.timezone("Europe/Moscow")
    now = datetime.now(msk)

    date_str = now.strftime('%d.%m.%Y')
    start_str = now.strftime('%d.%m.%Y %H:%M')

    # Добавляем запись
    sheet_trips.append_row([full_name, org, date_str, start_str, '', ''])

# 📥 Получение таблицы поездок как DataFrame
def get_trip_dataframe() -> pd.DataFrame:
    client = get_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_TRIPS)
    data = sheet.get_all_records()
    return pd.DataFrame(data)
