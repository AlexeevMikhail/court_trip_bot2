# core/sheets.py

import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# 1. Загружаем переменные окружения
from dotenv import load_dotenv
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

def _open_sheet():
    """
    Открывает первую вкладку таблицы по ключу и возвращает объект worksheet.
    """
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return spreadsheet.sheet1


def add_trip(full_name: str, org_name: str, start_dt: datetime):
    """
    Добавляет новую строку в Google Sheets с данными о начале поездки.
    Структура столбцов:
    A: ФИО
    B: Организация
    C: Дата
    D: Начало поездки
    E: (Конец поездки — пусто)
    F: (Продолжительность — пусто)
    """
    sheet = _open_sheet()
    date_str      = start_dt.strftime("%d.%m.%Y")
    start_str     = start_dt.strftime("%H:%M")
    row = [full_name, org_name, date_str, start_str, "", ""]
    sheet.append_row(row, value_input_option="USER_ENTERED")


async def end_trip_in_sheet(
    full_name: str,
    org_name:   str,
    start_dt:   datetime,
    end_dt:     datetime,
    duration:   timedelta
):
    """
    Дописывает в Google Sheets время конца и продолжительность к последней незавершённой поездке.
    Ищем снизу вверх первую строку, у которой:
      - Колонка A == full_name
      - Колонка B == org_name
      - Колонка E == "" (пустая)
    Затем обновляем:
      E: end_dt.strftime("%H:%M")
      F: строковое представление duration (например "0:37:12")
    """
    sheet = _open_sheet()
    # Берём все данные
    all_values = sheet.get_all_values()
    # Идём с конца, пропуская заголовок (строка 1)
    for idx in range(len(all_values)-1, 0, -1):
        row = all_values[idx]
        if row[0] == full_name and row[1] == org_name and row[4] == "":
            # Нашли нужную строку
            end_str      = end_dt.strftime("%H:%M")
            # Форматируем duration как H:MM или H:MM:SS
            total_seconds = int(duration.total_seconds())
            hours   = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if seconds:
                dur_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                dur_str = f"{hours}:{minutes:02d}"
            # Обновляем ячейки (нумерация строк/столбцов в gspread — с 1)
            sheet.update_cell(idx+1, 5, end_str)   # колонка E
            sheet.update_cell(idx+1, 6, dur_str)   # колонка F
            return
    # Если не нашли — можно залогировать
    print(f"[Google Sheets] Не найдена открытая поездка для {full_name}, {org_name}")
