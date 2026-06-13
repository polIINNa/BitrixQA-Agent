"""Обработка сообщений от клиентов."""
import asyncio
import logging
from collections import defaultdict

from aiogram import Bot, types
from aiogram.methods import ReadBusinessMessage

from telegram_bot.database import crud
from telegram_bot.database.models import SupportSession, Message
from telegram_bot.enums import (
    AssistantType,
    ChatType,
    MessageRole,
    MessageType,
    SupportStatus,
)
from telegram_bot.utils import (
    MediaData,
    has_media_content,
    get_media_content,
    get_message_media_type,
    content_type_to_message_type,
)
from telegram_bot.constants import (
    AUTO_REPLY,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_SIMPLE,
    NEED_HUMAN_MESSAGE_WITH_GREETINGS,
    NEED_HUMAN_MESSAGE,
)
from telegram_bot.services import qa as qa_service
from telegram_bot.services import chat_flow as chat_flow_service
from telegram_bot.services.qa import QAResponse
from media_recognizer.api import extract_text_from_media

logger = logging.getLogger(__name__)


# Блокировки по chat_id: сериализуют обработку сообщений одного чата, чтобы
# исключить гонки при создании сессии / сохранении истории и гарантировать порядок.
# Бот — один процесс с одним event loop, поэтому in-process локов достаточно.
_chat_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _get_chat_lock(chat_id: str) -> asyncio.Lock:
    return _chat_locks[chat_id]


# =============================================================================
# Главный обработчик сообщения пользователя
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
    chat_flow_service.cancel_followup(chat_id, followup_tasks)

    # Сериализуем обработку сообщений одного чата: порядок + защита от гонок
    async with _get_chat_lock(chat_id):
        # Получение или создание сессии
        support_session = await crud.get_or_create_active_session(chat_id=chat_id)

        # Если сессию ведёт специалист — сохраняем сырое сообщение без LLM-обработки
        if support_session.assistant_type == AssistantType.human:
            await _save_human_session_message(support_session, message)
            logger.info("Сессию ведёт специалист, сообщение сохранено")
            return

        logger.info("Сессию ведёт AI-помощник")

        try:
            await _process_ai_message(
                chat_type=chat_type,
                support_session=support_session,
                bot=bot,
                message=message,
                followup_tasks=followup_tasks,
                operator_id=operator_id,
                tech_support_account_id=tech_support_account_id,
            )
        except Exception:
            # Любой сбой пайплайна (граф, таймаут LLM/прокси, медиа, отправка) не должен
            # оставлять клиента без ответа: логируем и переводим на специалиста.
            logger.exception(
                "Ошибка обработки сообщения клиента (chat_id=%s), фолбэк на специалиста",
                chat_id,
            )
            # Сессия могла смениться при intent_changed — берём актуальную активную.
            current_session = await crud.get_active_session(chat_id) or support_session
            await _switch_to_human_specialist(
                chat_type=chat_type,
                support_session=current_session,
                bot=bot,
                message=message,
                operator_id=operator_id,
                tech_support_account_id=tech_support_account_id,
            )


