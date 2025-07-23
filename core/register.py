# core/register.py

import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
from core.sheets import add_user

DB = "court_tracking.db"

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # 1) Фаза запроса — без аргументов: просим ФИО и ставим флаг
    if not args and not context.user_data.get("awaiting_registration"):
        context.user_data["awaiting_registration"] = True
        await update.message.reply_text(
            "✏️ *Введите Фамилию и Имя*",
            parse_mode="Markdown"
        )
        return

    # 2) Фаза приёма ФИО: либо из args (командой), либо из свободного текста
    if context.user_data.get("awaiting_registration"):
        full_name = update.message.text.strip()
        context.user_data.pop("awaiting_registration", None)
    else:
        full_name = " ".join(args).strip()

    # Сохраняем в SQLite
    conn   = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            user_id   INTEGER PRIMARY KEY,
            full_name TEXT      NOT NULL
        )
    """)
    conn.commit()

    try:
        cursor.execute(
            "INSERT INTO employees (user_id, full_name) VALUES (?, ?)",
            (user_id, full_name)
        )
        conn.commit()

        # Добавляем в Google Sheets
        add_user(full_name, user_id)

        # Подтверждение
        await update.message.reply_text(
            f"✅ *Регистрация прошла успешно!*\nДобро пожаловать, *{full_name}*!",
            parse_mode="Markdown"
        )
    except sqlite3.IntegrityError:
        await update.message.reply_text(
            "⚠️ *Вы уже зарегистрированы.*",
            parse_mode="Markdown"
        )
    finally:
        conn.close()
