"""Обработка сообщений от клиентов."""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, types
from aiogram.methods import ReadBusinessMessage
from aiogram.types import ReactionTypeEmoji

from telegram_bot.database import crud
from telegram_bot.database.models import SupportSession, Message
from telegram_bot.enums import (
    ChatType,
    AssistantType,
    SupportStatus,
    MessageRole,
    MessageType,
)
from telegram_bot.utils import format_chat_from_message, has_media_content, get_media_content
from telegram_bot.constants import (
    AUTO_REPLY,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_SIMPLE,
    NEED_HUMAN_MESSAGE_WITH_GREETINGS,
    NEED_HUMAN_MESSAGE,
    CHECK_USER_MESSAGE,
)
from service import get_user_message_from_media, get_answer

logger = logging.getLogger(__name__)


# =============================================================================
# Главные обработчики
# =============================================================================

async def handle_client_message(
        chat_type: ChatType,
        chat_id: str,
        bot: Bot,
        message: types.Message,
        followup_tasks: dict[str, asyncio.Task],
        operator_id: str,
        tech_support_account_id: str | None = None,
) -> None:
    """
    Обработчик сообщений от пользователя.
    
    Args:
        chat_type: тип чата (личные сообщения или группа)
        chat_id: идентификатор чата
        bot: Telegram бот
        message: Telegram сообщение
        followup_tasks: задачи для отправки сообщения с напоминанием
        operator_id: id оператора для пересылки сообщений
        tech_support_account_id: id аккаунта поддержки (для личных сообщений)
    """
    # Отменяем предыдущую задачу напоминания
    if task := followup_tasks.pop(chat_id, None):
        task.cancel()
    
    # Обработка медиа-контента
    media_data: dict | None = None
    if has_media_content(message):
        print("Сообщение клиента содержит медиа-контент")
        media_data = await get_media_content(message, bot)
        message_text_content = await get_user_message_from_media(
            type=media_data["media_type"],
            content=media_data["content"],
            caption=media_data.get("caption"),
        )
    else:
        print("Сообщение клиента просто текст")
        message_text_content = message.text
    
    # Получение или создание (если новый чат) сессии
    support_session = await _get_active_support_session(chat_id=chat_id)
    support_session = await _get_or_create_session(
        support_session=support_session,
        chat_id=chat_id,
    )
    
    # Автоответ (только для личных сообщений)
    if chat_type == ChatType.PRIVATE:
        print("Проверка на автоответчик")
        should_send_auto_reply_check = await _should_send_auto_reply(session_id=support_session.id)
        if should_send_auto_reply_check:
            await crud.add_message(
                support_session_id=support_session.id,
                content=AUTO_REPLY,
                role=MessageRole.system
            )
            await bot.send_message(
                chat_id=chat_id,
                text=AUTO_REPLY,
                business_connection_id=message.business_connection_id
            )
    
    # Если сессию ведёт специалист — проверяем на смену темы
    if support_session.assistant_type == AssistantType.human:
        print("Сессию ведет специалист, проверка на смену темы")
        is_new_intent = await _check_intent_change_for_human_session(
            support_session=support_session,
            message_text_content=message_text_content,
        )
        
        if is_new_intent:
            print("Обнаружена смена темы в сессии специалиста, создание новой AI сессии")
            await _handle_intent_change(
                support_session=support_session,
                chat_type=chat_type,
                bot=bot,
                message=message,
                message_text_content=message_text_content,
                operator_id=operator_id,
                tech_support_account_id=tech_support_account_id,
                followup_tasks=followup_tasks,
                media_data=media_data,
            )
            return
        
        # Интент не изменился — просто сохраняем сообщение
        print("Интент не изменился, сохраняем сообщение для специалиста")
        await _save_user_message_to_db(
            support_session=support_session,
            message_text_content=message_text_content,
            media_data=media_data,
        )
        return
    
    print("Сессию ведет ai-помощник")
    await _process_ai_assistant_session(
        support_session=support_session,
        chat_type=chat_type,
        bot=bot,
        message=message,
        message_text_content=message_text_content,
        operator_id=operator_id,
        tech_support_account_id=tech_support_account_id,
        followup_tasks=followup_tasks,
        media_data=media_data,
    )


# =============================================================================
# Работа с сессиями
# =============================================================================

async def _get_active_support_session(chat_id: str) -> SupportSession | None:
    """Получить активную сессию поддержки для чата."""
    chat = await crud.get_or_create_chat(chat_id)
    return await crud.get_active_session(chat.id)


