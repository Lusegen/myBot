import logging
from aiogram import types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config.config import ADMIN_ID
from database.settings_db import get_bot_setting, set_bot_setting
from keyboards.keyboards import get_bot_settings_keyboard


class DoctorCallMessageStates(StatesGroup):
    waiting_for_new_message = State()


async def change_doctor_call_message_start(message: types.Message, state: FSMContext):
    """Начать изменение сообщения для вызова врача"""
    logging.info(f"✏️ Обработчик 'Изменить сообщение вызова врача' вызван для {message.from_user.id}")

    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Доступ запрещен")
        return

    # Получаем текущее сообщение из БД
    current_message = get_bot_setting('home_visit_message')

    # Если сообщение еще не сохранено, показываем стандартное
    if not current_message:
        current_message = (
            "🏥 Сообщение еще не настроено. "
            "Текущий текст  будет использоваться, пока не установите новое."
        )

    # Клавиатура для отмены
    cancel_keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True
    )

    await message.answer(
        f"✏️ <b>Изменение сообщения вызова врача</b>\n\n"
        f"<b>Текущее сообщение:</b>\n"
        f"{current_message}\n\n"
        "<b>Введите новое сообщение, которое будет появляться при нажатии пациента на кнопку вызов врача на дом:</b>\n"
        "<i>Или нажмите '❌ Отменить'</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard
    )
    await state.set_state(DoctorCallMessageStates.waiting_for_new_message)


async def change_doctor_call_message_finish(message: types.Message, state: FSMContext):
    """Завершить изменение сообщения вызова врача"""
    logging.info(f"✏️ Получено новое сообщение для вызова врача: {message.text}")

    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return

    # Проверяем отмену
    if message.text == "❌ Отменить":
        await message.answer(
            "❌ Изменение сообщения отменено",
            reply_markup=await get_bot_settings_keyboard()
        )
        await state.clear()
        return

    new_message = message.text.strip()

    # Простая проверка
    if not new_message:
        await message.answer(
            "⚠️ Сообщение не может быть пустым! Попробуйте еще раз:",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True
            )
        )
        return

    # Сохраняем в БД (старая запись автоматически заменится благодаря REPLACE)
    success = set_bot_setting('home_visit_message', new_message)

    if success:
        await message.answer(
            f"✅ <b>Сообщение успешно обновлено!</b>\n\n"
            f"<b>Новое сообщение:</b>\n{new_message}",
            parse_mode="HTML",
            reply_markup=await get_bot_settings_keyboard()
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