import sqlite3
import logging
from datetime import datetime
from typing import List, Optional
from config.config import DB_NAME


class ChatMessagesDB:
    def __init__(self):
        self.db_path = DB_NAME

    def _get_connection(self):
        """Получение соединения с базой данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для возврата словарей
        return conn

    def save_message(self, session_id: int, sender_id: int,
                     sender_type: str, message_text: str) -> Optional[int]:
        """Сохранение сообщения в БД"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO chat_messages 
                (session_id, sender_id, sender_type, message_text)
                VALUES (?, ?, ?, ?)
            ''', (session_id, sender_id, sender_type, message_text))

            message_id = cursor.lastrowid
            conn.commit()

            logging.info(f"💾 Сообщение сохранено: сессия {session_id}, отправитель {sender_id} ({sender_type})")
            return message_id

        except Exception as e:
            logging.error(f"❌ Ошибка при сохранении сообщения: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_session_messages(self, session_id: int, limit: int = 50) -> List[dict]:
        """Получение сообщений сессии (от старых к новым)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT 
                    id, session_id, sender_id, sender_type, 
                    message_text, created_at,
                    CASE 
                        WHEN sender_type = 'doctor' THEN '👨‍⚕️ Врач'
                        WHEN sender_type = 'patient' THEN '👤 Пациент'
                        ELSE sender_type
                    END as sender_display
                FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY created_at ASC 
                LIMIT ?
            ''', (session_id, limit))

            rows = cursor.fetchall()
            messages = []

            for row in rows:
                message = {
                    'id': row[0],
                    'session_id': row[1],
                    'sender_id': row[2],
                    'sender_type': row[3],
                    'message_text': row[4],
                    'created_at': row[5],
                    'sender_display': row[6]
                }

                # Форматируем дату для удобного отображения
                if message['created_at']:
                    try:
                        dt = datetime.fromisoformat(message['created_at'].replace('Z', '+00:00'))
                        message['created_at_formatted'] = dt.strftime("%H:%M %d.%m.%Y")
                    except:
                        message['created_at_formatted'] = message['created_at']

                messages.append(message)

            return messages

        except Exception as e:
            logging.error(f"❌ Ошибка при получении сообщений: {e}")
            return []
        finally:
            conn.close()

    def get_last_message(self, session_id: int) -> Optional[dict]:
        """Получение последнего сообщения в сессии"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT 
                    id, session_id, sender_id, sender_type, 
                    message_text, created_at
                FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (session_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'session_id': row[1],
                    'sender_id': row[2],
                    'sender_type': row[3],
                    'message_text': row[4],
                    'created_at': row[5]
                }
            return None

        except Exception as e:
            logging.error(f"❌ Ошибка при получении последнего сообщения: {e}")
            return None
        finally:
            conn.close()

    def get_message_count(self, session_id: int) -> int:
        """Получение количества сообщений в сессии"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT COUNT(*) FROM chat_messages 
                WHERE session_id = ?
            ''', (session_id,))

            count = cursor.fetchone()[0]
            return count

        except Exception as e:
            logging.error(f"❌ Ошибка при подсчете сообщений: {e}")
            return 0
        finally:
            conn.close()

    def delete_session_messages(self, session_id: int) -> int:
        """Удаление всех сообщений сессии"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM chat_messages WHERE session_id = ?', (session_id,))
            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logging.info(f"🗑️ Удалено сообщений сессии {session_id}: {deleted_count}")

            return deleted_count

        except Exception as e:
            logging.error(f"❌ Ошибка при удалении сообщений: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def get_recent_messages(self, hours: int = 24) -> List[dict]:
        """Получение последних сообщений за период"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cutoff_time = datetime.now().replace(hour=datetime.now().hour - hours)

            cursor.execute('''
                SELECT 
                    cm.id, cm.session_id, cm.sender_id, cm.sender_type, 
                    cm.message_text, cm.created_at,
                    cs.patient_id, cs.doctor_id, cs.status as session_status
                FROM chat_messages cm
                JOIN consultation_sessions cs ON cm.session_id = cs.id
                WHERE cm.created_at >= ?
                ORDER BY cm.created_at DESC
                LIMIT 100
            ''', (cutoff_time,))

            rows = cursor.fetchall()
            messages = []

            for row in rows:
                message = {
                    'id': row[0],
                    'session_id': row[1],
                    'sender_id': row[2],
                    'sender_type': row[3],
                    'message_text': row[4],
                    'created_at': row[5],
                    'patient_id': row[6],
                    'doctor_id': row[7],
                    'session_status': row[8]
                }
                messages.append(message)

            return messages

        except Exception as e:
            logging.error(f"❌ Ошибка при получении последних сообщений: {e}")
            return []
        finally:
            conn.close()


# Глобальный экземпляр для удобства использования
chat_messages_db = ChatMessagesDB()