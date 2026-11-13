import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from config.config import DB_NAME,  CONSULTATION_SESSION_DURATION


class ConsultationDB:
    def __init__(self):
        self.db_path = DB_NAME

    def _get_connection(self):
        """Получение соединения с базой данных"""
        return sqlite3.connect(self.db_path)

    def create_session(self, patient_id: int, session_type: str,
                       phone_number: str) -> Optional[int]:
        """Создание новой сессии консультации"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Получаем ID врача
            cursor.execute('SELECT telegram_id FROM users WHERE is_doctor = 1 LIMIT 1')
            doctor_result = cursor.fetchone()

            if not doctor_result:
                logging.error("❌ В системе не найден врач")
                return None

            doctor_id = doctor_result[0]

            cursor.execute('''
                INSERT INTO consultation_sessions 
                (patient_id, doctor_id, session_type, phone_number, status, payment_status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                patient_id, doctor_id, session_type, phone_number, 'pending', 'pending'
            ))

            session_id = cursor.lastrowid
            conn.commit()
            logging.info(f"✅ Создана новая сессия консультации ID: {session_id}")
            return session_id

        except Exception as e:
            logging.error(f"❌ Ошибка при создании сессии: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    def get_session(self, session_id: int) -> Optional[dict]:
        """Получение сессии по ID (безопасная версия)"""
        from database.safe_db import safe_fetch_one

        try:
            row = safe_fetch_one(
                'SELECT * FROM consultation_sessions WHERE id = ?',
                (session_id,)
            )

            if row:
                # Преобразуем в словарь (row уже может быть кортежем)
                columns = ['id', 'patient_id', 'doctor_id', 'session_type',
                           'phone_number', 'status', 'payment_status',
                           'created_at', 'activated_at', 'expires_at', 'completed_at']
                return dict(zip(columns, row)) if row else None
            return None

        except Exception as e:
            logging.error(f"❌ Ошибка при получении сессии: {e}")
            return None

    def get_session_by_payment_id(self, yookassa_payment_id: str) -> Optional[dict]:
        """Получение сессии по ID платежа ЮKassa"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM consultation_sessions WHERE yookassa_payment_id = ?',
                           (yookassa_payment_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logging.error(f"❌ Ошибка при получении сессии по payment_id: {e}")
            return None
        finally:
            conn.close()

    def update_session_status(self, session_id: int, status: str) -> bool:
        """Обновление статуса сессии (безопасная версия)"""
        from database.safe_db import safe_execute

        try:
            cursor = safe_execute(
                'UPDATE consultation_sessions SET status = ? WHERE id = ?',
                (status, session_id)
            )

            if cursor and cursor.rowcount > 0:
                logging.info(f"✅ Статус сессии {session_id} обновлен на: {status}")
                return True
            return False

        except Exception as e:
            logging.error(f"❌ Ошибка при обновлении статуса сессии: {e}")
            return False

    def update_payment_status(self, session_id: int, payment_status: str) -> bool:
        """Обновление статуса оплаты сессии"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'UPDATE consultation_sessions SET payment_status = ? WHERE id = ?',
                (payment_status, session_id)
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logging.info(f"✅ Статус оплаты сессии {session_id} обновлен на: {payment_status}")
            return success

        except Exception as e:
            logging.error(f"❌ Ошибка при обновлении статуса оплаты: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def activate_session(self, session_id: int) -> bool:
        """Активация сессии (после успешной оплаты)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            activated_at = datetime.now()
            expires_at = activated_at + timedelta(hours=CONSULTATION_SESSION_DURATION)

            cursor.execute('''
                UPDATE consultation_sessions 
                SET status = 'active', payment_status = 'paid', 
                    activated_at = ?, expires_at = ?
                WHERE id = ?
            ''', (activated_at, expires_at, session_id))

            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logging.info(f"✅ Сессия {session_id} активирована до {expires_at}")
            return success

        except Exception as e:
            logging.error(f"❌ Ошибка при активации сессии: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def complete_session(self, session_id: int) -> bool:
        """Завершение сессии"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            completed_at = datetime.now()

            cursor.execute('''
                UPDATE consultation_sessions 
                SET status = 'completed', completed_at = ?
                WHERE id = ?
            ''', (completed_at, session_id))

            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logging.info(f"✅ Сессия {session_id} завершена")
            return success

        except Exception as e:
            logging.error(f"❌ Ошибка при завершении сессии: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_active_sessions(self, patient_id: int = None) -> List[dict]:
        """Получение активных сессий пользователя (ТОЛЬКО НЕ ПРОСРОЧЕННЫЕ)"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            current_time = datetime.now()

            # ВАРИАНТ А: с разными параметрами
            if patient_id is not None:
                query = '''
                    SELECT * FROM consultation_sessions 
                    WHERE status = "active" 
                    AND (expires_at IS NULL OR expires_at > :current_time)
                    AND patient_id = :patient_id
                '''
                cursor.execute(query, {
                    'current_time': current_time,
                    'patient_id': patient_id
                })
            else:
                query = '''
                    SELECT * FROM consultation_sessions 
                    WHERE status = "active" 
                    AND (expires_at IS NULL OR expires_at > :current_time)
                '''
                cursor.execute(query, {'current_time': current_time})

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            logging.error(f"❌ Ошибка при получении активных сессий: {e}")
            return []
        finally:
            conn.close()

    def get_pending_sessions(self, patient_id: int = None) -> List[dict]:
        """Получение сессий ожидающих оплаты"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            query = '''SELECT * FROM consultation_sessions 
                      WHERE status = "pending" AND payment_status = "pending"'''
            params = []

            if patient_id:
                query += ' AND patient_id = ?'
                params.append(patient_id)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            logging.error(f"❌ Ошибка при получении pending сессий: {e}")
            return []
        finally:
            conn.close()

    def cleanup_stuck_pending_sessions(self, hours=24):
        """Очистка зависших pending-сессий (не оплаченных)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            cursor.execute('''
                DELETE FROM consultation_sessions 
                WHERE status = 'pending' 
                AND payment_status = 'pending'
                AND created_at < ?
            ''', (cutoff_time,))

            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logging.info(f"🧹 Удалено зависших pending сессий: {deleted_count}")

            return deleted_count
        except Exception as e:
            logging.error(f"❌ Ошибка при очистке pending сессий: {e}")
            return 0
        finally:
            conn.close()

    def set_yookassa_payment_id(self, session_id: int, yookassa_payment_id: str) -> bool:
        """Установка ID платежа ЮKassa для сессии"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'UPDATE consultation_sessions SET yookassa_payment_id = ? WHERE id = ?',
                (yookassa_payment_id, session_id)
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logging.info(f"✅ Для сессии {session_id} установлен payment_id: {yookassa_payment_id}")
            return success

        except Exception as e:
            logging.error(f"❌ Ошибка при установке payment_id: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def expire_old_sessions(self) -> int:
        """Автоматическое завершение просроченных сессий"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE consultation_sessions 
                SET status = 'expired' 
                WHERE status = 'active' AND expires_at < ?
            ''', (datetime.now(),))

            expired_count = cursor.rowcount
            conn.commit()

            if expired_count > 0:
                logging.info(f"🕒 Автоматически завершено просроченных сессий: {expired_count}")

            return expired_count

        except Exception as e:
            logging.error(f"❌ Ошибка при завершении просроченных сессий: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def get_user_sessions(self, user_id: int, limit: int = 10) -> List[dict]:
        """Получение истории сессий пользователя"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM consultation_sessions 
                WHERE patient_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            logging.error(f"❌ Ошибка при получении истории сессий: {e}")
            return []
        finally:
            conn.close()

    def get_doctor_id(self) -> Optional[int]:
        """Получение ID врача (он один в системе)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT telegram_id FROM users WHERE is_doctor = 1 LIMIT 1')
            result = cursor.fetchone()
            return result[0] if result else None

        except Exception as e:
            logging.error(f"❌ Ошибка при получении ID врача: {e}")
            return None
        finally:
            conn.close()

    def can_user_start_consultation(self, user_id: int) -> bool:
        """Проверка может ли пользователь начать новую консультацию"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Проверяем есть ли активные сессии у пользователя
            cursor.execute('''
                SELECT COUNT(*) FROM consultation_sessions 
                WHERE patient_id = ? AND status = 'active'
            ''', (user_id,))

            active_count = cursor.fetchone()[0]
            return active_count == 0  # Можно начать если нет активных сессий

        except Exception as e:
            logging.error(f"❌ Ошибка при проверке возможности консультации: {e}")
            return False
        finally:
            conn.close()

    def get_all_active_sessions(self) -> List[dict]:
        """Получение ВСЕХ активных сессий (для админ-панели)"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # ИСПРАВЛЯЕМ ЗАПРОС: добавляем проверку expires_at
            cursor.execute('''
                SELECT * FROM consultation_sessions 
                WHERE status = "active" 
                AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC
            ''', (datetime.now(),))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            logging.error(f"❌ Ошибка при получении всех активных сессий: {e}")
            return []
        finally:
            conn.close()

    def cleanup_old_sessions(self, hours=72):
        """Удаление сессий старше N часов"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            cursor.execute(
                'DELETE FROM consultation_sessions WHERE created_at < ?',
                (cutoff_time,)
            )

            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logging.info(f"🧹 Удалено устаревших сессий: {deleted_count}")

            return deleted_count

        except Exception as e:
            logging.error(f"❌ Ошибка при очистке сессий: {e}")
            return 0
        finally:
            conn.close()

# Создаем глобальный экземпляр для удобства использования
consultation_db = ConsultationDB()