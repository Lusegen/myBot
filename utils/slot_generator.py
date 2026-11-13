# utils/slot_generator.py
import logging
from datetime import datetime, timedelta


def validate_time_format(time_str: str) -> bool:
    """Проверка формата времени ЧЧ:ММ"""
    try:
        datetime.strptime(time_str, '%H:%M')
        return True
    except ValueError:
        return False


def parse_time(time_str: str) -> tuple:
    """Парсинг времени в часы и минуты"""
    time_obj = datetime.strptime(time_str, '%H:%M')
    return time_obj.hour, time_obj.minute


def generate_time_slots(start_time: str, end_time: str, interval_minutes: int = 60) -> list:
    """
    Генерация временных слотов от start_time до end_time с заданным интервалом

    Args:
        start_time: время начала в формате "ЧЧ:ММ"
        end_time: время окончания в формате "ЧЧ:ММ"
        interval_minutes: интервал в минутах (по умолчанию 60)

    Returns:
        Список строк со временем в формате "ЧЧ:ММ"
    """
    if not validate_time_format(start_time):
        raise ValueError(f"Неверный формат начала времени: {start_time}. Ожидается ЧЧ:ММ")

    if not validate_time_format(end_time):
        raise ValueError(f"Неверный формат окончания времени: {end_time}. Ожидается ЧЧ:ММ")

    start_hour, start_minute = parse_time(start_time)
    end_hour, end_minute = parse_time(end_time)

    # Преобразуем в datetime для удобства вычислений
    start_dt = datetime(2024, 1, 1, start_hour, start_minute)
    end_dt = datetime(2024, 1, 1, end_hour, end_minute)

    if start_dt >= end_dt:
        raise ValueError("Время начала должно быть раньше времени окончания")

    time_slots = []  # Изменили имя переменной
    current_dt = start_dt

    while current_dt < end_dt:
        time_slots.append(current_dt.strftime('%H:%M'))
        current_dt += timedelta(minutes=interval_minutes)

    logging.info(
        f"✅ Сгенерировано {len(time_slots)} слотов: {start_time} - {end_time} (интервал {interval_minutes} мин)")
    return time_slots


# Пример использования для тестирования
if __name__ == "__main__":
    # Тест 1: нормальная работа
    test_slots = generate_time_slots("08:00", "20:00")  # Изменили имя переменной
    print(f"Слоты 08:00-20:00: {test_slots}")

    # Тест 2: ошибка формата
    try:
        generate_time_slots("25:00", "20:00")
    except ValueError as e:
        print(f"Ошибка: {e}")

    # Тест 3: начало позже окончания
    try:
        generate_time_slots("18:00", "08:00")
    except ValueError as e:
        print(f"Ошибка: {e}")