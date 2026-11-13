"""
Минимальная обертка для безопасности
"""
import sqlite3
import logging
from config.config import DB_NAME

def safe_execute(query: str, params: tuple = ()):
    """
    Безопасное выполнение запроса с параметрами
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
        return cursor
    except sqlite3.Error as e:
        logging.error(f"❌ Ошибка SQL: {e}\nЗапрос: {query}\nПараметры: {params}")
        conn.rollback()
        return None
    # НЕ закрываем соединение здесь!

def safe_fetch_one(query: str, params: tuple = ()):
    """Получить одну запись"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        return cursor.fetchone()
    except sqlite3.Error as e:
        logging.error(f"❌ Ошибка SQL: {e}\nЗапрос: {query}\nПараметры: {params}")
        return None
    finally:
        conn.close()  # Здесь можно закрыть