async def _get_or_create_session(
        support_session: SupportSession | None,
        chat_id: str,
) -> SupportSession:
    """Получить существующую или создать новую сессию поддержки."""
    if support_session is None:
        print("Нет действующей сессии, создание новой")
        return await crud.create_support_session(chat_id=chat_id)
    
    print("Есть действующая сессия, продолжение")
    return support_session


# =============================================================================
# Проверка смены интента
# =============================================================================

async def _check_intent_change_for_human_session(
        support_session: SupportSession,
        message_text_content: str | None,
) -> bool:
    """
    Проверить, сменилась ли тема диалога в сессии, которую ведёт специалист.
    
    Использует режим intent_check_only для эффективной проверки без полной
    обработки сообщения (только 1 вызов LLM вместо 3-5).
    
    Returns:
        True если интент изменился и нужно создать новую AI сессию,
        False если интент тот же и сообщение останется в текущей сессии.
    """
    # Если сообщение не распознано, не можем проверить интент
    if message_text_content is None:
        return False
    
    # Получаем историю сообщений текущей сессии
    session_messages = await crud.get_all_messages(support_session.id)
    chat_history = format_chat_from_message(support_session_messages=session_messages)
    
    # Вызываем QA агента в режиме только проверки интента
    qa_result = await get_answer(
        chat_history=chat_history,
        last_user_message=message_text_content,
        intent_check_only=True,
    )
    
    print(f"Проверка интента для human сессии: {qa_result['message_type']}")
    
    return qa_result["message_type"] == "intent_changed"


# =============================================================================
# Обработка активной сессии
# =============================================================================

async def _process_ai_assistant_session(
        support_session: SupportSession,
        chat_type: ChatType,
        bot: Bot,
        message: types.Message,
        operator_id: str,
        followup_tasks: dict,
        tech_support_account_id: str | None = None,
        message_text_content: str | None = None,
        media_data: dict | None = None,
) -> None:
    """Обработать сообщение клиента в сессии, которую ведёт AI."""
    # TODO: реализовать чтение сообщений в группе
    if chat_type == ChatType.PRIVATE:
        await bot(
            ReadBusinessMessage(
                business_connection_id=message.business_connection_id,
                chat_id=int(support_session.chat_id),
                message_id=message.message_id
            )
        )
    
    # Невозможно распознать сообщение — сохраняем и переключаем на специалиста
    if message_text_content is None:
        print("Переключение на специалиста: невозможно определить сообщение")
        await _save_user_message_to_db(
            support_session=support_session,
            message_text_content=message_text_content,
            media_data=media_data,
        )
        await _switch_to_human_specialist(
            chat_type=chat_type,
            support_session=support_session,
            bot=bot,
            message=message,
            operator_id=operator_id,
            tech_support_account_id=tech_support_account_id,
        )
        return
    
    # Получаем ответ от QA агента
    print("Сообщение клиента распознано, отвечает бот")
    session_messages = await crud.get_all_messages(support_session.id)
    chat_history = format_chat_from_message(support_session_messages=session_messages)
    qa_result = await get_answer(
        chat_history=chat_history,
        last_user_message=message_text_content,
    )
    
    print(f"Обработка ответа QA агента: {qa_result['message_type']}")
    
    await _handle_qa_response(
        qa_result=qa_result,
        chat_type=chat_type,
        support_session=support_session,
        bot=bot,
        message=message,
        operator_id=operator_id,
        tech_support_account_id=tech_support_account_id,
        followup_tasks=followup_tasks,
        message_text_content=message_text_content,
        media_data=media_data,
    )


