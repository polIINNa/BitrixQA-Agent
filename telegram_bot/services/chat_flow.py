"""Логика ведения диалога с клиентом: условия отправки сообщений и напоминания."""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, types

from telegram_bot.database import crud
from telegram_bot.database.models import Message
from telegram_bot.constants import (
    AUTO_REPLY,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD,
    CHECK_USER_MESSAGE,
)
from telegram_bot.enums import ChatType, MessageRole

logger = logging.getLogger(__name__)


# =============================================================================
# Условия отправки сообщений
# =============================================================================

async def should_send_auto_reply(chat_id: str) -> bool:
    """Определяет, нужно ли отправить автоответ."""
    all_messages = await crud.get_all_messages_by_chat_id(chat_id)
    
    # Если AUTO_REPLY ещё не отправлялся в этом чате
    if not any(m.content == AUTO_REPLY for m in all_messages):
        return True
    
    # Если с предыдущего сообщения прошло больше 14 дней
    previous_message = _get_previous_user_message(all_messages)
    if previous_message is None:
        return True
    
    return _is_message_older_than_days(previous_message, days=14)


async def should_show_ad_on_positive_acknowledgement(chat_id: str) -> bool:
    """Определяет, показывать ли рекламу при положительном отклике."""
    all_messages = await crud.get_all_messages_by_chat_id(chat_id)
    
    # Если реклама ещё не показывалась в этом чате
    if not any(m.content == POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD for m in all_messages):
        return True
    
    # Если с предыдущего сообщения прошло больше 10 дней
    previous_message = _get_previous_user_message(all_messages)
    if previous_message is None:
        return True
    
    return _is_message_older_than_days(previous_message, days=10)


# =============================================================================
# Напоминания (followup)
# =============================================================================

FOLLOWUP_DELAY_SECONDS = 1800  # 30 минут


async def schedule_followup(
    chat_type: ChatType,
    message: types.Message,
    support_session_id: str,
    followup_tasks: dict[str, asyncio.Task],
    bot: Bot | None = None,
    chat_id: str | None = None,
) -> None:
    """
    Запланировать отправку напоминания через 30 минут.
    
    Args:
        chat_type: тип чата
        message: исходное сообщение
        support_session_id: ID сессии
        followup_tasks: словарь активных задач
        bot: бот (для личных сообщений)
        chat_id: ID чата (для личных сообщений)
    """
    # Удаление старой задачи
    if old_task := followup_tasks.pop(chat_id, None):
        old_task.cancel()
    
    # Создание новой задачи
    task = asyncio.create_task(
        _send_followup(
            chat_type=chat_type,
            message=message,
            support_session_id=support_session_id,
            bot=bot,
            chat_id=chat_id,
        )
    )
    followup_tasks[chat_id] = task


def cancel_followup(chat_id: str, followup_tasks: dict[str, asyncio.Task]) -> None:
    """Отменить запланированное напоминание."""
    if task := followup_tasks.pop(chat_id, None):
        task.cancel()


# =============================================================================
# Вспомогательные функции
# =============================================================================

def _get_previous_user_message(messages: list[Message]) -> Message | None:
    """Получить предпоследнее сообщение клиента (до текущего)."""
    user_messages = [m for m in messages if m.role == MessageRole.user]
    if len(user_messages) < 2:
        return None
    return user_messages[-2]


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


async def _send_followup(
    chat_type: ChatType,
    message: types.Message,
    support_session_id: str,
    bot: Bot | None = None,
    chat_id: str | None = None,
) -> None:
    """Отправить напоминание после задержки."""
    await asyncio.sleep(FOLLOWUP_DELAY_SECONDS)
    
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

