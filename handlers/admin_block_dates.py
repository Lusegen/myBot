# handlers/admin_block_dates.py
import logging
from datetime import datetime, timedelta
from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.config import ADMIN_ID
from database.blocked_dates import block_date, unblock_date, is_date_blocked
from utils.date_utils import format_date_russian


# Состояния для блокировки дней
class BlockDatesStates(StatesGroup):
    selecting_dates = State()


def get_next_25_dates():
    """Получить следующие 25 БУДНИХ дней"""
    dates = []
    current_date = datetime.now()
    days_added = 0

    while days_added < 25:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:  # пн-пт (0-4)
            dates.append(current_date)
            days_added += 1

    return dates


async def generate_dates_keyboard():
    """Создать клавиатуру с 25 датами и их статусами"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    dates = get_next_25_dates()
    buttons = []
    row = []

    for i, date in enumerate(dates, 1):
        date_str = format_date_russian(date)

        if is_date_blocked(date_str):
            status = "❌"
        else:
            status = "✅"

        button_text = f"{date_str} {status}"
        callback_data = f"block_toggle:{date_str}"

        row.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))

        if i % 3 == 0:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Только одна кнопка НАЗАД на всю ширину
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="block_back")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def register_admin_block_dates_handlers(dp: Dispatcher):
    """Регистрация обработчиков для блокировки дней"""
    logging.info("🔄 Регистрируем обработчики блокировки дней...")

    @dp.message(lambda message: message.text == "🚫 Блокировка дней")
    async def cmd_block_dates(message: types.Message, state: FSMContext):
        """Показать меню блокировки дней"""
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        keyboard = await generate_dates_keyboard()

        await message.answer(
            "🚫 <b>Блокировка дней</b>\n\n"
            "Нажимайте на даты, чтобы заблокировать (❌) или разблокировать (✅)\n"
            "После выбора нажмите 'Сохранить'",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await state.set_state(BlockDatesStates.selecting_dates)

    @dp.callback_query(lambda c: c.data.startswith('block_toggle:'), BlockDatesStates.selecting_dates)
    async def process_date_toggle(callback: types.CallbackQuery):
        """Обработка нажатия на дату"""
        date_str = callback.data.split(':')[1]

        if is_date_blocked(date_str):
            unblock_date(date_str)
            new_status = "✅"
        else:
            block_date(date_str, callback.from_user.id)
            new_status = "❌"

        keyboard = await generate_dates_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer(f"Дата {date_str} теперь {new_status}")

    @dp.callback_query(lambda c: c.data == 'block_back', BlockDatesStates.selecting_dates)
    async def process_back(callback: types.CallbackQuery, state: FSMContext):
        """Возврат без сохранения"""
        from keyboards.keyboards import get_manage_functions_keyboard

        await callback.message.edit_text(
            "⬅️ Возврат в меню управления функциями",
            reply_markup=None
        )
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=await get_manage_functions_keyboard()
        )
        await state.clear()
        await callback.answer()

    logging.info("✅ Обработчики блокировки дней зарегистрированы")