async def _process_ai_message(
    chat_type: ChatType,
    support_session: SupportSession,
    bot: Bot,
    message: types.Message,
    followup_tasks: dict[str, asyncio.Task],
    operator_id: str,
    tech_support_account_id: str | None = None,
) -> None:
    """Обработать сообщение в AI-режиме: медиа → сохранение → граф → ответ."""
    # Обработка медиа-контента
    media_data = await _extract_message_content(message, bot)
    message_text_content = media_data["text_content"]

    # Если невозможно распознать текст сообщения — на специалиста
    if message_text_content is None:
        logger.info("Невозможно извлечь текст из сообщения")
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

    # Сохраняем сообщение клиента сразу при входе, чтобы оно не терялось при падении
    # графа. В граф оно передаётся отдельно (last_user_message), поэтому из chat_history
    # исключается по id.
    saved_message = await _save_user_message(support_session, message_text_content, media_data)

    # Внутри графа первым шагом идёт проверка смены интента
    qa_response = await qa_service.get_response(
        user_message=message_text_content,
        session_id=support_session.id,
        exclude_message_id=saved_message.id,
    )

    # Если интент изменился — закрываем текущую сессию, открываем новую и переносим
    # в неё уже сохранённое сообщение, затем получаем ответ заново
    if qa_response.message_type == "intent_changed":
        logger.info("Обнаружена смена темы, создание новой сессии")
        await crud.update_session_status(session_id=support_session.id, status=SupportStatus.end)
        support_session = await crud.create_support_session(chat_id=support_session.chat_id)
        await crud.reassign_message(saved_message.id, support_session.id)
        qa_response = await qa_service.get_response(
            user_message=message_text_content,
            session_id=support_session.id,
            exclude_message_id=saved_message.id,
        )

    # Автоответ + отметка о прочтении (только для личных сообщений)
    if chat_type == ChatType.PRIVATE:
        await _send_auto_reply_if_needed(bot, message, support_session)
        await bot(
            ReadBusinessMessage(
                business_connection_id=message.business_connection_id,
                chat_id=int(support_session.chat_id),
                message_id=message.message_id,
            )
        )

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

async def _extract_message_content(message: types.Message, bot: Bot) -> MediaData:
    """Извлечь контент из сообщения (текст или медиа через LLM)."""
    if has_media_content(message):
        logger.info("Сообщение клиента содержит медиа-контент")
        media_data = await get_media_content(message, bot)
        media_data["text_content"] = await extract_text_from_media(
            media_type=media_data["media_type"],
            content=media_data["content"],
            caption=media_data["caption"],
        )
        return media_data

    logger.info("Сообщение клиента — просто текст")
    return MediaData(text_content=message.text, media_type=None, content=None, caption=None)


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
    media_data: MediaData | None = None,
) -> None:
    """Обработка сообщения, которое невозможно распознать."""
    await _save_user_message(support_session, None, media_data)

    # AI сессия — переключаем на специалиста
    logger.info("Переключение на специалиста: невозможно определить сообщение")
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
        logger.info("Переключение диалога на специалиста")
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
        logger.info("Сообщение не требует ответа")
        return

    # Положительный отклик
    if message_type == "positive_acknowledgement":
        logger.info("Сообщение является положительным откликом")
        await _send_positive_acknowledgement_reply(bot, message, support_session)
        return

    # Ответ из базы знаний или чат
    if message_type in ("knowledge_required", "chat"):
        logger.info("Поиск ответа в базе знаний либо простой чат")
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

    await crud.update_session_assistant_type(session_id=support_session.id, assistant_type=AssistantType.human)

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
    should_send = await chat_flow_service.should_send_auto_reply(chat_id=support_session.chat_id)

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
    should_show_ad = await chat_flow_service.should_show_ad_on_positive_acknowledgement(
        chat_id=support_session.chat_id
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

    if chat_type == ChatType.PRIVATE:
        await bot.send_message(
            chat_id=chat_id,
            text=answer,
            business_connection_id=message.business_connection_id
        )
    else:
        await message.reply(text=answer)

    await chat_flow_service.schedule_followup(
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
    media_data: MediaData | None = None,
) -> Message:
    """Сохранить сообщение клиента в БД (одна запись) и вернуть его."""
    media_type_str = media_data["media_type"] if media_data else None
    msg_type = content_type_to_message_type(media_type_str)

    return await crud.add_message(
        support_session_id=support_session.id,
        content=message_text_content,
        role=MessageRole.user,
        type=msg_type,
    )


async def _save_human_session_message(
    support_session: SupportSession,
    message: types.Message,
) -> None:
    """Сохранить сообщение клиента для human-сессии без LLM-обработки."""
    media_type_str = get_message_media_type(message)
    msg_type = content_type_to_message_type(media_type_str)
    content = message.text or message.caption

    await crud.add_message(
        support_session_id=support_session.id,
        content=content,
        role=MessageRole.user,
        type=msg_type,
    )
