from aiogram import Dispatcher, types
from keyboards.keyboards import get_record_keyboard, get_back_keyboard, get_start_keyboard
from states.user_states import user_states
from utils.validators import validate_phone_number
from config.config import ADMIN_ID
from keyboards.keyboards import get_admin_user_panel_keyboard
from database.settings_db import get_bot_setting

def register_record_handlers(dp: Dispatcher):
    @dp.message(lambda message: message.text == "📅 Записаться")
    async def handle_record_button(message: types.Message):
        await message.answer("Выберите вариант:", reply_markup=await get_record_keyboard())

    @dp.message(lambda message: message.text == "Вызов врача на дом")
    async def handle_home_visit(message: types.Message):
        # Получаем сообщение из БД настроек
        from database.settings_db import get_bot_setting
        custom_message = get_bot_setting('home_visit_message')

        # Если сообщение есть в БД и не пустое - используем его
        if custom_message and custom_message.strip():
            await message.answer(
                custom_message,
                reply_markup=get_back_keyboard()
            )
        else:
            # Если в БД пусто, используем старый хардкод (опционально)
            await message.answer(
                "Вы выбрали вызов врача на дом, пожалуйста, оставьте Ваш номер телефона, врач в свободное время свяжется с Вами и уточнит детали консультации (время и место). Стоимость консультации 100 долларов",
                reply_markup=get_back_keyboard()
            )

        await message.answer("Введите номер телефона:")
        user_states[message.from_user.id] = "waiting_phone"

    @dp.message(lambda message: message.text == "Записаться на прием в частную клинику")
    async def handle_private_clinic(message: types.Message):
        # ✅ ПОЛУЧАЕМ ССЫЛКУ ИЗ БД НАСТРОЕК
        consultation_link = get_bot_setting('consultation_link')

        await message.answer(
            f"📝 Для записи в частную клинику перейдите по ссылке:\n"
            f"👉 <a href='{consultation_link}'>Записаться на прием</a>",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )

    @dp.message(lambda message: user_states.get(message.from_user.id) == "waiting_phone")
    async def handle_phone_input(message: types.Message):
        user_input = message.text

        if message.text == "⬅️ Назад":
            user_states.pop(message.from_user.id, None)
            await message.answer("Возвращаемся в меню записи:", reply_markup=await get_record_keyboard())
            return

        # Очищаем телефон от потенциально опасных символов
        import re
        clean_phone = re.sub(r'[^\d+]', '', user_input)  # оставляем только цифры и +

        if not validate_phone_number(clean_phone):
            await message.answer(
                "❌ Номер телефона должен содержать 11 цифр. Попробуйте еще раз:",
                reply_markup=get_back_keyboard()
            )
            return

        user_states[message.from_user.id] = {"phone": clean_phone, "state": "waiting_complaints"}
        await message.answer("Теперь кратко опишите ваши жалобы:")

    @dp.message(lambda message: message.text == "⬅️ Назад")
    async def handle_back(message: types.Message):
        if str(message.from_user.id) == str(ADMIN_ID):
            # Для админа - возвращаем в пользовательскую панель
            await message.answer(
                "👤 <b>Пользовательская панель</b>\n\n"
                "Здесь доступны функции обычного пользователя:",
                parse_mode="HTML",
                reply_markup=await get_admin_user_panel_keyboard()
            )
        else:
            user_states.pop(message.from_user.id, None)
            await message.answer("Возвращаемся в главное меню:", reply_markup=await get_start_keyboard(message.from_user.id))