from aiogram import Dispatcher, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.operations import get_user_name
from database.consultation_db import consultation_db
from keyboards.paid_keyboards import get_phone_input_keyboard
from database.chat_messages_db import chat_messages_db
from database.settings_db import get_welcome_message  # ✅ Импорт приветствия

from datetime import datetime
from config.config import ADMIN_ID


class ConsultationStates(StatesGroup):
    """Состояния для консультации (упрощено)"""
    waiting_phone = State()  # Только одно состояние - ожидание телефона


async def handle_consultation_start(message: types.Message, state: FSMContext):
    """Обработчик кнопки 💬 Сообщение - упрощенная версия без оплаты"""
    user_id = message.from_user.id

    # Показываем проверку
    checking_msg = await message.answer("🔍 Проверка активных сессий...")

    # Проверяем есть ли активная сессия
    active_sessions = consultation_db.get_active_sessions(user_id)

    if active_sessions:
        # У пользователя есть активная сессия
        await checking_msg.edit_text(
            "✅ <b>У вас есть активная консультация!</b>\n\n"
            "Можете писать врачу в любое время в течение 24 часов.\n\n"
            "💡 <i>Просто напишите сообщение - оно будет доставлено врачу.</i>",
            parse_mode="HTML"
        )
        return

    # Нет активной сессии - показываем приветствие из БД
    await checking_msg.delete()  # Удаляем сообщение о проверке

    # ✅ ПОЛУЧАЕМ ПРИВЕТСТВИЕ ИЗ БД
    welcome_text = get_welcome_message()

    # Запрашиваем номер телефона
    await message.answer(
        f"{welcome_text}\n\n"
        f"📱 <b>Введите ваш номер телефона:</b>\n"
        f"Формат: +7XXX XXX XX XX или 8XXX XXX XX XX",
        reply_markup=get_phone_input_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ConsultationStates.waiting_phone)


async def handle_phone_input(message: types.Message, state: FSMContext):
    """Обработчик ввода номера телефона - создание бесплатной сессии"""

    # Проверка на админские команды (защита от конфликтов)
    admin_commands = [
        "📋 Мои записи", "👥 Все записи", "🏠 Заявки на вызов",
        "💬 Активные чаты", "⚙️ Управление кнопками",
        "✅ Включить все кнопки", "❌ Выключить все кнопки",
        "📊 Статус кнопок", "⬅️ Назад в меню"
    ]

    if message.text in admin_commands:
        return  # Не обрабатываем, передаем другим хендлерам

    if message.text == "⬅️ Назад":
        # Возвращаемся в главное меню
        from keyboards.keyboards import get_start_keyboard
        await message.answer(
            "Возвращаемся в главное меню",
            reply_markup=await get_start_keyboard(message.from_user.id)
        )
        await state.clear()
        return

    phone_number = message.text.strip()

    # Валидация номера телефона
    if not is_valid_phone(phone_number):
        await message.answer(
            "❌ <b>Неверный формат номера телефона.</b>\n\n"
            "Пожалуйста, введите номер в формате:\n"
            "+7XXX XXX XX XX или 8XXX XXX XX XX\n\n"
            "<i>Или нажмите '⬅️ Назад' для возврата</i>",
            parse_mode="HTML"
        )
        return

    # ✅ СОЗДАЕМ СЕССИЮ (БЕЗ ОПЛАТЫ)
    session_id = consultation_db.create_session(
        patient_id=message.from_user.id,
        session_type="primary",  # ✅ Используем существующий тип
        phone_number=phone_number
    )

    if not session_id:
        from keyboards.keyboards import get_back_keyboard
        await message.answer(
            "❌ Ошибка при создании сессии. Попробуйте позже.",
            reply_markup=get_back_keyboard()
        )
        await state.clear()
        return

    # ✅ АКТИВИРУЕМ СЕССИЮ СРАЗУ (БЕЗ ОПЛАТЫ)
    activation_success = consultation_db.activate_session(session_id)

    if not activation_success:
        from keyboards.keyboards import get_back_keyboard
        await message.answer(
            "❌ Ошибка при активации сессии. Попробуйте позже.",
            reply_markup=get_back_keyboard()
        )
        await state.clear()
        return

    # Получаем информацию о сессии для подтверждения
    session = consultation_db.get_session(session_id)

    # Сообщаем пользователю об успехе
    await message.answer(
        "✅ <b>Сессия создана!</b>\n\n"
        "🎉 Теперь вы можете общаться с врачом в течение 24 часов.\n\n"
        "💬 <b>Как это работает:</b>\n"
        "• Просто напишите сообщение - оно будет доставлено врачу\n"
        "• Врач ответит вам в ближайшее время\n"
        "• Диалог будет продолжаться 24 часа с момента активации\n\n"
        "📱 <b>Ваш номер для связи:</b>\n"
        f"<code>{phone_number}</code>\n\n"
        "👇 <i>Напишите ваше сообщение врачу...</i>",
        parse_mode="HTML"
    )

    # Отправляем служебное сообщение врачу о новой сессии
    doctor_id = consultation_db.get_doctor_id()
    if doctor_id:
        patient_name = get_user_name(message.from_user.id)
        expires_at = session.get('expires_at', 'Не указано')
        if expires_at != 'Не указано' and expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                expires_str = expires_dt.strftime("%d.%m.%Y %H:%M")
            except:
                expires_str = str(expires_at)
        else:
            expires_str = "Не указано"

        await message.bot.send_message(
            doctor_id,
            f"🆕 <b>НОВАЯ КОНСУЛЬТАЦИЯ</b>\n\n"
            f"👤 Пациент: {patient_name}\n"
            f"📱 Телефон: {phone_number}\n"
            f"🆔 Сессия: #{session_id}\n"
            f"⏰ Действует до: {expires_str}\n\n"
            f"💬 Пациент скоро напишет сообщение.",
            parse_mode="HTML"
        )

    await state.clear()


