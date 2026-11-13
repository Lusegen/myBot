# utils/date_utils.py
from datetime import datetime, timedelta
import locale
from database.blocked_dates import is_date_blocked


def get_weekdays(days_ahead=10):
    """Получить список будних дней на days_ahead дней вперед (исключая заблокированные)"""
    weekdays = []
    current_date = datetime.now()

    while len(weekdays) < days_ahead:
        current_date += timedelta(days=1)

        # Проверяем: будний день? (пн-пт)
        if current_date.weekday() < 5:
            date_str = format_date_russian(current_date)

            # Проверяем: не заблокирован ли этот день?
            if not is_date_blocked(date_str):
                weekdays.append(current_date)

    return weekdays


def format_date_russian(date):
    """Форматируем дату по-русски"""
    months = {
        1: 'янв', 2: 'фев', 3: 'мар', 4: 'апр', 5: 'май', 6: 'июн',
        7: 'июл', 8: 'авг', 9: 'сен', 10: 'окт', 11: 'ноя', 12: 'дек'
    }
    return f"{date.day} {months[date.month]}"


def setup_locale():
    """Настройка русской локали"""
    try:
        locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
    except (locale.Error, OSError):
        try:
            locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
        except (locale.Error, OSError):
            pass  # Если не получилось, оставляем системную локаль