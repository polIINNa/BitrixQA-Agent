"""Обработка сообщений от клиентов."""
import asyncio

from aiogram import Bot, types
from aiogram.methods import ReadBusinessMessage

from telegram_bot.database import crud
from telegram_bot.database.models import SupportSession
from telegram_bot.enums import (
    ChatType,
    AssistantType,
    MessageRole,
    MessageType,
)
from telegram_bot.utils import has_media_content, get_media_content
from telegram_bot.constants import (
    AUTO_REPLY,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_SIMPLE,
    NEED_HUMAN_MESSAGE_WITH_GREETINGS,
    NEED_HUMAN_MESSAGE,
)
from telegram_bot.services import session as session_service
from telegram_bot.services import qa as qa_service
from telegram_bot.services import notification as notification_service
from telegram_bot.services import business_rules as business_rules_service
from telegram_bot.services.qa import QAResponse
from media_recognizer.api import extract_text_from_media


# =============================================================================
# Главный обработчик
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
    notification_service.cancel_followup(chat_id, followup_tasks)
    
    # Обработка медиа-контента
    media_data = await _extract_message_content(message, bot)
    message_text_content = media_data["text_content"]
    
    # Получение или создание сессии
    support_session = await session_service.get_or_create_active_session(chat_id=chat_id)
    
    # Автоответ (только для личных сообщений)
    if chat_type == ChatType.PRIVATE:
        await _send_auto_reply_if_needed(bot, message, support_session)
    
    # Если невозможно распознать текст сообщения
    if message_text_content is None:
        print("Невозможно извлечь текст из сообщения")
        await _handle_unrecognized_message(
            support_session=support_session,
            chat_type=chat_type,
            bot=bot,
            message=message,
            operator_id=operator_id,
            tech_support_account_id=tech_support_account_id,
            media_data=media_data,
        )
        return
    
    # Проверка смены интента (для всех типов сессий: и ai и human)
    is_new_intent = await qa_service.check_intent_change(
        session_id=support_session.id,
        user_message=message_text_content,
    )
    
    # Если интент изменился — создаём новую AI сессию
    if is_new_intent:
        print("Обнаружена смена темы, создание новой AI сессии")
        await session_service.close_session(support_session.id)
        support_session = await session_service.create_new_session(chat_id=support_session.chat_id)
    
    # Сохраняем сообщение в актуальной сессии
    await _save_user_message(support_session, message_text_content, media_data)
    
    # Если интент не менялся и сессию ведёт специалист — выходим
    # (новая сессия после смены интента всегда AI)
    if not is_new_intent and support_session.assistant_type == AssistantType.human:
        print("Сессию ведёт специалист, сообщение сохранено")
        return
    
    # AI сессия: отметка о прочтении (только для личных сообщений)
    print("Сессию ведёт AI-помощник")
    if chat_type == ChatType.PRIVATE:
        await bot(
            ReadBusinessMessage(
                business_connection_id=message.business_connection_id,
                chat_id=int(support_session.chat_id),
                message_id=message.message_id
            )
        )
    
    # Получаем ответ от QA агента
    qa_response = await qa_service.get_response(
        user_message=message_text_content,
        session_id=support_session.id,
    )
    
    print(f"Обработка ответа QA агента: {qa_response.message_type}")
    
    # Обработка ответа
    await _handle_qa_response(
        qa_response=qa_response,
        chat_type=chat_type,
        support_session=support_session,
        bot=bot,
        message=message,
        operator_id=operator_id,
        tech_support_account_id=tech_support_account_id,
        followup_tasks=followup_tasks,
    )


# =============================================================================
# Извлечение контента сообщения
# =============================================================================

async def _extract_message_content(message: types.Message, bot: Bot) -> dict:
    """Извлечь контент из сообщения (текст или медиа)."""
    if has_media_content(message):
        print("Сообщение клиента содержит медиа-контент")
        media_data = await get_media_content(message, bot)
        text_content = await extract_text_from_media(
            media_type=media_data["media_type"],
            content=media_data["content"],
            caption=media_data.get("caption"),
        )
        return {**media_data, "text_content": text_content}
    
    print("Сообщение клиента просто текст")
    return {"text_content": message.text, "media_type": None, "content": None}


# =============================================================================
# Обработка нераспознанного сообщения
# =============================================================================

