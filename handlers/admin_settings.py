import logging
from aiogram import Dispatcher, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config.config import ADMIN_ID
from handlers.settings_handlers import (
    change_doctor_call_message_start,
    change_doctor_call_message_finish,
    DoctorCallMessageStates
)
from keyboards.keyboards import (
    get_bot_settings_keyboard,
    get_manage_functions_keyboard,
    get_edit_messages_keyboard
)
from database.settings_db import get_bot_setting, set_bot_setting

# Импортируем функции кэша из admin_core.py
from .admin_core import (
    update_button_cache,
    get_cached_button_status,
    update_button_status_in_cache
)


# ✅ СОСТОЯНИЯ ДЛЯ НАСТРОЕК (только для изменения ссылки)
class SettingsStates(StatesGroup):
    waiting_for_consultation_link = State()


def register_admin_settings_handlers(dp: Dispatcher):
    """Регистрирует обработчики настроек админа"""
    logging.info("🔄 Регистрируем админ-обработчики настроек...")

    # ✅ ОБРАБОТЧИК: Кнопка "⚙️ Настройки бота"
    @dp.message(lambda message: message.text == "⚙️ Настройки бота")
    async def cmd_bot_settings(message: types.Message):
        """Показать настройки бота"""
        logging.info(f"⚙️ Обработчик 'Настройки бота' вызван для админа {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await message.answer(
            "⚙️ <b>Настройки бота</b>\n\n"
            "Управление функциями бота:",
            parse_mode="HTML",
            reply_markup=await get_bot_settings_keyboard()
        )

    # ✅ ОБРАБОТЧИК: Кнопка "⚙️ Управление функциями"
    @dp.message(lambda message: message.text == "⚙️ Управление функциями")
    async def cmd_manage_functions(message: types.Message):
        """Показать меню управления функциями"""
        logging.info(f"⚙️ Обработчик 'Управление функциями' вызван для админа {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await message.answer(
            "⚙️ <b>Управление функциями</b>\n\n"
            "Выберите раздел для управления:",
            parse_mode="HTML",
            reply_markup=await get_manage_functions_keyboard()
        )

    # ✅ ОБРАБОТЧИК: Кнопка "✏️ Редактирование сообщений"
    @dp.message(lambda message: message.text == "✏️ Редактирование сообщений")
    async def cmd_edit_messages(message: types.Message):
        """Показать меню редактирования сообщений"""
        logging.info(f"✏️ Обработчик 'Редактирование сообщений' вызван для админа {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await message.answer(
            "✏️ <b>Редактирование сообщений</b>\n\n"
            "Выберите сообщение для редактирования:",
            parse_mode="HTML",
            reply_markup=await get_edit_messages_keyboard()
        )

    # 🎛️ Управление кнопками (теперь доступно через меню управления функциями)
    @dp.message(lambda message: message.text == "🎛️ Управление кнопками")
    async def manage_buttons(message: types.Message):
        logging.info(f"🎛️ Обработчик 'Управление кнопками' вызван для пользователя {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await update_button_cache()
        call_doctor_status = await get_cached_button_status("call_doctor")
        clinic_status = await get_cached_button_status("clinic_appointment")
        consultation_status = await get_cached_button_status("individual_consultation")
        paid_consultation_status = await get_cached_button_status("paid_consultation")

        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="✅ Включить все кнопки")],
                [types.KeyboardButton(text="❌ Выключить все кнопки")],
                [types.KeyboardButton(text=f"{'❌ Выключить' if call_doctor_status else '✅ Включить'} вызов врача")],
                [types.KeyboardButton(text=f"{'❌ Выключить' if clinic_status else '✅ Включить'} запись в клинику")],
                [types.KeyboardButton(text=f"{'❌ Выключить' if consultation_status else '✅ Включить'} консультацию")],
                [types.KeyboardButton(
                    text=f"{'❌ Выключить' if paid_consultation_status else '✅ Включить'} платные консультации")],
                [types.KeyboardButton(text="⬅️ Назад в управление функции")]
            ],
            resize_keyboard=True
        )
        await message.answer("Управление кнопками:", reply_markup=keyboard)

    # ✅ Включить все кнопки
    @dp.message(lambda message: message.text == "✅ Включить все кнопки")
    async def enable_all_buttons(message: types.Message):
        logging.info(f"✅ Обработчик 'Включить все кнопки' вызван")
        await update_button_status_in_cache("call_doctor", True)
        await update_button_status_in_cache("clinic_appointment", True)
        await update_button_status_in_cache("individual_consultation", True)
        await update_button_status_in_cache("paid_consultation", True)
        await manage_buttons(message)

    # ❌ Выключить все кнопки
    @dp.message(lambda message: message.text == "❌ Выключить все кнопки")
    async def disable_all_buttons(message: types.Message):
        logging.info(f"❌ Обработчик 'Выключить все кнопки' вызван")
        await update_button_status_in_cache("call_doctor", False)
        await update_button_status_in_cache("clinic_appointment", False)
        await update_button_status_in_cache("individual_consultation", False)
        await update_button_status_in_cache("paid_consultation", False)
        await manage_buttons(message)

    # Вызов врача
    @dp.message(lambda message: message.text in ["❌ Выключить вызов врача", "✅ Включить вызов врача"])
    async def handle_call_doctor(message: types.Message):
        logging.info(f"🔄 Обработчик 'Вызов врача' вызван: {message.text}")
        current_status = await get_cached_button_status("call_doctor")
        new_status = not current_status
        await update_button_status_in_cache("call_doctor", new_status)
        await manage_buttons(message)

    # Запись в клинику
    @dp.message(lambda message: message.text in ["❌ Выключить запись в клинику", "✅ Включить запись в клинику"])
    async def handle_clinic_appointment(message: types.Message):
        logging.info(f"🔄 Обработчик 'Запись в клинику' вызван: {message.text}")
        current_status = await get_cached_button_status("clinic_appointment")
        new_status = not current_status
        await update_button_status_in_cache("clinic_appointment", new_status)
        await manage_buttons(message)

    # Консультация
    @dp.message(lambda message: message.text in ["❌ Выключить консультацию", "✅ Включить консультацию"])
    async def handle_individual_consultation(message: types.Message):
        logging.info(f"🔄 Обработчик 'Консультация' вызван: {message.text}")
        current_status = await get_cached_button_status("individual_consultation")
        new_status = not current_status
        await update_button_status_in_cache("individual_consultation", new_status)
        await manage_buttons(message)

    # Платные консультации
    @dp.message(lambda message: message.text in ["❌ Выключить платные консультации", "✅ Включить платные консультации"])
    async def handle_paid_consultation(message: types.Message):
        logging.info(f"🔄 Обработчик 'Платные консультации' вызван: {message.text}")
        current_status = await get_cached_button_status("paid_consultation")
        new_status = not current_status
        await update_button_status_in_cache("paid_consultation", new_status)
        await manage_buttons(message)



    # ✅ ОБРАБОТЧИК: Кнопка "⬅️ Назад в управление функции"
    @dp.message(lambda message: message.text == "⬅️ Назад в управление функции")
    async def cmd_back_to_manage_functions(message: types.Message):
        """Вернуться в меню управления функциями"""
        logging.info(f"⬅️ Обработчик 'Назад в управление функции' вызван для {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await cmd_manage_functions(message)

    # ✅ ОБРАБОТЧИК: Кнопка "⬅️ Назад в настройки" (работает из обоих подменю)
    @dp.message(lambda message: message.text == "⬅️ Назад в настройки")
    async def cmd_back_to_settings(message: types.Message):
        """Вернуться в главное меню настроек"""
        logging.info(f"⬅️ Обработчик 'Назад в настройки' вызван для {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await cmd_bot_settings(message)

    # ============================================================================
    # ✏️ ОБРАБОТЧИКИ ДЛЯ " Изменить приветствие сообщений"
    # ============================================================================

    # ✅ СОСТОЯНИЕ ДЛЯ ВВОДА ПРИВЕТСТВИЯ
    class WelcomeMessageStates(StatesGroup):
        waiting_for_new_message = State()

    # ✅ ОБРАБОТЧИК: Кнопка "✏️ Приветствие"
    @dp.message(lambda message: message.text == "✏️ Изменить приветствие сообщений")
    async def change_welcome_message_start(message: types.Message, state: FSMContext):
        """Начать изменение приветственного сообщения"""
        logging.info(f"✏️ Обработчик 'Приветствие' вызван для {message.from_user.id}")

        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        # Получаем текущее приветствие из БД
        from database.settings_db import get_welcome_message
        current_message = get_welcome_message()

        # Клавиатура для отмены
        cancel_keyboard = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )

        await message.answer(
            f"✏️ <b>Редактирование приветствия</b>\n\n"
            f"<b>Текущее сообщение:</b>\n"
            f"——————————————\n"
            f"{current_message}\n"
            f"——————————————\n\n"
            f"📝 Введите новое приветственное сообщение:\n"
            f"<i>(или нажмите '❌ Отменить')</i>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard
        )
        await state.set_state(WelcomeMessageStates.waiting_for_new_message)

    # ✅ ОБРАБОТЧИК: Получение нового приветствия от админа
    @dp.message(WelcomeMessageStates.waiting_for_new_message)
    async def change_welcome_message_finish(message: types.Message, state: FSMContext):
        """Завершить изменение приветствия"""
        logging.info(f"📝 Получено сообщение в состоянии изменения приветствия")

        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        # Проверяем отмену
        if message.text == "❌ Отменить":
            await message.answer(
                "❌ Изменение приветствия отменено",
                reply_markup=await get_edit_messages_keyboard()
            )
            await state.clear()
            return

        new_message = message.text.strip()

        # Проверка на пустое сообщение
        if not new_message:
            await message.answer(
                "⚠️ Сообщение не может быть пустым! Попробуйте еще раз:",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
                    resize_keyboard=True
                )
            )
            return

        # Сохраняем в БД
        from database.settings_db import set_welcome_message
        success = set_welcome_message(new_message)

        if success:
            # Показываем предпросмотр
            preview = new_message[:100] + "..." if len(new_message) > 100 else new_message

            await message.answer(
                f"✅ <b>Приветствие успешно обновлено!</b>\n\n"
                f"<b>Предпросмотр:</b>\n"
                f"——————————————\n"
                f"{preview}\n"
                f"——————————————",
                parse_mode="HTML",
                reply_markup=await get_edit_messages_keyboard()
            )
        else:
            await message.answer(
                "❌ <b>Ошибка при сохранении!</b>\n"
                "Попробуйте еще раз:",
                parse_mode="HTML",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
                    resize_keyboard=True
                )
            )
            return

        await state.clear()

    # ============================================================================
    # 🔗 ОБРАБОТЧИКИ ДЛЯ ИЗМЕНЕНИЯ ССЫЛКИ НА КЛИНИКУ
    # ============================================================================

    # ✅ ОБРАБОТЧИК: Кнопка "🔗 Изменить ссылку на клинику"
    @dp.message(lambda message: message.text == "🔗 Изменить ссылку на клинику")
    async def change_consultation_link_start(message: types.Message, state: FSMContext):
        """Начать изменение ссылки на запись в клинику"""
        logging.info(f"🔗 Обработчик 'Изменить ссылку на клинику' вызван для {message.from_user.id}")

        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        # Получаем текущую ссылку из БД
        current_link = get_bot_setting('consultation_link')

        # Клавиатура для отмены - всегда видима
        cancel_keyboard = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )

        await message.answer(
            f"📝 <b>Текущая ссылка:</b>\n<code>{current_link}</code>\n\n"
            "Введите новую ссылку для записи в клинику:\n"
            "<i>Или нажмите '❌ Отменить'</i>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard
        )
        await state.set_state(SettingsStates.waiting_for_consultation_link)

    # ✅ ОБРАБОТЧИК: Получение новой ссылки от админа
    @dp.message(SettingsStates.waiting_for_consultation_link)
    async def change_consultation_link_finish(message: types.Message, state: FSMContext):
        """Завершить изменение ссылки"""
        logging.info(f"📝 Получено сообщение в состоянии изменения ссылки: {message.text}")

        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        # Проверяем отмену
        if message.text == "❌ Отменить":
            await message.answer(
                "❌ Изменение ссылки отменено",
                reply_markup=await get_edit_messages_keyboard()
            )
            await state.clear()
            return

        new_link = message.text.strip()

        # Простая проверка
        if not new_link:
            await message.answer(
                "⚠️ Ссылка не может быть пустой! Попробуйте еще раз:",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
                    resize_keyboard=True
                )
            )
            return

        # Сохраняем в БД (старая запись автоматически удалится)
        success = set_bot_setting('consultation_link', new_link)

        if success:
            await message.answer(
                f"✅ <b>Ссылка успешно обновлена!</b>\n\n"
                f"Новая ссылка:\n<code>{new_link}</code>",
                parse_mode="HTML",
                reply_markup=await get_edit_messages_keyboard()
            )
        else:
            await message.answer(
                "❌ <b>Ошибка при сохранении!</b>\nПопробуйте еще раз:",
                parse_mode="HTML",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
                    resize_keyboard=True
                )
            )
            return

        # Очищаем состояние
        await state.clear()

    # ✅ ОБРАБОТЧИК: Кнопка "✏️ Изменить сообщение вызова врача"
    @dp.message(lambda message: message.text == "✏️ Изменить сообщение вызова врача")
    async def handle_change_doctor_call_message(message: types.Message, state: FSMContext):
        await change_doctor_call_message_start(message, state)

    # ✅ ОБРАБОТЧИК: Получение нового сообщения от админа
    @dp.message(DoctorCallMessageStates.waiting_for_new_message)
    async def handle_doctor_call_message_finish(message: types.Message, state: FSMContext):
        await change_doctor_call_message_finish(message, state)

    logging.info("✅ Админ-обработчики настроек зарегистрированы")