async def _handle_qa_response(
        qa_result: dict,
        chat_type: ChatType,
        support_session: SupportSession,
        bot: Bot,
        message: types.Message,
        operator_id: str,
        followup_tasks: dict,
        tech_support_account_id: str | None = None,
        message_text_content: str | None = None,
        media_data: dict | None = None,
        skip_message_save: bool = False,
) -> None:
    """Обработка результата QA агента."""
    message_type = qa_result["message_type"]
    
    # Обработка смены темы диалога (новый интент)
    # Сообщение будет сохранено в новую сессию внутри _handle_intent_change
    if message_type == "intent_changed":
        print("Обнаружена смена темы диалога, создание новой сессии")
        await _handle_intent_change(
            support_session=support_session,
            chat_type=chat_type,
            bot=bot,
            message=message,
            message_text_content=message_text_content,
            operator_id=operator_id,
            tech_support_account_id=tech_support_account_id,
            followup_tasks=followup_tasks,
            media_data=media_data,
        )
        return
    
    # Для всех остальных типов — сохраняем сообщение в текущую сессию (если ещё не сохранено)
    if not skip_message_save:
        await _save_user_message_to_db(
            support_session=support_session,
            message_text_content=message_text_content,
            media_data=media_data,
        )
    
    if message_type == "negative":
        print("Переключение диалога на специалиста")
        await _switch_to_human_specialist(
            chat_type=chat_type,
            support_session=support_session,
            bot=bot,
            message=message,
            operator_id=operator_id,
            tech_support_account_id=tech_support_account_id,
        )
        return
    
    # TODO: реализовать отправку реакции для группы
    if message_type == "no_need_reply":
        print("Сообщение не требует ответа,")
        return
    
    if message_type == "positive_acknowledgement":
        print("Сообщение является положительным откликом")
        should_show_ad = await _positive_acknowledgement_date_check(session_id=support_session.id)
        reply_text = (
            POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD 
            if should_show_ad 
            else POSITIVE_ACKNOWLEDGEMENT_REPLY_SIMPLE
        )
        await crud.add_message(
            support_session_id=support_session.id,
            content=reply_text,
            role=MessageRole.assistant,
            assistant_type=AssistantType.ai
        )
        await bot.send_message(
            chat_id=support_session.chat_id,
            text=reply_text,
            business_connection_id=message.business_connection_id,
        )
        return
    
    if message_type in ("knowledge_required", "chat"):
        print("Поиск ответа в базе знаний либо простой чат")
        await _process_ai_assistant_answer(
            bot=bot,
            chat_type=chat_type,
            support_session=support_session,
            answer=qa_result["answer"],
            message=message,
            followup_tasks=followup_tasks,
        )


# =============================================================================
# Обработка смены темы диалога
# =============================================================================

async def _handle_intent_change(
    support_session: SupportSession,
    chat_type: ChatType,
    bot: Bot,
    message: types.Message,
    message_text_content: str,
    operator_id: str,
    followup_tasks: dict,
    tech_support_account_id: str | None = None,
    media_data: dict | None = None,
) -> None:
    """Обработка смены темы диалога: завершение старой сессии и создание новой."""
    # Завершаем текущую сессию
    await crud.update_session_status(session_id=support_session.id, status=SupportStatus.end)
    
    # Создаём новую сессию
    new_session = await crud.create_support_session(chat_id=support_session.chat_id)
    
    # Сохраняем сообщение пользователя в новую сессию
    await _save_user_message_to_db(
        support_session=new_session,
        message_text_content=message_text_content,
        media_data=media_data,
    )
    
    # Вызываем агента снова с пустой историей (новая сессия)
    qa_result = await get_answer(
        chat_history="",
        last_user_message=message_text_content,
    )
    
    print(f"Обработка ответа QA агента для новой сессии: {qa_result['message_type']}")
    
    # Обрабатываем результат (рекурсивно, но уже без intent_changed)
    await _handle_qa_response(
        qa_result=qa_result,
        chat_type=chat_type,
        support_session=new_session,
        bot=bot,
        message=message,
        operator_id=operator_id,
        tech_support_account_id=tech_support_account_id,
        followup_tasks=followup_tasks,
        message_text_content=message_text_content,
        media_data=media_data,
        skip_message_save=True,  # сообщение уже сохранено выше
    )


# =============================================================================
# Переключение на специалиста
# =============================================================================

async def _switch_to_human_specialist(
    chat_type: ChatType,
    bot: Bot,
    support_session: SupportSession,
    message: types.Message,
    operator_id: str,
    tech_support_account_id: str | None = None,
) -> None:
    """Переключить сессию на специалиста и отправить уведомления."""
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    user_message_count = sum(
        1 for msg in support_session_messages if msg.role == MessageRole.user
    )
    
    text = NEED_HUMAN_MESSAGE_WITH_GREETINGS if user_message_count == 1 else NEED_HUMAN_MESSAGE
    
    await crud.update_session_assistant_type(
        session_id=support_session.id,
        assistant_type=AssistantType.human
    )
    
    if chat_type == ChatType.PRIVATE:
        await bot.send_message(
            chat_id=support_session.chat_id,
            text=text,
            business_connection_id=message.business_connection_id
        )
        chat_link = f"https://t.me/{message.from_user.username}"
        await bot.send_message(
            chat_id=operator_id,
            text="Бот перевел поддержку на специалиста (ЛИЧНЫЕ СООБЩЕНИЯ)"
        )
        if tech_support_account_id:
            await bot.send_message(
                chat_id=tech_support_account_id,
                text=f"Ссылка на чат для специалиста: {chat_link}"
            )
    else:
        await message.reply(text=text)
        await bot.send_message(
            chat_id=operator_id,
            text=f"Бот перевел поддержку на специалиста (ГРУППА): {message.get_url()}"
        )