async def _handle_unrecognized_message(
    support_session: SupportSession,
    chat_type: ChatType,
    bot: Bot,
    message: types.Message,
    operator_id: str,
    tech_support_account_id: str | None = None,
    media_data: dict | None = None,
) -> None:
    """Обработка сообщения, которое невозможно распознать."""
    print("Невозможно распознать текст сообщения")
    
    # Сохраняем сообщение
    await _save_user_message(support_session, None, media_data)
    
    # Если сессию ведёт специалист — выходим
    if support_session.assistant_type == AssistantType.human:
        print("Сессию ведёт специалист, сообщение сохранено")
        return
    
    # AI сессия — переключаем на специалиста
    print("Переключение на специалиста: невозможно определить сообщение")
    await _switch_to_human_specialist(
        chat_type=chat_type,
        support_session=support_session,
        bot=bot,
        message=message,
        operator_id=operator_id,
        tech_support_account_id=tech_support_account_id,
    )


# =============================================================================
# Обработка ответа QA агента
# =============================================================================

async def _handle_qa_response(
    qa_response: QAResponse,
    chat_type: ChatType,
    support_session: SupportSession,
    bot: Bot,
    message: types.Message,
    operator_id: str,
    followup_tasks: dict,
    tech_support_account_id: str | None = None,
) -> None:
    """Обработка результата QA агента."""
    message_type = qa_response.message_type
    
    # Переключение на специалиста
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
    
    # Не требует ответа
    if message_type == "no_need_reply":
        print("Сообщение не требует ответа")
        return
    
    # Положительный отклик
    if message_type == "positive_acknowledgement":
        print("Сообщение является положительным откликом")
        await _send_positive_acknowledgement_reply(bot, message, support_session)
        return
    
    # Ответ из базы знаний или чат
    if message_type in ("knowledge_required", "chat"):
        print("Поиск ответа в базе знаний либо простой чат")
        await _send_ai_answer(
            bot=bot,
            chat_type=chat_type,
            support_session=support_session,
            answer=qa_response.answer,
            message=message,
            followup_tasks=followup_tasks,
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

    text = NEED_HUMAN_MESSAGE_WITH_GREETINGS if len(support_session_messages) < 2 else NEED_HUMAN_MESSAGE
    
    await session_service.switch_to_human(support_session.id)
    
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
# Отправка сообщений
# =============================================================================

async def _send_auto_reply_if_needed(
    bot: Bot,
    message: types.Message,
    support_session: SupportSession,
) -> None:
    """Отправить автоответ, если нужно."""
    print("Проверка на автоответчик")
    should_send = await business_rules_service.should_send_auto_reply(chat_id=support_session.chat_id)
    
    if should_send:
        await crud.add_message(
            support_session_id=support_session.id,
            content=AUTO_REPLY,
            role=MessageRole.system
        )
        await bot.send_message(
            chat_id=support_session.chat_id,
            text=AUTO_REPLY,
            business_connection_id=message.business_connection_id
        )


async def _send_positive_acknowledgement_reply(
    bot: Bot,
    message: types.Message,
    support_session: SupportSession,
) -> None:
    """Отправить ответ на положительный отклик."""
    should_show_ad = await business_rules_service.should_show_ad_on_positive_acknowledgement(
        session_id=support_session.id
    )
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


async def _send_ai_answer(
    bot: Bot,
    support_session: SupportSession,
    chat_type: ChatType,
    message: types.Message,
    answer: str,
    followup_tasks: dict[str, asyncio.Task]
) -> None:
    """Отправить ответ AI и запланировать напоминание."""
    chat_id = support_session.chat_id
    
    await crud.add_message(
        support_session_id=support_session.id,
        content=answer,
        role=MessageRole.assistant,
        assistant_type=AssistantType.ai
    )
    
    # Отправка ответа
    if chat_type == ChatType.PRIVATE:
        await bot.send_message(
            chat_id=chat_id,
            text=answer,
            business_connection_id=message.business_connection_id
        )
    else:
        await message.reply(text=answer)
    
    # Планирование напоминания
    await notification_service.schedule_followup(
        chat_type=chat_type,
        message=message,
        support_session_id=support_session.id,
        followup_tasks=followup_tasks,
        bot=bot,
        chat_id=chat_id,
    )


# =============================================================================
# Сохранение сообщений
# =============================================================================

async def _save_user_message(
    support_session: SupportSession,
    message_text_content: str | None = None,
    media_data: dict | None = None,
) -> None:
    """Сохранить сообщение клиента в БД."""
    if media_data and media_data.get("media_type"):
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
