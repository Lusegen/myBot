import asyncio
import logging
from datetime import datetime
from aiogram import types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.operations import get_user_name
from config.config import ADMIN_ID
from database.consultation_db import consultation_db
from database.chat_messages_db import chat_messages_db

# ✅ ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ АКТИВНЫХ ДИАЛОГОВ ВРАЧА
# Формат: {doctor_id: {"chat_id": int, "patient_id": int, "last_activity": datetime}}
active_doctor_chats = {}


# ✅ ДОБАВЛЯЕМ СОСТОЯНИЯ ДЛЯ ОТВЕТА
class ChatStates(StatesGroup):
    waiting_reply = State()  # Ожидание текста ответа (оставляем для совместимости)


class ChatManager:
    def __init__(self, dp):
        self.dp = dp
        self.register_handlers()

    def register_handlers(self):
        """Регистрация обработчиков для управления чатами"""
        # Обработчик кнопки "💬 Активные чаты"
        self.dp.message.register(self.show_active_chats, F.text == "💬 Активные чаты")

        # Обработчики callback для inline-кнопок
        self.dp.callback_query.register(self.handle_view_chat, F.data.startswith("view_chat:"))
        self.dp.callback_query.register(self.handle_back_to_chats, F.data == "back_to_chats")
        self.dp.callback_query.register(self.handle_reply_chat, F.data.startswith("reply_chat:"))

        # ✅ ОБРАБОТЧИК ДЛЯ ИСТОРИИ СООБЩЕНИЙ
        self.dp.callback_query.register(self.handle_show_history, F.data.startswith("show_history:"))

        # ✅ ОБРАБОТЧИК ДЛЯ ВВОДА ТЕКСТА ОТВЕТА (оставляем для совместимости)
        self.dp.message.register(self.handle_reply_text, ChatStates.waiting_reply)

        # ✅ НОВЫЙ ОБРАБОТЧИК ДЛЯ СООБЩЕНИЙ ВРАЧА В РЕЖИМЕ ЧАТА
        self.dp.message.register(
            self.handle_doctor_message_in_chat,
            lambda message: (
                # Только врач
                    str(message.from_user.id) == str(ADMIN_ID) and
                    # Есть текст
                    message.text and
                    # НЕ команда
                    not message.text.startswith('/') and
                    # Врач ДОЛЖЕН БЫТЬ в активном чате
                    message.from_user.id in active_doctor_chats
            )
        )

    @staticmethod
    async def show_active_chats(message: types.Message):
        """Показать список активных чатов"""
        logging.info(f"💬 Обработчик 'Активные чаты' вызван для пользователя {message.from_user.id}")

        if str(message.from_user.id) != str(ADMIN_ID):
            await message.answer("❌ Доступ запрещен")
            return

        # Очищаем старые сессии
        deleted_count = consultation_db.cleanup_old_sessions(hours=72)
        if deleted_count > 0:
            logging.info(f"🧹 Автоматически удалено устаревших чатов: {deleted_count}")

        # Получаем активные сессии
        active_sessions = consultation_db.get_all_active_sessions()

        if not active_sessions:
            await message.answer("💬 Нет активных чатов.")
            return

        # Сортируем по новизне (сначала новые)
        active_sessions.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # Создаем сообщение с inline-кнопками
        text = "💬 <b>АКТИВНЫЕ ЧАТЫ</b>\n\n"

        # Создаем inline-кнопки
        inline_keyboard = []
        row = []

        for session in active_sessions:
            # Определяем "новизну" чата
            created_at = session.get('created_at', '')
            if 'T' in created_at:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_diff = datetime.now() - created_dt
                if time_diff.total_seconds() < 3600:  # Менее 1 часа
                    new_indicator = "🆕 "
                elif time_diff.total_seconds() < 10800:  # Менее 3 часов
                    new_indicator = "⏳ "
                else:
                    new_indicator = "💬 "
            else:
                new_indicator = "💬 "

            # Время до окончания
            if session.get('expires_at'):
                expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
                time_left = expires_at - datetime.now()
                hours_left = max(0, int(time_left.total_seconds() / 3600))
                time_text = f"⏰ {hours_left}ч"
            else:
                time_text = "⏰ ?"

            patient_name = get_user_name(session['patient_id'])
            patient_display = patient_name if patient_name else f"ID: {session['patient_id']}"

            text += (
                f"{new_indicator}<b>Чат #{session['id']}</b>\n"
                f"   👤 {patient_display}\n"
                f"   📱 {session['phone_number']}\n"
                f"   {time_text}\n\n"
            )

            # Добавляем кнопку для этого чата
            row.append(types.InlineKeyboardButton(
                text=f"👁️ Чат #{session['id']}",
                callback_data=f"view_chat:{session['id']}"
            ))

            if len(row) == 2:  # 2 кнопки в строке
                inline_keyboard.append(row)
                row = []

        if row:  # Добавляем оставшиеся кнопки
            inline_keyboard.append(row)

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        text += f"📊 Всего активных чатов: {len(active_sessions)}"

        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    async def handle_view_chat(self, callback: types.CallbackQuery):
        """Обработчик просмотра деталей чата"""
        chat_id = int(callback.data.split(":")[1])

        await callback.answer(f"Загружаем чат #{chat_id}...")

        # Используем get_session() вместо get_session_by_id()
        session = consultation_db.get_session(chat_id)

        if not session:
            await callback.message.answer("❌ Чат не найден")
            return

        # Форматируем информацию о чате
        text = self._format_chat_details(session)

        # ✅ ОБНОВЛЯЕМ КЛАВИАТУРУ - ДОБАВЛЯЕМ КНОПКУ "ИСТОРИЯ"
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_chat:{chat_id}")],
                [types.InlineKeyboardButton(text="📜 История", callback_data=f"show_history:{chat_id}")],
                [types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_chats")]
            ]
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

    @staticmethod
    async def handle_back_to_chats(callback: types.CallbackQuery):
        """Обработчик возврата к списку чатов (выход из режима чата)"""
        doctor_id = callback.from_user.id

        # ✅ ВЫХОД ИЗ РЕЖИМА ЧАТА (если был активен)
        if doctor_id in active_doctor_chats:
            chat_data = active_doctor_chats[doctor_id]
            chat_id = chat_data["chat_id"]
            del active_doctor_chats[doctor_id]
            logging.info(f"👨‍⚕️ Врач {doctor_id} вышел из режима чата #{chat_id}")

        await callback.answer("Возвращаемся к списку...")

        # Проверяем права доступа
        if str(callback.from_user.id) != str(ADMIN_ID):
            await callback.message.answer("❌ Доступ запрещен")
            return

        # Очищаем старые сессии
        deleted_count = consultation_db.cleanup_old_sessions(hours=72)
        if deleted_count > 0:
            logging.info(f"🧹 Автоматически удалено устаревших чатов: {deleted_count}")

        # Получаем активные сессии
        active_sessions = consultation_db.get_all_active_sessions()

        if not active_sessions:
            await callback.message.edit_text("💬 Нет активных чатов.")
            return

        # Сортируем по новизне (сначала новые)
        active_sessions.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # Создаем сообщение с inline-кнопками
        text = "💬 <b>АКТИВНЫЕ ЧАТЫ</b>\n\n"

        # Создаем inline-кнопки
        inline_keyboard = []
        row = []

        for session in active_sessions:
            # Определяем "новизну" чата
            created_at = session.get('created_at', '')
            if 'T' in created_at:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_diff = datetime.now() - created_dt
                if time_diff.total_seconds() < 3600:  # Менее 1 часа
                    new_indicator = "🆕 "
                elif time_diff.total_seconds() < 10800:  # Менее 3 часов
                    new_indicator = "⏳ "
                else:
                    new_indicator = "💬 "
            else:
                new_indicator = "💬 "

            # Время до окончания
            if session.get('expires_at'):
                expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
                time_left = expires_at - datetime.now()
                hours_left = max(0, int(time_left.total_seconds() / 3600))
                time_text = f"⏰ {hours_left}ч"
            else:
                time_text = "⏰ ?"

            patient_name = get_user_name(session['patient_id'])
            patient_display = patient_name if patient_name else f"ID: {session['patient_id']}"

            text += (
                f"{new_indicator}<b>Чат #{session['id']}</b>\n"
                f"   👤 {patient_display}\n"
                f"   📱 {session['phone_number']}\n"
                f"   {time_text}\n\n"
            )

            # Добавляем кнопку для этого чата
            row.append(types.InlineKeyboardButton(
                text=f"👁️ Чат #{session['id']}",
                callback_data=f"view_chat:{session['id']}"
            ))

            if len(row) == 2:  # 2 кнопки в строке
                inline_keyboard.append(row)
                row = []

        if row:  # Добавляем оставшиеся кнопки
            inline_keyboard.append(row)

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        text += f"📊 Всего активных чатов: {len(active_sessions)}"

        # Редактируем текущее сообщение
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

    # ✅ ИЗМЕНЯЕМ МЕТОД: теперь это ВХОД В РЕЖИМ ЧАТА
    @staticmethod
    async def handle_reply_chat(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик кнопки 'Ответить' - ВХОД В РЕЖИМ НЕПРЕРЫВНОГО ЧАТА"""
        chat_id = int(callback.data.split(":")[1])

        await callback.answer(f"💬 Режим чата с пациентом #{chat_id} включен")

        # Получаем информацию о чате
        session = consultation_db.get_session(chat_id)
        if not session:
            await callback.message.answer("❌ Чат не найден")
            await state.clear()
            return

        # ✅ ВХОД В РЕЖИМ ЧАТА
        doctor_id = callback.from_user.id
        active_doctor_chats[doctor_id] = {
            "chat_id": chat_id,
            "patient_id": session['patient_id'],
            "last_activity": datetime.now(),
            "phone_number": session['phone_number']
        }

        logging.info(f"👨‍⚕️ Врач {doctor_id} вошел в режим чата #{chat_id} с пациентом {session['patient_id']}")

        # ✅ ПОЛУЧАЕМ ИНФОРМАЦИЮ О ПАЦИЕНТЕ
        patient_id = session['patient_id']
        patient_name = get_user_name(patient_id)
        patient_display = f"👤 {patient_name}" if patient_name else f"👤 ID: {patient_id}"

        # ✅ ИСПРАВЛЕНИЕ: ДОБАВЛЯЕМ КНОПКУ "НАЗАД К СПИСКУ" (как раньше)
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_chats")]
            ]
        )

        # ✅ УБИРАЕМ КНОПКУ "ОТВЕТИТЬ" ИЗ ПРЕДЫДУЩЕГО СООБЩЕНИЯ
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass  # Если не удалось редактировать, не страшно

        # Сообщаем врачу с кнопкой "Назад к списку"
        await callback.message.answer(
            f"💬 <b>РЕЖИМ ЧАТА ВКЛЮЧЕН</b>\n\n"
            f"Вы в чате с {patient_display}\n"
            f"📱 {session['phone_number']}\n\n"
            f"<i>Все ваши сообщения теперь будут автоматически отправляться пациенту.</i>\n"
            f"Для выхода нажмите '⬅️ Назад к списку'\n\n"
            f"<b>Просто пишите сообщения ниже...</b>",
            parse_mode="HTML",
            reply_markup=keyboard  # ← кнопка "Назад к списку"
        )

        # Очищаем состояние FSM (если было)
        await state.clear()

    # ✅ НОВЫЙ МЕТОД: обработка сообщений врача в режиме чата
    @staticmethod
    async def handle_doctor_message_in_chat(message: types.Message):
        """Обработчик сообщений врача в режиме активного чата"""
        doctor_id = message.from_user.id

        # Проверяем, находится ли врач в активном чате
        if doctor_id not in active_doctor_chats:
            # Не в режиме чата - игнорируем
            logging.info(f"👨‍⚕️ Врач {doctor_id} не в режиме чата, игнорируем сообщение")
            return False

        # Обновляем время активности
        active_doctor_chats[doctor_id]["last_activity"] = datetime.now()

        chat_data = active_doctor_chats[doctor_id]
        chat_id = chat_data["chat_id"]
        patient_id = chat_data["patient_id"]

        logging.info(f"👨‍⚕️ Врач {doctor_id} пишет в чат #{chat_id} пациенту {patient_id}")

        # Получаем информацию о сессии
        session = consultation_db.get_session(chat_id)
        if not session:
            await message.answer("❌ Сессия не найдена. Режим чата отключен.")
            del active_doctor_chats[doctor_id]
            return True

        # ✅ СОХРАНЯЕМ СООБЩЕНИЕ ВРАЧА В БД
        message_id = chat_messages_db.save_message(
            session_id=chat_id,
            sender_id=doctor_id,
            sender_type='doctor',
            message_text=message.text
        )

        logging.info(f"💾 Сообщение врача сохранено в БД: ID {message_id}")

        # Отправляем сообщение пациенту
        try:
            await message.bot.send_message(
                chat_id=patient_id,
                text=f"👨‍⚕️ <b>Врач:</b>\n{message.text}\n\n"
                     f"💡 Вы можете продолжить диалог, просто написав сообщение.",
                parse_mode="HTML"
            )

            # ✅ ИСПРАВЛЕНИЕ: В КАЖДОМ СООБЩЕНИИ ВРАЧА ДОБАВЛЯЕМ ИНДИКАТОР РЕЖИМА
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_chats")]
                ]
            )

            # Формируем текст с индикатором режима
            patient_name = get_user_name(patient_id)
            patient_display = f"👤 {patient_name}" if patient_name else f"👤 ID: {patient_id}"

            # Формируем текст с индикатором режима
            reply_text = (
                f"✅ <b>Отправлено {patient_display}</b>\n"
                f"📱 {session['phone_number']}\n\n"
                f"⚡ <i>Режим чата активен</i>"
            )

            # Отправляем врачу подтверждение С КНОПКОЙ
            await message.answer(
                reply_text,
                parse_mode="HTML",
                reply_markup=keyboard  # ← кнопка в каждом сообщении!
            )

        except Exception as e:
            logging.error(f"❌ Ошибка при отправке сообщения пациенту: {e}")

            # Даже при ошибке показываем кнопку
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_chats")]
                ]
            )

            await message.answer(
                "❌ <b>Не удалось отправить сообщение.</b>\n"
                "Пациент возможно заблокировал бота или чат завершен.\n\n"
                "⚡ <i>Вы все еще в режиме чата. Нажмите 'Назад к списку' для выхода.</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )

        return True

    # ✅ СТАРЫЙ МЕТОД (оставляем для совместимости, но он теперь не должен вызываться)
    async def handle_reply_text(self, message: types.Message, state: FSMContext):
        """Обработчик введенного текста ответа (старый метод, для совместимости)"""
        # Этот метод теперь должен вызываться только если врач не в режиме чата

        # Проверяем, не находится ли врач в режиме чата
        doctor_id = message.from_user.id
        if doctor_id in active_doctor_chats:
            # Врач в режиме чата - сообщение уже обработано handle_doctor_message_in_chat
            await state.clear()
            return

        # Старая логика (оставляем на всякий случай)
        data = await state.get_data()
        chat_id = data.get('chat_id')

        if not chat_id:
            await message.answer("❌ Ошибка: ID чата не найден")
            await state.clear()
            return

        session = consultation_db.get_session(chat_id)
        if not session:
            await message.answer("❌ Чат не найден")
            await state.clear()
            return

        # Сохраняем сообщение
        chat_messages_db.save_message(
            session_id=chat_id,
            sender_id=message.from_user.id,
            sender_type='doctor',
            message_text=message.text
        )

        # Отправляем пациенту
        try:
            await message.bot.send_message(
                chat_id=session['patient_id'],
                text=f"👨‍⚕️ <b>Врач:</b>\n{message.text}\n\n"
                     f"💡 Вы можете продолжить диалог, просто написав сообщение.",
                parse_mode="HTML"
            )

            patient_name = get_user_name(session['patient_id'])
            patient_display = patient_name if patient_name else f"ID: {session['patient_id']}"

            await message.answer(
                f"✅ <b>Сообщение отправлено пациенту!</b>\n\n"
                f"📝 Чат #{chat_id}\n"
                f"👤 Пациент: {patient_display}\n"
                f"💬 Ваш ответ: {message.text[:50]}...",
                parse_mode="HTML"
            )

            text = self._format_chat_details(session)
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_chat:{chat_id}")],
                    [types.InlineKeyboardButton(text="📜 История", callback_data=f"show_history:{chat_id}")],
                    [types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_chats")]
                ]
            )

            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

        except Exception as e:
            logging.error(f"❌ Ошибка при отправке сообщения пациенту: {e}")
            await message.answer(
                "❌ <b>Не удалось отправить сообщение пациенту.</b>\n"
                "Возможно, пациент заблокировал бота или чат завершен.",
                parse_mode="HTML"
            )

        await state.clear()

    # ✅ МЕТОД ДЛЯ ИСТОРИИ СООБЩЕНИЙ
    async def handle_show_history(self, callback: types.CallbackQuery):
        """Обработчик кнопки 'История' в чате"""
        chat_id = int(callback.data.split(":")[1])

        await callback.answer(f"Загружаем историю чата #{chat_id}...")

        # Получаем информацию о чате
        session = consultation_db.get_session(chat_id)
        if not session:
            await callback.message.answer("❌ Чат не найден")
            return

        # Получаем сообщения из БД
        messages = chat_messages_db.get_session_messages(session_id=chat_id, limit=50)

        if not messages:
            # Нет сообщений - показываем информацию о чате
            text = self._format_chat_details(session)
            text += "\n\n📭 <b>В этом чате еще нет сообщений.</b>"

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_chat:{chat_id}")],
                    [types.InlineKeyboardButton(text="📜 История", callback_data=f"show_history:{chat_id}")],
                    [types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_chats")]
                ]
            )

            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            return

        # Форматируем историю сообщений
        history_text = self._format_chat_history(chat_id, session, messages)

        # Проверяем длину текста
        if len(history_text) > 4000:
            history_text = self._format_chat_history(chat_id, session, messages[-20:])
            history_text += "\n\n⚠️ <i>Показаны только последние 20 сообщений из-за ограничений Telegram.</i>"

        # Создаем клавиатуру для возврата
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад к чату", callback_data=f"view_chat:{chat_id}")],
                [types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_chats")]
            ]
        )

        # Показываем историю
        await callback.message.edit_text(history_text, parse_mode="HTML", reply_markup=keyboard)

    @staticmethod
    def _format_chat_details(session):
        """Форматирование детальной информации о чате"""
        # Время активации
        activated_at = "Не активирован"
        if session.get('activated_at'):
            activated_dt = datetime.fromisoformat(session['activated_at'].replace('Z', '+00:00'))
            activated_at = activated_dt.strftime("%d.%m.%Y %H:%M")

        # Время до окончания
        time_left = "Не установлено"
        if session.get('expires_at'):
            expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
            time_diff = expires_at - datetime.now()
            if time_diff.total_seconds() > 0:
                hours = int(time_diff.total_seconds() / 3600)
                minutes = int((time_diff.total_seconds() % 3600) / 60)
                time_left = f"{hours}ч {minutes}м"
            else:
                time_left = "⏰ Время истекло"

        # Тип консультации
        consultation_type = "Первичная" if session['session_type'] == 'primary' else "Повторная"

        # Получаем имя пациента
        patient_name = get_user_name(session['patient_id'])
        patient_display = patient_name if patient_name else f"ID: {session['patient_id']}"

        text = (
            f"💬 <b>ЧАТ #{session['id']} - ДЕТАЛИ</b>\n\n"
            f"👤 <b>Пациент:</b> {patient_display}\n"
            f"📱 <b>Телефон:</b> {session['phone_number']}\n"
            f"💬 <b>Тип:</b> {consultation_type}\n"
            
            f"⏰ <b>Активирован:</b> {activated_at}\n"
            f"⏳ <b>Осталось:</b> {time_left}\n"
            f"📊 <b>Статус:</b> {session['status']}"
        )

        return text

    @staticmethod
    def _format_chat_history(chat_id: int, session: dict, messages: list) -> str:
        """Форматирование истории сообщений чата"""

        consultation_type = "Первичная" if session['session_type'] == 'primary' else "Повторная"

        # Получаем имя пациента
        patient_name = get_user_name(session['patient_id'])
        patient_display = patient_name if patient_name else f"ID: {session['patient_id']}"

        text = (
            f"📜 <b>ЧАТ #{chat_id} - ИСТОРИЯ ПЕРЕПИСКИ</b>\n"
            f"💬 Тип: {consultation_type}\n"
            f"👤 Пациент: {patient_display}\n"
            f"📱 Телефон: {session['phone_number']}\n"
            f"📊 Сообщений: {len(messages)}\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
        )

        # Добавляем сообщения
        for message in messages:
            if message['sender_type'] == 'doctor':
                sender = "👨‍⚕️ <b>Врач</b>"
            else:
                sender = "👤 <b>Пациент</b>"

            time_str = message.get('created_at_formatted', message.get('created_at', 'Время не указано'))

            text += f"{sender} ({time_str}):\n"
            text += f"{message['message_text']}\n\n"

        # Добавляем информацию о статусе
        if session.get('expires_at'):
            expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
            time_diff = expires_at - datetime.now()
            if time_diff.total_seconds() > 0:
                hours = int(time_diff.total_seconds() / 3600)
                minutes = int((time_diff.total_seconds() % 3600) / 60)
                text += f"\n⏳ <b>Осталось времени:</b> {hours}ч {minutes}м"
            else:
                text += f"\n⏰ <b>Время сессии истекло</b>"

        return text


# ✅ ФУНКЦИЯ АВТООТКЛЮЧЕНИЯ (ВНЕ КЛАССА!)
async def check_inactive_doctors(bot: Bot):
    """Фоновая задача: проверка неактивных врачей в режиме чата"""
    while True:
        await asyncio.sleep(60)  # Проверяем каждую минуту

        current_time = datetime.now()
        doctors_to_remove = []

        for doctor_id, chat_data in active_doctor_chats.items():
            last_activity = chat_data.get("last_activity")
            if last_activity:
                inactive_time = current_time - last_activity
                # 20 минут = 1200 секунд
                if inactive_time.total_seconds() > 1200:
                    doctors_to_remove.append(doctor_id)

        # Отключаем неактивных врачей
        for doctor_id in doctors_to_remove:
            chat_data = active_doctor_chats[doctor_id]
            chat_id = chat_data["chat_id"]

            try:
                await bot.send_message(
                    doctor_id,
                    "⏰ <b>Режим чата отключен</b> (20 минут неактивности)",
                    parse_mode="HTML"
                )
                logging.info(f"👨‍⚕️ Автоотключение: врач {doctor_id} из чата #{chat_id}")
            except Exception as e:
                logging.info(f"⚠️ Не удалось уведомить врача {doctor_id}: {e}")

            # Удаляем из активных чатов
            del active_doctor_chats[doctor_id]


# Функция для регистрации в основном файле
def register_chat_handlers(dp):
    """Регистрация обработчиков чатов в диспетчере"""
    ChatManager(dp)