# =============================================================================
# Отправка ответов и напоминаний
# =============================================================================

async def _process_ai_assistant_answer(
    bot: Bot,
    support_session: SupportSession,
    chat_type: ChatType,
    message: types.Message,
    answer: str,
    followup_tasks: dict[str, asyncio.Task]
) -> None:
    """Обработка ответа агента: сохранение в БД, установка таймера, отправка сообщения."""
    chat_id = support_session.chat_id
    
    await crud.add_message(
        support_session_id=support_session.id,
        content=answer,
        role=MessageRole.assistant,
        assistant_type=AssistantType.ai
    )
    
    # Удаление старой задачи напоминания
    if old_task := followup_tasks.pop(chat_id, None):
        old_task.cancel()
    
    # Отправка ответа и установка таймера напоминания
    if chat_type == ChatType.PRIVATE:
        task = asyncio.create_task(_schedule_followup(
            bot=bot,
            chat_type=chat_type,
            message=message,
            chat_id=chat_id,
            support_session_id=support_session.id
        ))
        await bot.send_message(
            chat_id=chat_id,
            text=answer,
            business_connection_id=message.business_connection_id
        )
    else:
        task = asyncio.create_task(_schedule_followup(
            chat_type=chat_type,
            support_session_id=support_session.id,
            message=message,
        ))
        await message.reply(text=answer)
    
    followup_tasks[chat_id] = task


async def _schedule_followup(
        chat_type: ChatType,
        message: types.Message,
        support_session_id: str,
        bot: Bot | None = None,
        chat_id: str | None = None,
) -> None:
    """Отправить сообщение с вопросом 'всё ли понятно' через 30 минут."""
    await asyncio.sleep(1800)
    await crud.add_message(
        support_session_id=support_session_id,
        content=CHECK_USER_MESSAGE,
        role=MessageRole.system
    )
    if chat_type == ChatType.PRIVATE:
        await bot.send_message(
            chat_id=chat_id,
            text=CHECK_USER_MESSAGE,
            business_connection_id=message.business_connection_id
        )
    else:
        await message.reply(CHECK_USER_MESSAGE)


# =============================================================================
# Сохранение сообщений
# =============================================================================

async def _save_user_message_to_db(
        support_session: SupportSession,
        message_text_content: str | None = None,
        media_data: dict | None = None,
) -> None:
    """Сохранить сообщение клиента в БД."""
    if media_data:
        await crud.add_message(
            support_session_id=support_session.id,
            role=MessageRole.user,
            type=media_data["media_type"],
        )
    await crud.add_message(
        support_session_id=support_session.id,
        content=message_text_content,
        role=MessageRole.user,
        type=MessageType.text
    )


# =============================================================================
# Бизнес-правила
# =============================================================================

async def _should_send_auto_reply(session_id: str) -> bool:
    """Определяет, нужно ли отправить автоответ."""
    session_messages = await crud.get_all_messages(session_id)
    
    # Первая сессия и первое сообщение
    session_number = _get_session_number(session_id)
    if session_number == 1 and len(session_messages) == 1:
        return True
    
    # Проверка давности последнего сообщения
    if not session_messages:
        return True
    return _is_message_older_than_days(session_messages[-1], days=14)


async def _positive_acknowledgement_date_check(session_id: str) -> bool:
    """Определение показа рекламы при положительном отклике."""
    session_messages = await crud.get_all_messages(session_id)
    if not session_messages:
        return True
    return _is_message_older_than_days(session_messages[-1], days=10)


def _get_session_number(session_id: str) -> int:
    """Извлечь номер сессии из session_id."""
    try:
        return int(session_id.rsplit("_", 1)[-1])
    except (ValueError, IndexError):
        return 0


def _is_message_older_than_days(message: Message, days: int) -> bool:
    """Проверить, старше ли сообщение указанного количества дней."""
    if not message.created_at_str:
        return True
    
    try:
        message_date = datetime.fromisoformat(message.created_at_str)
        return datetime.now() - message_date >= timedelta(days=days)
    except Exception as e:
        logger.warning(f"Ошибка парсинга даты: {e}")
        return True
