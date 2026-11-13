import sqlite3
import logging
from config.config import DB_NAME
from datetime import datetime
from utils.slot_generator import generate_time_slots
from database.settings_db import get_bot_setting


def create_home_visit_request(user_id: int, user_name: str, username: str, phone: str, complaints: str) -> bool:
    """Создать заявку на вызов врача на дом (безопасная версия)"""
    from database.safe_db import safe_execute

    try:
        # ВАЖНО: очищаем complaints от потенциально опасных символов
        import re
        clean_complaints = re.sub(r'[;\'"\-]', '', complaints)

        cursor = safe_execute('''
            INSERT INTO home_visits (user_id, user_name, username, phone, complaints)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, user_name, username, phone, clean_complaints))

        return cursor is not None

    except Exception as e:
        logging.error(f"❌ Ошибка создания заявки на вызов: {e}")
        return False


def get_pending_home_visits():
    """Получить все новые заявки на вызовы"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_name, username, phone, complaints, created_at 
        FROM home_visits 
        WHERE status = 'новая'
        ORDER BY created_at
    ''')

    visits = cursor.fetchall()
    conn.close()
    return visits


def delete_old_visits(days_old: int = 7):
    """Удалить старые заявки (старше 7 дней)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM home_visits WHERE created_at < datetime('now', ?)",
        (f'-{days_old} days',)
    )

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count


def get_available_slots(date):
    """Получить доступные слоты для даты"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Получаем занятые слоты из БД
    cursor.execute(
        "SELECT time, status FROM schedule WHERE date = ? ORDER BY time",
        (date,)
    )
    db_slots = cursor.fetchall()
    conn.close()

    # Преобразуем в словарь для быстрого поиска
    db_slots_dict = {row[0]: row[1] for row in db_slots}

    # 2. Получаем настройки и генерируем все возможные слоты
    try:
        start_time = get_bot_setting('individual_slots_start', '10:00')
        end_time = get_bot_setting('individual_slots_end', '17:00')

        all_possible_slots = generate_time_slots(start_time, end_time, 60)
    except Exception as e:
        logging.error(f"❌ Ошибка генерации слотов: {e}")
        # Возвращаем то, что есть в БД
        return db_slots_dict

    # 3. Создаем полный список слотов с правильными статусами
    all_slots = {}
    for slot_time in all_possible_slots:
        if slot_time in db_slots_dict:
            # Слот есть в БД - берем его статус
            all_slots[slot_time] = db_slots_dict[slot_time]
        else:
            # Слота нет в БД - значит он свободен (еще не добавлен в расписание)
            all_slots[slot_time] = "свободно"

    return all_slots


def book_slot(user_id, user_name, date, slot_time):
    """Забронировать слот (безопасная версия)"""
    from database.safe_db import safe_execute

    try:
        cursor = safe_execute(
            '''UPDATE schedule 
               SET status = 'занято', user_id = ?, user_name = ?
               WHERE date = ? AND time = ? AND status = 'свободно'
            ''',
            (user_id, user_name, date, slot_time)
        )

        if cursor:
            return cursor.rowcount > 0
        return False

    except Exception as e:
        logging.error(f"❌ Ошибка бронирования: {e}")
        return False

def get_user_appointments(user_id):
    """Получить записи пользователя с правильной сортировкой"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT date, time FROM schedule WHERE user_id = ?",
        (user_id,)
    )
    appointments = cursor.fetchall()
    conn.close()

    # Сортировка для формата "15 янв", "16 янв"
    months = {
        'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
        'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
    }

    # ТЕКУЩАЯ ДАТА
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day

    def parse_appointment_date(date_str):
        """Парсим дату типа '9 дек' и определяем год"""
        day_str, month_name = date_str.split()
        day = int(day_str)
        month_num = months.get(month_name, 0)

        # ОПРЕДЕЛЯЕМ ГОД:
        # 1. Если месяц декабрь (12), а сейчас январь (1) - это ПРОШЛЫЙ год
        if month_name == 'дек' and current_month == 1:
            year = current_year - 1
        # 2. Если месяц меньше текущего (кроме декабрь→январь) - это ПРОШЛЫЙ год
        elif month_num < current_month and not (month_name == 'дек' and current_month == 1):
            year = current_year - 1
        else:
            year = current_year

        return year, month_num, day

    def is_future_appointment_func(appointment):
        """Определить, является ли запись будущей с учетом года"""
        date_str, time_str = appointment

        try:
            year, month_num, day = parse_appointment_date(date_str)

            # Сравниваем с текущей датой
            if year < current_year:
                return False  # Прошлый год
            elif year > current_year:
                return True  # Будущий год
            else:
                # Тот же год
                if month_num < current_month:
                    return False  # Прошлый месяц
                elif month_num > current_month:
                    return True  # Будущий месяц
                else:
                    # Тот же месяц
                    return day >= current_day  # Сегодня или позже

        except Exception:
            return False  # Если ошибка - считаем прошедшей

    def sort_key(appointment):
        date_str, time_str = appointment
        year, month_num, day = parse_appointment_date(date_str)
        return year, month_num, day, time_str

    # Фильтруем ТОЛЬКО будущие записи
    future_appointments = [app for app in appointments if is_future_appointment_func(app)]

    # Сортируем
    future_appointments.sort(key=sort_key)

    return future_appointments


def get_user_name(user_id: int) -> str:
    """Получить имя пользователя по ID"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT full_name FROM users WHERE telegram_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else ""
    except sqlite3.Error as e:
        logging.error(f"Ошибка получения имени пользователя {user_id}: {e}")
        return ""
    finally:
        conn.close()