def is_valid_phone(phone: str) -> bool:
    """Простая валидация номера телефона"""
    # Убираем все нецифровые символы кроме +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

    # Проверяем основные форматы
    if cleaned.startswith('+7') and len(cleaned) == 12:
        return True
    elif cleaned.startswith('7') and len(cleaned) == 11:
        return True
    elif cleaned.startswith('8') and len(cleaned) == 11:
        return True
    elif len(cleaned) == 10:  # Без кода страны
        return True

    return False


# ⚠️ ВНИМАНИЕ: Функции handle_patient_message и handle_doctor_reply
# остаются без изменений - они отвечают за переписку и должны работать как раньше

async def handle_patient_message(message: types.Message):
    """Обработчик сообщений от пациентов с активными сессиями"""
    user_id = message.from_user.id

    # Проверяем, не является ли отправитель врачом
    if str(user_id) == str(ADMIN_ID):
        return False

    # Проверяем есть ли активная сессия у пользователя
    active_sessions = consultation_db.get_active_sessions(user_id)

    if not active_sessions:
        return False  # Нет активной сессии - игнорируем

    session = active_sessions[0]

    # Проверяем, не истекла ли сессия
    if session.get('expires_at'):
        expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
        if datetime.now() > expires_at:
            # Сессия просрочена - обновляем статус
            consultation_db.update_session_status(session['id'], 'expired')
            await message.answer(
                "⏰ <b>Время вашей консультации истекло.</b>\n\n"
                "Для продолжения общения с врачом начните новую сессию через меню.",
                parse_mode="HTML"
            )
            return True

    # У пользователя есть активная сессия - пересылаем сообщение врачу
    doctor_id = consultation_db.get_doctor_id()

    if doctor_id:
        # Рассчитываем оставшееся время
        if session.get('activated_at'):
            activated_at = datetime.fromisoformat(session['activated_at'])
            time_passed = datetime.now() - activated_at
            hours_left = max(0.0, 24 - time_passed.total_seconds() / 3600)
            time_text = f"🕐 Осталось: {hours_left:.1f} часов"
        else:
            time_text = "🕐 Время не установлено"

        # Сохраняем сообщение пациента в БД
        chat_messages_db.save_message(
            session_id=session['id'],
            sender_id=user_id,
            sender_type='patient',
            message_text=message.text
        )

        # Формируем текст сообщения для врача
        patient_name = get_user_name(user_id)

        patient_info = (
            f"👤 Пациент: {patient_name}\n"
            f"💬 Сессия: #{session['id']}\n"
            f"📱 Телефон: {session['phone_number']}\n"
            f"{time_text}\n"
            f"➖➖➖➖➖➖➖➖➖➖"
        )

        # Проверяем: врач уже в режиме чата с этим пациентом?
        from handlers.admins.chat_manager import active_doctor_chats

        is_doctor_in_chat_with_this_patient = (
                doctor_id and
                doctor_id in active_doctor_chats and
                active_doctor_chats[doctor_id]["patient_id"] == user_id
        )

        if is_doctor_in_chat_with_this_patient:
            # Врач уже в чате - просто пересылаем без кнопки
            await message.bot.send_message(
                doctor_id,
                f"{patient_info}\n\n{message.text}"
            )
        else:
            # Показываем кнопку "Ответить"
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(
                        text="💬 Ответить",
                        callback_data=f"reply_chat:{session['id']}"
                    )]
                ]
            )
            await message.bot.send_message(
                doctor_id,
                f"{patient_info}\n\n{message.text}",
                reply_markup=keyboard
            )

        # Подтверждаем пациенту
        await message.answer("✅ Сообщение отправлено врачу. Ожидайте ответа.")
        return True
    else:
        from keyboards.keyboards import get_back_keyboard
        await message.answer(
            "❌ Врач недоступен. Попробуйте позже.",
            reply_markup=get_back_keyboard()
        )
        return True

async def handle_doctor_reply(message: types.Message):
    """Обработчик ответов врача на сообщения пациентов (без изменений)"""
    user_id = message.from_user.id

    if str(user_id) != str(ADMIN_ID):
        return False

    if message.reply_to_message and "👤 Пациент:" in message.reply_to_message.text:
        lines = message.reply_to_message.text.split('\n')
        session_id = None

        for line in lines:
            if line.startswith('👤 Пациент:'):
                # Пропускаем, нам нужен только session_id
                continue
            elif line.startswith('💬 Сессия: #') or '💬 Сессия: #' in line:
                try:
                    session_id = int(line.split('#')[1].strip())
                except (IndexError, ValueError):
                    # Неправильный формат строки или не число
                    pass
                except Exception:
                    # Любая другая ошибка
                    pass

        if not session_id:
            return False

        # Получаем сессию
        session = consultation_db.get_session(session_id)
        if not session:
            await message.answer("❌ Сессия не найдена")
            return True

        # Сохраняем ответ врача
        chat_messages_db.save_message(
            session_id=session_id,
            sender_id=user_id,
            sender_type='doctor',
            message_text=message.text
        )

        # Отправляем пациенту
        await message.bot.send_message(
            session['patient_id'],
            f"👨‍⚕️ <b>Врач:</b>\n{message.text}\n\n"
            f"💡 Вы можете продолжить диалог, просто написав сообщение.",
            parse_mode="HTML"
        )
        await message.answer("✅ Ответ отправлен пациенту.")
        return True

    return False

# Регистрация обработчиков
def register_paid_consultation_handlers(dp: Dispatcher):
    """Регистрация всех хендлеров консультаций (упрощенная версия)"""

    # Основной обработчик кнопки "💬 Сообщение"
    dp.message.register(handle_consultation_start, lambda message: message.text == "💬 Сообщение")

    # Обработчик ввода телефона
    dp.message.register(handle_phone_input, StateFilter(ConsultationStates.waiting_phone))

    # Обработчики сообщений (переписка)
    dp.message.register(
        handle_patient_message,
        lambda message: (
                str(message.from_user.id) != str(ADMIN_ID) and
                bool(message.text) and
                not message.text.startswith('/')
        )
    )
    dp.message.register(handle_doctor_reply)