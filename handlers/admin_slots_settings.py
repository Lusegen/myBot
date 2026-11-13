# handlers/admin_slots_settings.py
import logging
from datetime import datetime, timedelta
from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.config import ADMIN_ID
from database.settings_db import get_bot_setting, set_bot_setting
from keyboards.keyboards import get_manage_functions_keyboard, get_slots_settings_keyboard


# Состояния для управления слотами
class SlotsSettingsStates(StatesGroup):
    managing_slots = State()


def adjust_time(time_str: str, increment: bool, is_start: bool) -> str:
    """Изменение времени на 1 час с учетом диапазонов"""
    time_obj = datetime.strptime(time_str, '%H:%M')

    if increment:
        new_time = time_obj + timedelta(hours=1)
    else:
        new_time = time_obj - timedelta(hours=1)

    # Проверяем диапазоны
    if is_start:
        min_time = datetime.strptime('07:00', '%H:%M')
        max_time = datetime.strptime('14:00', '%H:%M')
    else:
        min_time = datetime.strptime('12:00', '%H:%M')
        max_time = datetime.strptime('22:00', '%H:%M')

    # Ограничиваем диапазоном
    if new_time < min_time:
        new_time = min_time
    elif new_time > max_time:
        new_time = max_time

    return new_time.strftime('%H:%M')


def register_admin_slots_handlers(dp: Dispatcher):
    """Регистрирует обработчики для настройки временных слотов"""
    logging.info("🔄 Регистрируем обработчики настройки слотов...")

    # ✅ ОБРАБОТЧИК: Кнопка "⏰ Настройка временных слотов" (главный вход)
    @dp.message(lambda message: message.text == "⏰ Настройка временных слотов")
    async def cmd_slots_settings(message: types.Message, state: FSMContext):
        """Показать меню настройки временных слотов"""
        logging.info(f"⏰ Обработчик 'Настройка временных слотов' вызван для админа {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        # Получаем текущие настройки
        start_time = get_bot_setting('individual_slots_start', '10:00')
        end_time = get_bot_setting('individual_slots_end', '17:00')

        # Показываем клавиатуру с текущими настройками
        keyboard = await get_slots_settings_keyboard(start_time, end_time)

        await message.answer(
            f"⏰ <b>Настройка временных слотов для консультаций</b>\n\n"
            f"Текущие настройки:\n"
            f"• Начало: <b>{start_time}</b>\n"
            f"• Окончание: <b>{end_time}</b>\n\n"
            f"Диапазоны:\n"
            f"• Начало: 07:00 - 14:00\n"
            f"• Окончание: 12:00 - 22:00\n\n"
            f"<i>Нажмите 'Начало' или 'Окончание', затем используйте ⬆️/⬇️</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Сохраняем текущие настройки в состоянии
        await state.update_data(
            start_time=start_time,
            end_time=end_time,
            last_selected="Начало"  # По умолчанию выбрано начало
        )
        await state.set_state(SlotsSettingsStates.managing_slots)

    # ✅ ОБРАБОТЧИК: ВСЕ сообщения в состоянии managing_slots
    @dp.message(SlotsSettingsStates.managing_slots)
    async def handle_slots_state(message: types.Message, state: FSMContext):
        """Обработка ВСЕХ сообщений в состоянии настройки слотов"""
        # ВАЖНО: Убираем любую другую обработку
        logging.info(f"🟢 СЛОТЫ ХЕНДЛЕР: получено сообщение '{message.text}'")
        """Обработка ВСЕХ сообщений в состоянии настройки слотов"""
        logging.info(f"🔍 Хендлер состояния получил сообщение: '{message.text}'")
        logging.info(f"🔍 Длина сообщения: {len(message.text)}")
        logging.info(f"🔍 Содержит 'Окончание'? {'Окончание' in message.text}")
        logging.info(f"🔍 Содержит 'Начало'? {'Начало' in message.text}")

        data = await state.get_data()
        start_time = data.get('start_time', '10:00')
        end_time = data.get('end_time', '17:00')
        last_selected = data.get('last_selected', 'Начало')

        logging.info(f"🔍 Текущие данные: start={start_time}, end={end_time}, last={last_selected}")



        # Обработка кнопок выбора - более гибкие условия
        if "Начало" in message.text:
            logging.info(f"🔵 Выбрано НАЧАЛО для редактирования")
            last_selected = "Начало"
            changed = True
        elif "Окончание" in message.text:
            logging.info(f"🔵 Выбрано ОКОНЧАНИЕ для редактирования")
            last_selected = "Окончание"
            changed = True

        # Обработка кнопок изменения
        elif message.text == "⬆️":
            logging.info(f"⬆️ Кнопка ВВЕРХ, редактируем: {last_selected}")
            if last_selected == "Начало":
                start_time = adjust_time(start_time, increment=True, is_start=True)
                logging.info(f"🕐 Новое время начала: {start_time}")
            else:
                end_time = adjust_time(end_time, increment=True, is_start=False)
                logging.info(f"🕐 Новое время окончания: {end_time}")
            changed = True
        elif message.text == "⬇️":
            logging.info(f"⬇️ Кнопка ВНИЗ, редактируем: {last_selected}")
            if last_selected == "Начало":
                start_time = adjust_time(start_time, increment=False, is_start=True)
                logging.info(f"🕐 Новое время начала: {start_time}")
            else:
                end_time = adjust_time(end_time, increment=False, is_start=False)
                logging.info(f"🕐 Новое время окончания: {end_time}")
            changed = True

        # Обработка кнопки сохранения
        elif message.text == "💾 Сохранить настройки":
            logging.info(f"💾 Сохраняем настройки: {start_time} - {end_time}")

            # Сохраняем в БД
            success_start = set_bot_setting('individual_slots_start', start_time)
            success_end = set_bot_setting('individual_slots_end', end_time)

            if success_start and success_end:
                # СРАЗУ обновляем расписание
                from database.db_init import update_database
                update_database()
                logging.info(f"🔄 Расписание обновлено с новыми слотами: {start_time} - {end_time}")

                await message.answer(
                    f"✅ <b>Настройки сохранены и расписание обновлено!</b>\n\n"
                    f"• Начало: <b>{start_time}</b>\n"
                    f"• Окончание: <b>{end_time}</b>\n\n"
                    f"Новые слоты уже доступны для записи.",
                    parse_mode="HTML",
                    reply_markup=await get_manage_functions_keyboard()
                )
            else:
                await message.answer(
                    "❌ <b>Ошибка сохранения настроек!</b>\nПопробуйте еще раз.",
                    parse_mode="HTML",
                    reply_markup=await get_slots_settings_keyboard(start_time, end_time)
                )

            await state.clear()
            return
        # Обработка кнопки возврата
        elif message.text == "⬅️ Назад в управление функции":
            logging.info(f"⬅️ Возврат в управление функциями")
            await message.answer(
                "Возвращаемся в управление функциями:",
                reply_markup=await get_manage_functions_keyboard()
            )
            await state.clear()
            return

        # Неизвестная команда
        else:
            logging.info(f"❓ Неизвестная команда: '{message.text}'")
            return

        # Если что-то изменилось - обновляем состояние и интерфейс
        if changed:
            await state.update_data(
                start_time=start_time,
                end_time=end_time,
                last_selected=last_selected
            )

            # Обновляем клавиатуру
            keyboard = await get_slots_settings_keyboard(start_time, end_time)

            # Отправляем обновленное сообщение
            await message.answer(
                f"⏰ <b>Настройка временных слотов для консультаций</b>\n\n"
                f"Текущие настройки:\n"
                f"• Начало: <b>{start_time}</b>\n"
                f"• Окончание: <b>{end_time}</b>\n\n"
                f"Диапазоны:\n"
                f"• Начало: 07:00 - 14:00\n"
                f"• Окончание: 12:00 - 22:00\n\n"
                f"<i>Редактируем: <b>{'НАЧАЛО' if last_selected == 'Начало' else 'ОКОНЧАНИЕ'}</b></i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            logging.info(f"🔄 Интерфейс обновлен: start={start_time}, end={end_time}, last={last_selected}")

    logging.info("✅ Обработчики настройки слотов зарегистрированы")