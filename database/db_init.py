import sqlite3
import logging
from config.config import DB_NAME
from utils.date_utils import get_weekdays, format_date_russian
from utils.slot_generator import generate_time_slots


def init_database():
    """Инициализация и автоматическое обновление базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # ✅ ДОБАВЛЯЕМ таблицу пользователей ПЕРВОЙ
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                phone_number TEXT,
                is_doctor BOOLEAN DEFAULT 0,
                is_available_for_consultation BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logging.info("✅ Таблица users создана/проверена")

        # СУЩЕСТВУЮЩИЕ таблицы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'свободно',
                user_id INTEGER,
                user_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, time)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS home_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                username TEXT,
                phone TEXT NOT NULL,
                complaints TEXT NOT NULL,
                status TEXT DEFAULT 'новая',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ✅ НОВЫЕ таблицы для консультаций (упрощенные, без оплаты)
        _create_consultation_tables(cursor)
        _create_consultation_indexes(cursor)

        # ✅ ДОБАВЛЯЕМ ТАБЛИЦУ ДЛЯ СООБЩЕНИЙ ЧАТОВ
        _create_chat_messages_table(cursor)

        # ДОБАВЛЯЕМ таблицу для управления кнопками
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS button_settings (
                name TEXT PRIMARY KEY,
                enabled BOOLEAN DEFAULT TRUE
            )
        ''')

        # Инициализируем кнопки по умолчанию
        default_buttons = [
            ('call_doctor', 1),
            ('clinic_appointment', 1),
            ('individual_consultation', 1)
        ]

        cursor.executemany(
            "INSERT OR IGNORE INTO button_settings (name, enabled) VALUES (?, ?)",
            default_buttons
        )

        # Добавляем кнопку для консультаций
        cursor.execute(
            "INSERT OR IGNORE INTO button_settings (name, enabled) VALUES (?, ?)",
            ('paid_consultation', 1)  # Название можно потом сменить на 'consultation'
        )

        # ЗАМЕНЯЕМ create_initial_schedule на автоматическое обновление
        update_schedule_smart(cursor)

        conn.commit()
        logging.info("✅ База данных инициализирована и обновлена (включая консультации и чаты)")

    except Exception as e:
        logging.error(f"❌ Ошибка при инициализации БД: {e}")
        conn.rollback()
    finally:
        conn.close()


def _create_consultation_tables(cursor):
    """Создание таблиц для консультаций (без оплаты)"""

    # ✅ ПРИНУДИТЕЛЬНО УДАЛЯЕМ СТАРУЮ ТАБЛИЦУ (только для разработки!)
    # cursor.execute('DROP TABLE IF EXISTS consultation_sessions')
    # logging.info("🗑️ Старая таблица consultation_sessions удалена")

    # Таблица сессий консультаций - упрощенная версия
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consultation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            session_type TEXT NOT NULL CHECK(session_type IN ('primary', 'followup')),
            phone_number TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'completed', 'expired', 'cancelled')),
            payment_status TEXT NOT NULL DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            activated_at DATETIME NULL,
            expires_at DATETIME NULL,
            completed_at DATETIME NULL,

            FOREIGN KEY (patient_id) REFERENCES users (telegram_id),
            FOREIGN KEY (doctor_id) REFERENCES users (telegram_id)
        )
    ''')
    logging.info("✅ Таблица consultation_sessions создана/проверена (упрощенная версия)")

    # Добавляем поле доступности для консультаций в таблицу пользователей
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_available_for_consultation BOOLEAN DEFAULT 1')
        logging.info("✅ Добавлено поле is_available_for_consultation в таблицу users")
    except sqlite3.OperationalError:
        pass  # Поле уже существует


def _create_consultation_indexes(cursor):
    """Создание индексов для таблиц консультаций"""
    consultation_indexes = [
        'CREATE INDEX IF NOT EXISTS idx_consultation_sessions_patient_id ON consultation_sessions(patient_id)',
        'CREATE INDEX IF NOT EXISTS idx_consultation_sessions_doctor_id ON consultation_sessions(doctor_id)',
        'CREATE INDEX IF NOT EXISTS idx_consultation_sessions_status ON consultation_sessions(status)',
        'CREATE INDEX IF NOT EXISTS idx_consultation_sessions_payment_status ON consultation_sessions(payment_status)',
        'CREATE INDEX IF NOT EXISTS idx_consultation_sessions_expires_at ON consultation_sessions(expires_at)',
    ]

    for index_sql in consultation_indexes:
        cursor.execute(index_sql)
    logging.info("✅ Индексы для консультаций созданы/проверены")


def _create_chat_messages_table(cursor):
    """Создание таблицы для хранения сообщений чатов"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL CHECK(sender_type IN ('patient', 'doctor')),
            message_text TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (session_id) REFERENCES consultation_sessions (id)
        )
    ''')
    logging.info("✅ Таблица chat_messages создана/проверена")

    # Создаем индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_type ON chat_messages(sender_type)')
    logging.info("✅ Индексы для таблицы chat_messages созданы")


def update_schedule_smart(cursor, days_ahead=30):
    """
    Умное обновление расписания:
    - Удаляет устаревшие СВОБОДНЫЕ слоты (подтверждённые записи сохраняются)
    - Добавляет новые даты на 30 дней вперед
    - Использует динамические слоты из настроек
    - Удаляет свободные слоты вне нового диапазона
    - Пропускает заблокированные даты
    """
    try:
        from database.blocked_dates import is_date_blocked

        # 1. Получаем все будущие даты которые должны быть в расписании
        future_dates = get_weekdays(days_ahead)
        future_date_strings = [format_date_russian(date) for date in future_dates]

        # 2. Удаляем устаревшие СВОБОДНЫЕ слоты (подтверждённые записи не трогаем)
        if future_date_strings:
            placeholders = ','.join(['?'] * len(future_date_strings))
            cursor.execute(
                f"DELETE FROM schedule WHERE date NOT IN ({placeholders}) AND status = 'свободно'",
                future_date_strings
            )
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logging.info(f"🗑️ Удалено устаревших свободных слотов: {deleted_count}")

        # 3. Получаем настройки слотов из БД настроек
        try:
            from database.settings_db import get_bot_setting
            start_time = get_bot_setting('individual_slots_start', '10:00')
            end_time = get_bot_setting('individual_slots_end', '17:00')
            time_slots = generate_time_slots(start_time, end_time, 60)
            logging.info(f"⏰ Используем слоты из настроек: {start_time} - {end_time}")
        except Exception as e:
            logging.warning(f"⚠️ Не удалось получить настройки слотов, используем по умолчанию: {e}")
            time_slots = generate_time_slots("10:00", "17:00", 60)

        # 4. Удаляем свободные слоты вне нового диапазона
        deleted_free_count = 0
        if time_slots:
            for date in future_dates:
                date_str = format_date_russian(date)
                placeholders = ','.join(['?'] * len(time_slots))

                cursor.execute(f"""
                    DELETE FROM schedule 
                    WHERE date = ? 
                    AND time NOT IN ({placeholders})
                    AND status = 'свободно'
                """, [date_str] + time_slots)

                deleted_free_count += cursor.rowcount

        if deleted_free_count > 0:
            logging.info(f"🗑️ Удалено свободных слотов вне диапазона: {deleted_free_count}")

        # 5. Добавляем недостающие даты (только для НЕзаблокированных дней)
        added_count = 0
        skipped_blocked = 0

        for date in future_dates:
            date_str = format_date_russian(date)

            # ПРОВЕРЯЕМ, НЕ ЗАБЛОКИРОВАН ЛИ ДЕНЬ
            if is_date_blocked(date_str):
                # Удаляем свободные слоты на этот день (подтверждённые записи сохраняем)
                cursor.execute(
                    "DELETE FROM schedule WHERE date = ? AND status = 'свободно'",
                    (date_str,)
                )
                deleted_for_blocked = cursor.rowcount
                if deleted_for_blocked > 0:
                    logging.info(f"🚫 Удалено свободных слотов на заблокированную дату {date_str}: {deleted_for_blocked}")
                skipped_blocked += 1
                continue

            for slot_time in time_slots:
                cursor.execute(
                    "SELECT 1 FROM schedule WHERE date = ? AND time = ?",
                    (date_str, slot_time)
                )

                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO schedule (date, time, status) VALUES (?, ?, ?)",
                        (date_str, slot_time, "свободно")
                    )
                    added_count += 1

        if added_count > 0:
            logging.info(f"📅 Добавлено новых слотов: {added_count}")
        if skipped_blocked > 0:
            logging.info(f"🚫 Пропущено заблокированных дней: {skipped_blocked}")

        logging.info(f"✅ Расписание обновлено на {days_ahead} дней вперед")

    except Exception as e:
        logging.error(f"❌ Ошибка при обновлении расписания: {e}")
        raise


def update_database():
    """Функция для автоматического обновления (для планировщика)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        update_schedule_smart(cursor, days_ahead=30)
        conn.commit()
        conn.close()
        logging.info("🔄 Расписание автоматически обновлено")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка при автоматическом обновлении: {e}")
        return False


async def get_button_status(button_name: str) -> bool:
    """Получить статус кнопки из БД"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT enabled FROM button_settings WHERE name = ?", (button_name,))
    result = cursor.fetchone()

    conn.close()

    # Возвращаем True если кнопка включена, False если выключена
    return bool(result[0]) if result else True  # По умолчанию включено


async def set_button_status(button_name: str, enabled: bool):
    """Установить статус кнопки в БД"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR REPLACE INTO button_settings (name, enabled) VALUES (?, ?)",
        (button_name, 1 if enabled else 0)  # Конвертируем bool в int для SQLite
    )

    conn.commit()
    conn.close()