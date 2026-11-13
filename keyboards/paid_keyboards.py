from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_consultation_type_keyboard():
    """Клавиатура выбора типа консультации"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆕 Первичная консультация")],
            [KeyboardButton(text="🔄 Повторная консультация")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_phone_input_keyboard():
    """Клавиатура для ввода телефона"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard