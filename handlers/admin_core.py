import logging
from aiogram import Dispatcher, types
from aiogram.filters import Command

from config.config import ADMIN_ID
from database.operations import get_user_appointments, get_all_appointments, get_pending_home_visits, delete_old_visits
from database.db_init import get_button_status, set_button_status
from keyboards.keyboards import (
    get_admin_main_keyboard,
    get_admin_user_panel_keyboard,
    get_start_keyboard
)

# Кэш для статусов кнопок (оставляем здесь, т.к. используется в обоих модулях)
button_status_cache = {}


async def update_button_cache():
    """Обновляем кэш статусов кнопок"""
    button_status_cache["call_doctor"] = await get_button_status("call_doctor")
    button_status_cache["clinic_appointment"] = await get_button_status("clinic_appointment")
    button_status_cache["individual_consultation"] = await get_button_status("individual_consultation")
    button_status_cache["paid_consultation"] = await get_button_status("paid_consultation")


async def get_cached_button_status(button_name: str) -> bool:
    """Получаем статус кнопки из кэша"""
    return button_status_cache.get(button_name, True)


async def update_button_status_in_cache(button_name: str, enabled: bool):
    """Обновляем статус кнопки в кэше и БД"""
    button_status_cache[button_name] = enabled
    await set_button_status(button_name, enabled)


def register_admin_core_handlers(dp: Dispatcher):
    """Регистрирует основные админ-обработчики"""
    logging.info("🔄 Регистрируем основные админ-обработчики...")

    # ✅ ОБРАБОТЧИК: Кнопка "👤 Пользовательская панель"
    @dp.message(lambda message: message.text == "👤 Пользовательская панель")
    async def cmd_user_panel(message: types.Message):
        """Показать пользовательскую панель администратору"""
        logging.info(f"👤 Обработчик 'Пользовательская панель' вызван для админа {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await message.answer(
            "👤 <b>Пользовательская панель</b>\n\n"
            "Здесь доступны функции обычного пользователя:",
            parse_mode="HTML",
            reply_markup=await get_admin_user_panel_keyboard()
        )

    # ✅ ОБРАБОТЧИК: Кнопка "⬅️ Назад в админ-панель" (из пользовательской панели)
    @dp.message(lambda message: message.text == "⬅️ Назад в админ-панель")
    async def cmd_back_to_admin_panel(message: types.Message):
        """Вернуться в главное меню админ-панели"""
        logging.info(f"⬅️ Обработчик 'Назад в админ-панель' вызван для {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        await message.answer(
            "👨‍⚕️ <b>Административная панель</b>",
            parse_mode="HTML",
            reply_markup=await get_admin_main_keyboard()
        )

    # ✅ ОБРАБОТЧИК: Кнопка "⬅️ Назад в меню" (старая кнопка, теперь ведет в админ-панель для админа)
    @dp.message(lambda message: message.text == "⬅️ Назад в меню")
    async def back_to_menu(message: types.Message):
        """Возврат в главное меню (для админа - в админ-панель)"""
        logging.info(f"⬅️ Обработчик 'Назад в меню' вызван для пользователя {message.from_user.id}")

        # Для админа - возврат в админ-панель
        if str(message.from_user.id) == str(ADMIN_ID):
            await message.answer(
                "👨‍⚕️ <b>Административная панель</b>",
                parse_mode="HTML",
                reply_markup=await get_admin_main_keyboard()
            )
        else:
            # Для обычных пользователей - старый функционал
            await message.answer(
                "Возвращаемся в главное меню:",
                reply_markup=await get_start_keyboard(message.from_user.id)
            )

    # 📋 Мои записи (теперь доступна из пользовательской панели админа)
    @dp.message(Command('мои_записи'))
    @dp.message(Command('my_appointments'))
    @dp.message(lambda message: message.text == "📋 Мои записи")
    async def cmd_my_appointments(message: types.Message):
        logging.info(f"📋 Обработчик 'Мои записи' вызван для пользователя {message.from_user.id}")
        appointments = get_user_appointments(message.from_user.id)
        if not appointments:
            await message.answer("У вас нет активных записей.")
            return
        text = "📋 Ваши записи:\n\n"
        for date, slot_time in appointments:
            text += f"📅 {date} в {slot_time}\n"
        await message.answer(text)

    # 👥 Все записи (остается в главном меню админа)
    @dp.message(Command('все_записи'))
    @dp.message(Command('admin_schedule'))
    @dp.message(lambda message: message.text == "👥 Все записи")
    async def cmd_admin_schedule(message: types.Message):
        logging.info(f"👥 Обработчик 'Все записи' вызван для пользователя {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return
        appointments = get_all_appointments()
        if not appointments:
            await message.answer("Нет активных записей.")
            return
        text = "📋 Все записи на прием:\n\n"
        for date, slot_time, user_name in appointments:
            text += f"📅 {date} {slot_time} - {user_name}\n"
        await message.answer(text)

    # 🏠 Заявки на вызов (остается в главном меню админа)
    @dp.message(Command('заявки_на_вызов'))
    @dp.message(Command('home_visits'))
    @dp.message(lambda message: message.text == "🏠 Заявки на вызов")
    async def cmd_home_visits(message: types.Message):
        logging.info(f"🏠 Обработчик 'Заявки на вызов' вызван для пользователя {message.from_user.id}")
        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return
        delete_old_visits(7)
        visits = get_pending_home_visits()
        if not visits:
            await message.answer("📭 Нет новых заявки на вызов врача на дом.")
            return
        text = "🏠 ЗАЯВКИ НА ВЫЗОВ ВРАЧА НА ДОМ:\n\n"
        for i, (name, username, phone, complaints, created_at) in enumerate(visits, 1):
            created_str = created_at.split('.')[0] if '.' in created_at else created_at
            text += (
                f"🔸 {i}. {name}\n"
                f"   👤 Телеграм: {username}\n"
                f"   📞 Телефон: {phone}\n"
                f"   📝 Жалобы: {complaints}\n"
                f"   ⏰ Заявка: {created_str}\n\n"
            )
        await message.answer(text)



    logging.info("✅ Основные админ-обработчики зарегистрированы")