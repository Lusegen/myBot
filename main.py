import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher

from config.config import BOT_TOKEN
from database.db_init import init_database

from handlers.admin_core import register_admin_core_handlers
from handlers.admin_settings import register_admin_settings_handlers
from handlers.admins.chat_manager import register_chat_handlers
from handlers.start import register_start_handlers
from handlers.record import register_record_handlers
from handlers.consultation import register_consultation_handlers
from handlers.paid_consultation_handlers import register_paid_consultation_handlers
from database.scheduler import start_scheduler
from handlers.admin_slots_settings import register_admin_slots_handlers

# Настройка логирования
LOG_FILE = 'bot_debug.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)


def cleanup_old_logs(days_old: int = 14):
    """Очистка старых логов из файла"""
    try:
        if not os.path.exists(LOG_FILE):
            return

        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            return

        # Определяем дату границы (сегодня минус N дней)
        cutoff_date = datetime.now() - timedelta(days=days_old)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        # Оставляем только свежие логи
        fresh_lines = []
        for line in lines:
            # Пытаемся извлечь дату из начала строки "2025-12-29 20:54:05"
            if len(line) >= 19:
                log_date_str = line[:10]  # Берем "2025-12-29"
                if log_date_str >= cutoff_str:
                    fresh_lines.append(line)

        # Перезаписываем файл только свежими логами
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.writelines(fresh_lines)

        deleted_count = len(lines) - len(fresh_lines)
        if deleted_count > 0:
            logging.info(f"🧹 Удалено {deleted_count} строк логов старше {days_old} дней")

    except Exception as e:
        logging.error(f"❌ Ошибка очистки логов: {e}")


async def main():
    # ОЧИСТКА СТАРЫХ ЛОГОВ ПРИ ЗАПУСКЕ
    cleanup_old_logs(days_old=7)  # Удаляем логи старше 7 дней

    # Инициализируем базу данных
    logging.info("🗃️ Инициализация базы данных...")
    init_database()
    from database.blocked_dates import init_blocked_dates_table
    init_blocked_dates_table()


    # ✅ ИНИЦИАЛИЗИРУЕМ БД ДЛЯ НАСТРОЕК
    logging.info("⚙️ Инициализация БД настроек...")
    from database.settings_db import init_settings_database
    init_settings_database()

    # ✅ ИНИЦИАЛИЗИРУЕМ НАСТРОЙКИ СЛОТОВ (если их нет)
    from database.settings_db import get_bot_setting, set_bot_setting

    # Проверяем и устанавливаем настройки по умолчанию
    if not get_bot_setting('individual_slots_start'):
        set_bot_setting('individual_slots_start', '10:00')
        logging.info("✅ Установлено время начала слотов по умолчанию: 10:00")

    if not get_bot_setting('individual_slots_end'):
        set_bot_setting('individual_slots_end', '17:00')
        logging.info("✅ Установлено время окончания слотов по умолчанию: 17:00")

    # Запускаем планировщик
    logging.info("⏰ Запуск планировщика обновления базы...")
    start_scheduler()

    # Создаем бота и диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    from handlers.admins.chat_manager import check_inactive_doctors
    asyncio.create_task(check_inactive_doctors(bot))
    from handlers.admin_block_dates import register_admin_block_dates_handlers

    # Регистрируем обработчики - АДМИН ПЕРВЫМ!
    logging.info("1. Регистрируем админ-обработчики...")
    register_admin_core_handlers(dp)
    register_admin_slots_handlers(dp)

    register_admin_settings_handlers(dp)
    register_admin_block_dates_handlers(dp)
    register_chat_handlers(dp)

    logging.info("2. Регистрируем стартовые обработчики...")
    register_start_handlers(dp)

    logging.info("3. Регистрируем обработчики записи...")
    register_record_handlers(dp)

    logging.info("4. Регистрируем обработчики консультаций...")
    register_consultation_handlers(dp, bot)

    logging.info("5. Регистрируем обработчики платных консультаций...")
    register_paid_consultation_handlers(dp)



    # Запускаем бота
    logging.info("🚀 Бот запускается...")
    try:
        await dp.start_polling(bot)
    except Exception as error:
        logging.error(f"Ошибка при запуске бота: {error}")
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())