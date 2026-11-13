from aiogram import Dispatcher, Bot, types
import logging
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from datetime import datetime

from config.config import ADMIN_ID
from database.operations import book_slot, get_available_slots, create_home_visit_request
from keyboards.keyboards import get_dates_keyboard, get_times_keyboard, get_start_keyboard, get_record_keyboard
from states.user_states import user_states, user_selections
from utils.date_utils import get_weekdays, format_date_russian



def register_consultation_handlers(dp: Dispatcher, bot: Bot):
    @dp.message(lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_complaints")
    async def handle_complaints_input(message: types.Message):
        user_id = message.from_user.id

        if message.text == "⬅️ Назад":
            user_states.pop(user_id, None)
            await message.answer("Возвращаемся в меню записи:", reply_markup=await get_record_keyboard())
            return

        user_data = user_states[user_id]
        phone_number = user_data["phone"]
        complaints = message.text

        user = message.from_user
        full_name = f"{user.last_name or ''} {user.first_name or ''}".strip()
        username = f"@{user.username}" if user.username else "нет"

        try:
            # СОХРАНЯЕМ В БАЗУ ДАННЫХ вместо отправки в сообщении
            success = create_home_visit_request(
                user_id=user_id,
                user_name=full_name,
                username=username,
                phone=phone_number,
                complaints=complaints
            )

            if success:
                # Дублируем уведомление администратору в Telegram
                await bot.send_message(
                    ADMIN_ID,
                    f"🏠 НОВЫЙ ВЫЗОВ НА ДОМ:\n"
                    f"👤 Имя: {full_name}\n"
                    f"📱 Username: {username}\n"
                    f"🔢 Телефон: {phone_number}\n"
                    f"📝 Жалобы: {complaints}\n"
                    f"⏰ Время заявки: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )

                await message.answer(
                    "✅ Спасибо! Заявка на вызов врача принята. "
                    "Врач свяжется с Вами в ближайшее время для уточнения деталей и согласования времени визита.",
                    reply_markup=await get_start_keyboard(message.from_user.id)
                )
            else:
                await message.answer(
                    "❌ Произошла ошибка при сохранении заявки. Пожалуйста, попробуйте позже.",
                    reply_markup=await get_start_keyboard()
                )

        except TelegramForbiddenError:
            await message.answer("❌ Ошибка: бот не может отправить сообщение администратору.",
                                 reply_markup=await get_start_keyboard())
        except TelegramRetryAfter as retry_error:
            await message.answer(f"❌ Слишком много запросов. Попробуйте через {retry_error.retry_after} секунд.",
                                 reply_markup=await get_start_keyboard())
        except TelegramAPIError:
            await message.answer("❌ Ошибка соединения с Telegram.", reply_markup=await get_start_keyboard())
        except Exception as e:
            logging.error(f"Ошибка при обработке вызова на дом: {e}")
            await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
                                 reply_markup=await get_start_keyboard())

        user_states.pop(user_id, None)

    # Остальные хендлеры остаются без изменений
    @dp.message(lambda message: message.text == "Консультация в индивидуальном порядке")
    async def handle_individual_consultation(message: types.Message):
        weekdays = get_weekdays(10)
        date_keyboard = get_dates_keyboard(weekdays)
        await message.answer("📅 Выберите дату консультации (только будние дни):", reply_markup=date_keyboard)

    @dp.message(lambda message: message.text in [format_date_russian(date) for date in get_weekdays(10)])
    async def handle_date_selection(message: types.Message):
        selected_date = message.text
        user_selections[message.from_user.id] = {"date": selected_date}

        time_slots = get_available_slots(selected_date)
        time_keyboard = get_times_keyboard(time_slots)

        await message.answer(f"🕐 Выберите время на {selected_date}:\n✅ - свободно, ❌ - занято",
                             reply_markup=time_keyboard)

    @dp.message(lambda message: "✅" in message.text or "❌" in message.text)
    async def handle_time_selection(message: types.Message):
        user_id = message.from_user.id

        if user_id not in user_selections:
            await message.answer("❌ Ошибка. Начните запись заново.")
            return

        # Извлекаем время из сообщения (оно в начале)
        selected_time = message.text.split(" ")[0]
        selected_date = user_selections[user_id]["date"]

        user = message.from_user
        full_name = f"{user.last_name or ''} {user.first_name or ''}".strip()

        success = book_slot(user_id, full_name, selected_date, selected_time)

        if success:
            await message.answer(
                f"✅ Вы записаны на консультацию!\n"
                f"📅 Дата: {selected_date}\n"
                f"🕐 Время: {selected_time}\n"
                f"💬 Формат: консультация в чате Telegram",
                reply_markup=await get_start_keyboard(message.from_user.id)
            )

            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🔔 Новая запись на консультацию:\n"
                    f"👤 Имя: {full_name}\n"
                    f"📱 Username: @{user.username or 'нет'}\n"
                    f"📅 Дата: {selected_date}\n"
                    f"🕐 Время: {selected_time}\n"
                    f"💬 Тип: индивидуальная консультация"
                )
            except Exception as e:
                logging.error(f"Ошибка уведомления админа: {e}")

            user_selections.pop(user_id, None)
        else:
            await message.answer(
                "❌ Это время уже занято. Выберите другое время:",
                reply_markup=await get_record_keyboard()
            )

    @dp.message(lambda message: message.text == "⬅️ Назад к датам")
    async def handle_back_to_dates(message: types.Message):
        user_selections.pop(message.from_user.id, None)
        weekdays = get_weekdays(10)
        date_keyboard = get_dates_keyboard(weekdays)
        await message.answer("📅 Выберите дату консультации:", reply_markup=date_keyboard)

    