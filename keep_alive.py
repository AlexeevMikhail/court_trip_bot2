from flask import Flask, request
from threading import Thread
from datetime import datetime
import logging

# Отключаем лишние логи Flask
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)

@app.route('/', methods=["GET", "HEAD"])
def home():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if request.method == "HEAD":
        print(f"🔄 HEAD-запрос от UptimeRobot в {now}")
    else:
        print(f"✅ GET-запрос на / — бот активен в {now}")
    return "Бот активен", 200

# Дополнительный пинг-эндпоинт (по желанию)
@app.route('/ping', methods=["GET"])
def ping():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"✅ Получен GET-запрос на /ping в {now}")
    return "Pong", 200

# Дополнительная проверка (по желанию)
@app.route('/health', methods=["GET"])
def health():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"🟢 Получен GET-запрос на /health в {now}")
    return "Bot is alive", 200

def run():
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=False,
        use_reloader=False,
        threaded=True
    )

def keep_alive():
    Thread(target=run, daemon=True, name="FlaskThread").start()
    print("🛠️ Сервер keep_alive запущен на порту 8080")

