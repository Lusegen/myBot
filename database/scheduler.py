import time
import logging
from threading import Thread
from datetime import datetime, timedelta
from database.db_init import update_database
from database.consultation_db import consultation_db
from database.cleanup_db import cleanup_db


def simple_scheduler():
    """Упрощенный планировщик без внешних зависимостей"""
    logging.info("⏰ Упрощенный планировщик запущен")

    last_update_day = None  # Для обновления в 03:00
    last_cleanup_day = None  # Для очистки в 04:00

    # Время последнего выполнения каждой задачи
    last_executed = {
        'expired_sessions': datetime.now() - timedelta(days=1),
    }

    # Интервалы в секундах
    check_intervals = {
        'expired_sessions': 21600,  # 6 часов
    }

    while True:
        try:
            now = datetime.now()
            current_day = now.day

            # ✅ Задача 1: Проверка просроченных сессий каждые 5 минут
            time_since_last_check = (now - last_executed['expired_sessions']).total_seconds()
            if time_since_last_check >= check_intervals['expired_sessions']:
                logging.info("🕒 Проверка просроченных сессий...")
                expired_count = consultation_db.expire_old_sessions()
                if expired_count > 0:
                    logging.info(f"✅ Завершено просроченных сессий: {expired_count}")
                last_executed['expired_sessions'] = now

            # ✅ Задача 2: ЕЖЕДНЕВНАЯ ОЧИСТКА ВСЕХ ДАННЫХ (в 04:00)
            if (now.hour == 4 and now.minute == 0 and
                    last_cleanup_day != current_day):

                logging.info("🌙 Ночная очистка данных...")

                # 1. Сессии старше 3 дней (из consultation_db)
                deleted_sessions = consultation_db.cleanup_old_sessions(hours=72)

                # 2. Сообщения чатов старше 3 дней (из cleanup_db)
                deleted_messages = cleanup_db.cleanup_old_chat_messages(days=3)

                # 3. Записи вызовов старше 14 дней (из cleanup_db)
                deleted_visits = cleanup_db.cleanup_old_home_visits(days=7)

                # Логируем итоги
                total_deleted = deleted_sessions + deleted_messages + deleted_visits
                if total_deleted > 0:
                    logging.info(f"🧹 Итоги: сессии={deleted_sessions}, "
                                 f"сообщения={deleted_messages}, вызовы={deleted_visits}")
                else:
                    logging.info("✅ Нет данных для очистки")

                last_cleanup_day = current_day

            # ✅ Задача 3: Ежедневное обновление базы (в 03:00)
            if (now.hour == 3 and now.minute == 0 and
                    last_update_day != current_day):
                logging.info("🔄 Запуск ежедневного обновления базы...")
                update_database()
                last_update_day = current_day
                logging.info("✅ Обновление завершено. Следующее - завтра в 03:00")

            # Ждем 1 минуту перед следующей проверкой
            time.sleep(60)

        except Exception as e:
            logging.error(f"❌ Ошибка в планировщике: {e}")
            time.sleep(60)

def start_scheduler():
    """Запуск упрощенного планировщика"""
    scheduler_thread = Thread(target=simple_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    logging.info("🚀 Упрощенный планировщик запущен в отдельном потоке")