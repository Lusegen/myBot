import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Токен бота (обязательно)
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# ID администратора (обязательно)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID не найден в .env файле!")

# Имена файлов БД
DB_NAME = os.getenv('DB_NAME', 'bot_schedule.db')
SETTINGS_DB_NAME = os.getenv('SETTINGS_DB_NAME', 'bot_database.db')

# Настройки слотов (теперь в БД, но можно оставить как запасной вариант)
TIME_SLOTS = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]

# Длительность консультации
CONSULTATION_SESSION_DURATION = int(os.getenv('CONSULTATION_SESSION_DURATION', '24'))