import time
import logging
from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards.keyboards import get_start_keyboard
from states.user_states import user_last_command

# ✅ ИМПОРТИРУЕМ ФУНКЦИЮ СОХРАНЕНИЯ
from database.operations import save_user_on_start


def register_start_handlers(dp: Dispatcher):
    @dp.message(Command('start'))
    async def cmd_start(message: types.Message):
        user_id = message.from_user.id
        current_time = time.time()

        # Защита от дублирования команд
        if user_id in user_last_command:
            time_diff = current_time - user_last_command[user_id]
            if time_diff < 2:
                logging.info(f"Пропускаем дублирующий /start от пользователя {user_id}")
                return

        user_last_command[user_id] = current_time

        user = message.from_user
        full_name = f"{user.last_name or ''} {user.first_name or ''}".strip()

        # ✅ ДОБАВЬТЕ ЭТУ ОТЛАДОЧНУЮ ПЕЧАТЬ
        print(f"🔍 DEBUG /start: Пользователь ID={user_id}, имя='{full_name}'")

        # ✅ СОХРАНЯЕМ ПОЛЬЗОВАТЕЛЯ ПРИ СТАРТЕ
        success = save_user_on_start(
            telegram_id=user_id,
            full_name=full_name or user.username or f"Пользователь {user_id}"
        )

        print(f"🔍 DEBUG /start: Результат сохранения = {success}")

        logging.info(f"💾 Пользователь сохранен при /start: ID {user_id}, имя: '{full_name}'")

        await message.answer(
            f"""Здравствуйте, {full_name}. С помощью данного бота Вы сможете записаться ко мне на консультацию, а также получить консультацию в формате сообщение в чат Telegram. Нажмите соответствующие кнопки""",
            reply_markup=await get_start_keyboard(user_id)
        )