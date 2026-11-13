from aiogram import types
from config.config import ADMIN_ID
from database.db_init import get_button_status


async def get_start_keyboard(user_id: int = None):
    """Стартовая клавиатура с учетом прав пользователя"""
    keyboard = [
        [types.KeyboardButton(text="📅 Записаться")],
        [types.KeyboardButton(text="📋 Мои записи")]
    ]

    # ✅ ПРОВЕРЯЕМ СТАТУС ПЛАТНЫХ КОНСУЛЬТАЦИЙ
    if await get_button_status("paid_consultation"):
        keyboard[0].append(types.KeyboardButton(text="💬 Сообщение"))  # Добавляем только если включено

    # Если пользователь админ - добавляем админские кнопки
    if user_id and str(user_id) == str(ADMIN_ID):
        # ✅ ИЗМЕНЕНИЕ: Админ получает новое главное меню
        return await get_admin_main_keyboard()

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


# ✅ НОВАЯ ФУНКЦИЯ: Главное меню администратора
async def get_admin_main_keyboard():
    """Главное меню администратора"""
    keyboard = [
        [types.KeyboardButton(text="👥 Все записи"), types.KeyboardButton(text="🏠 Заявки на вызов")],
        [types.KeyboardButton(text="💬 Активные чаты")],
        [types.KeyboardButton(text="👤 Пользовательская панель")],
        [types.KeyboardButton(text="⚙️ Настройки бота")]
    ]

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел админ-панели..."
    )


# ✅ НОВАЯ ФУНКЦИЯ: Пользовательская панель для администратора
async def get_admin_user_panel_keyboard():
    """Пользовательская панель (для администратора)"""
    keyboard = [
        [types.KeyboardButton(text="📅 Записаться")],
        [types.KeyboardButton(text="📋 Мои записи")]
    ]

    # Проверяем статус платных консультаций
    if await get_button_status("paid_consultation"):
        keyboard[0].append(types.KeyboardButton(text="💬 Сообщение"))

    keyboard.append([types.KeyboardButton(text="⬅️ Назад в админ-панель")])

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Пользовательские функции..."
    )


async def get_bot_settings_keyboard():
    """Меню настроек бота (главное)"""
    keyboard = [
        [types.KeyboardButton(text="⚙️ Управление функциями")],
        [types.KeyboardButton(text="✏️ Редактирование сообщений")],
        [types.KeyboardButton(text="⬅️ Назад в админ-панель")]
    ]

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Настройки бота..."
    )


async def get_manage_functions_keyboard():
    """Меню управления функциями"""
    keyboard = [
        [types.KeyboardButton(text="🎛️ Управление кнопками")],
        [types.KeyboardButton(text="⏰ Настройка временных слотов")],
        [types.KeyboardButton(text="🚫 Блокировка дней")],  # НОВАЯ КНОПКА
        [types.KeyboardButton(text="⬅️ Назад в настройки")]
    ]

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Управление функциями..."
    )


async def get_slots_settings_keyboard(start_time: str, end_time: str):
    keyboard = [
        [types.KeyboardButton(text=f"🕐 Начало: {start_time}")],
        [types.KeyboardButton(text=f"🕔 Окончание: {end_time}")],
        [types.KeyboardButton(text="⬇️"), types.KeyboardButton(text="⬆️")],  # ОДНА пара для выбранного
        [types.KeyboardButton(text="💾 Сохранить настройки")],
        [types.KeyboardButton(text="⬅️ Назад в управление функции")]
    ]

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


async def get_edit_messages_keyboard():
    """Меню редактирования сообщений"""
    keyboard = [
        [types.KeyboardButton(text="🔗 Изменить ссылку на клинику")],
        [types.KeyboardButton(text="✏️ Изменить сообщение вызова врача")],
        [types.KeyboardButton(text="✏️ Изменить приветствие сообщений")],
        [types.KeyboardButton(text="⬅️ Назад в настройки")]
    ]

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Редактирование сообщений..."
    )

async def get_record_keyboard():
    """Клавиатура для записи с учетом включенных/выключенных кнопок"""
    buttons = []

    # Проверяем статус каждой кнопки в БД
    if await get_button_status("call_doctor"):
        buttons.append([types.KeyboardButton(text="Вызов врача на дом")])

    if await get_button_status("clinic_appointment"):
        buttons.append([types.KeyboardButton(text="Записаться на прием в частную клинику")])

    if await get_button_status("individual_consultation"):
        buttons.append([types.KeyboardButton(text="Консультация в индивидуальном порядке")])

    buttons.append([types.KeyboardButton(text="⬅️ Назад")])

    return types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


def get_back_keyboard():
    """Простая клавиатура с кнопкой Назад"""
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )


def get_dates_keyboard(weekdays):
    """Клавиатура с датами"""
    date_buttons = []
    row = []

    for i, date in enumerate(weekdays):
        from utils.date_utils import format_date_russian
        btn_text = format_date_russian(date)
        row.append(types.KeyboardButton(text=btn_text))

        if (i + 1) % 3 == 0:
            date_buttons.append(row)
            row = []

    if row:
        date_buttons.append(row)

    date_buttons.append([types.KeyboardButton(text="⬅️ Назад")])
    return types.ReplyKeyboardMarkup(keyboard=date_buttons, resize_keyboard=True)


def get_times_keyboard(time_slots):
    """Клавиатура со временем"""
    time_buttons = []
    row = []

    for slot_time, status in time_slots.items():
        if status == "свободно":
            btn_text = f"{slot_time} ✅"
        else:
            btn_text = f"{slot_time} ❌"

        row.append(types.KeyboardButton(text=btn_text))

        if len(row) == 2:
            time_buttons.append(row)
            row = []

    if row:
        time_buttons.append(row)

    time_buttons.append([types.KeyboardButton(text="⬅️ Назад к датам")])
    return types.ReplyKeyboardMarkup(keyboard=time_buttons, resize_keyboard=True)