def save_user_on_start(telegram_id: int, full_name: str = "") -> bool:
    """Сохранить пользователя при старте (безопасная версия)"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Проверяем существование
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        exists = cursor.fetchone()

        if exists:
            if full_name:
                cursor.execute('''
                    UPDATE users 
                    SET full_name = ?
                    WHERE telegram_id = ?
                ''', (full_name, telegram_id))
                logging.info(f"🔄 Имя обновлено: {telegram_id} -> '{full_name}'")
        else:
            cursor.execute('''
                INSERT INTO users 
                (telegram_id, full_name, is_doctor, is_available_for_consultation, created_at)
                VALUES (?, ?, 0, 1, datetime('now'))
            ''', (telegram_id, full_name))
            logging.info(f"🆕 Пользователь создан: {telegram_id}")

        conn.commit()
        return True

    except sqlite3.Error as e:
        logging.error(f"❌ Ошибка сохранения пользователя {telegram_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_all_appointments():
    """Получить все записи с правильной сортировкой"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT date, time, user_name FROM schedule WHERE status = 'занято'"
    )
    appointments = cursor.fetchall()
    conn.close()

    print(f"📋 Все записи из БД для админа: {appointments}")

    # Та же сортировка для всех записей
    months = {
        'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
        'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
    }

    # ТЕКУЩАЯ ДАТА
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day

    def parse_appointment_date(date_str):
        """Парсим дату типа '9 дек' и определяем год"""
        day_str, month_name = date_str.split()
        day = int(day_str)
        month_num = months.get(month_name, 0)

        # ОПРЕДЕЛЯЕМ ГОД:
        # 1. Если месяц декабрь (12), а сейчас январь (1) - это ПРОШЛЫЙ год
        if month_name == 'дек' and current_month == 1:
            year = current_year - 1
        # 2. Если месяц меньше текущего (кроме декабрь→январь) - это ПРОШЛЫЙ год
        elif month_num < current_month and not (month_name == 'дек' and current_month == 1):
            year = current_year - 1
        else:
            year = current_year

        return year, month_num, day

    def is_future_appointment_func(appointment):
        """Определить, является ли запись будущей с учетом года"""
        date_str, time_str, user_name = appointment

        try:
            year, month_num, day = parse_appointment_date(date_str)

            # Сравниваем с текущей датой
            if year < current_year:
                print(f"❌ {date_str} - прошлый год ({year} < {current_year})")
                return False  # Прошлый год
            elif year > current_year:
                print(f"✅ {date_str} - будущий год ({year} > {current_year})")
                return True  # Будущий год
            else:
                # Тот же год
                if month_num < current_month:
                    print(f"❌ {date_str} - прошлый месяц ({month_num} < {current_month})")
                    return False  # Прошлый месяц
                elif month_num > current_month:
                    print(f"✅ {date_str} - будущий месяц ({month_num} > {current_month})")
                    return True  # Будущий месяц
                else:
                    # Тот же месяц
                    is_future = day >= current_day
                    print(f"📅 {date_str} - тот же месяц: день {day} >= {current_day}? {is_future}")
                    return is_future

        except Exception as e:
            print(f"❌ Ошибка при обработке {appointment}: {e}")
            return False

    def sort_key(appointment):
        date_str, time_str, user_name = appointment
        year, month_num, day = parse_appointment_date(date_str)
        return year, month_num, day, time_str

    # Фильтруем ТОЛЬКО будущие записи
    future_appointments = [app for app in appointments if is_future_appointment_func(app)]

    # Сортируем
    future_appointments.sort(key=sort_key)

    print(f"🎯 Итоговые будущие записи для админа: {future_appointments}")
    return future_appointments