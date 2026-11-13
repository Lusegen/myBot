import sqlite3
import logging
from config.config import DB_NAME


def init_blocked_dates_table():
    """Создание таблицы заблокированных дат"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                blocked_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logging.info("✅ Таблица blocked_dates создана/проверена")
    except Exception as e:
        logging.error(f"❌ Ошибка создания таблицы blocked_dates: {e}")
    finally:
        conn.close()


def block_date(date_str: str, admin_id: int = None) -> bool:
    """Заблокировать дату"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT OR IGNORE INTO blocked_dates (date, blocked_by) VALUES (?, ?)",
            (date_str, admin_id)
        )
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logging.info(f"🚫 Дата заблокирована: {date_str}")
        return success
    except Exception as e:
        logging.error(f"❌ Ошибка блокировки даты {date_str}: {e}")
        return False
    finally:
        conn.close()


def unblock_date(date_str: str) -> bool:
    """Разблокировать дату"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM blocked_dates WHERE date = ?",
            (date_str,)
        )
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logging.info(f"✅ Дата разблокирована: {date_str}")
        return success
    except Exception as e:
        logging.error(f"❌ Ошибка разблокировки даты {date_str}: {e}")
        return False
    finally:
        conn.close()


def is_date_blocked(date_str: str) -> bool:
    """Проверить, заблокирована ли дата"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT 1 FROM blocked_dates WHERE date = ?",
            (date_str,)
        )
        return cursor.fetchone() is not None
    except Exception as e:
        logging.error(f"❌ Ошибка проверки даты {date_str}: {e}")
        return False
    finally:
        conn.close()


def get_blocked_dates() -> list:
    """Получить список всех заблокированных дат"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT date, blocked_by, created_at FROM blocked_dates ORDER BY date"
        )
        return cursor.fetchall()
    except Exception as e:
        logging.error(f"❌ Ошибка получения заблокированных дат: {e}")
        return []
    finally:
        conn.close()


def clear_all_blocked_dates() -> int:
    """Очистить все блокировки (для админа)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM blocked_dates")
        deleted = cursor.rowcount
        conn.commit()
        logging.info(f"🧹 Удалено блокировок: {deleted}")
        return deleted
    except Exception as e:
        logging.error(f"❌ Ошибка очистки блокировок: {e}")
        return 0
    finally:
        conn.close()