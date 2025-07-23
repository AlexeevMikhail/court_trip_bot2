# sync_users.py

import os
import sqlite3
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1) Загрузим настройки из .env
from dotenv import load_dotenv
load_dotenv()
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON")
SPREADSHEET_ID     = os.getenv("SPREADSHEET_ID")
DB_PATH            = "court_tracking.db"

if not GOOGLE_SHEETS_JSON or not SPREADSHEET_ID:
    raise RuntimeError("Не задана конфигурация Google Sheets в .env")

# 2) Авторизуемся в Google Sheets
creds_dict = json.loads(GOOGLE_SHEETS_JSON)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds  = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc     = gspread.authorize(creds)

# 3) Открываем лист «Пользователи»
sh    = gc.open_by_key(SPREADSHEET_ID)
try:
    ws = sh.worksheet("Пользователи")
except gspread.exceptions.WorksheetNotFound:
    # если листа нет — создаём его
    ws = sh.add_worksheet(title="Пользователи", rows="1000", cols="3")

def sync_users():
    # 4) Считаем из SQLite всех пользователей
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT full_name, user_id FROM employees ORDER BY full_name"
    ).fetchall()
    conn.close()

    # 5) Очищаем лист и прописываем шапку
    ws.clear()
    ws.append_row(["ФИО", "Telegram ID"], value_input_option="USER_ENTERED")

    # 6) Проставляем всех пользователей
    for full_name, user_id in rows:
        ws.append_row([full_name, str(user_id)], value_input_option="USER_ENTERED")

    print(f"[sync_users] Синхронизировано {len(rows)} записей")

if __name__ == "__main__":
    sync_users()
