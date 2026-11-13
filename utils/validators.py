# utils/validators.py

def validate_phone_number(phone):
    """Проверка номера телефона (11 цифр)"""
    return phone.isdigit() and len(phone) == 11


def validate_time_slot(time_slot):
    """Проверка корректности временного слота"""
    from config.config import TIME_SLOTS
    return time_slot in TIME_SLOTS