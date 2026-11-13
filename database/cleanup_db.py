"""
Модуль для очистки старых данных из базы данных
Только дополнительные функции очистки
"""
import sqlite3
import logging
from datetime import datetime, timedelta

from config.config import DB_NAME


class CleanupDB:
    def __init__(self):
        self.db_path = DB_NAME

    def _get_connection(self) -> sqlite3.Connection:
        """Получение соединения с базой данных"""
        return sqlite3.connect(self.db_path)

    def cleanup_old_chat_messages(self, days=3) -> int:
        """Очистка старых сообщений чатов (старше N дней)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            cursor.execute(
                'DELETE FROM chat_messages WHERE created_at < ?',
                (cutoff_time,)
            )

            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logging.info(f"🗑️ Удалено старых сообщений чатов: {deleted_count}")

            return deleted_count
        except Exception as e:
            logging.error(f"❌ Ошибка при очистке сообщений чатов: {e}")
            return 0
        finally:
            conn.close()

    def cleanup_old_home_visits(self, days=14) -> int:
        """Очистка старых записей на вызов врача (старше N дней)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            cursor.execute(
                'DELETE FROM home_visits WHERE created_at < ?',
                (cutoff_time,)
            )

            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logging.info(f"🏠 Удалено записей вызовов старше {days} дней: {deleted_count}")

            return deleted_count
        except Exception as e:
            logging.error(f"❌ Ошибка при очистке записей вызовов: {e}")
            return 0
        finally:
            conn.close()


# Создаем глобальный экземпляр для использования
cleanup_db = CleanupDB()