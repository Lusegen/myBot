import sqlite3
import logging
from config.config import SETTINGS_DB_NAME

# ✅ КОНСТАНТА ДЛЯ КЛЮЧА ПРИВЕТСТВИЯ
WELCOME_MESSAGE_KEY = "welcome_message"

# ✅ ДЕФОЛТНОЕ ПРИВЕТСТВИЕ
DEFAULT_WELCOME_MESSAGE = """Здравствуйте! Вы начали диалог с врачом.

Пожалуйста, введите ваш номер телефона для связи, и врач ответит вам в ближайшее время."""


def init_settings_database():
    """Инициализация БД для настроек"""
    conn = sqlite3.connect(SETTINGS_DB_NAME)
    cursor = conn.cursor()

    try:
        # Создаем таблицу настроек
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        logging.info(f"✅ БД настроек {SETTINGS_DB_NAME} инициализирована")

        # ✅ ПРОВЕРЯЕМ И СОЗДАЕМ ПРИВЕТСТВИЕ ПО УМОЛЧАНИЮ
        welcome = get_bot_setting(WELCOME_MESSAGE_KEY)
        if not welcome:
            set_bot_setting(WELCOME_MESSAGE_KEY, DEFAULT_WELCOME_MESSAGE, "Приветственное сообщение для консультаций")
            logging.info("✅ Создано приветственное сообщение по умолчанию")

    except Exception as e:
        logging.error(f"❌ Ошибка инициализации БД настроек: {e}")
    finally:
        conn.close()


def get_bot_setting(key: str, default: str = "") -> str:
    conn = sqlite3.connect(SETTINGS_DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT value FROM bot_settings 
            WHERE key = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        """, (key,))
        result = cursor.fetchone()
        return result[0] if result else default
    except Exception as e:
        logging.error(f"❌ Ошибка получения настройки {key}: {e}")
        return default
    finally:
        conn.close()


def set_bot_setting(key: str, value: str, description: str = None) -> bool:
    """Установить значение настройки в БД (с возможностью добавить описание)"""
    conn = sqlite3.connect(SETTINGS_DB_NAME)
    cursor = conn.cursor()

    try:
        if description:
            cursor.execute('''
                REPLACE INTO bot_settings (key, value, description, updated_at)
                VALUES (?, ?, ?, datetime('now'))
            ''', (key, value, description))
        else:
            cursor.execute('''
                REPLACE INTO bot_settings (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
            ''', (key, value))

        conn.commit()
        logging.info(f"✅ Настройка {key} обновлена")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения настройки {key}: {e}")
        return False
    finally:
        conn.close()


# ✅ НОВАЯ ФУНКЦИЯ: Получить приветственное сообщение
def get_welcome_message() -> str:
    """Получить приветственное сообщение для консультаций"""
    return get_bot_setting(WELCOME_MESSAGE_KEY, DEFAULT_WELCOME_MESSAGE)


# ✅ НОВАЯ ФУНКЦИЯ: Сохранить приветственное сообщение
def set_welcome_message(message: str) -> bool:
    """Сохранить приветственное сообщение для консультаций"""
    return set_bot_setting(WELCOME_MESSAGE_KEY, message, "Приветственное сообщение для консультаций")