import logging

from aiogram import types

from telegram_bot.database import crud
from telegram_bot.enums import MessageRole, AssistantType

logger = logging.getLogger(__name__)


async def handle_specialist_message(message: types.Message, chat_id: str) -> None:
    """
    Обработать сообщение специалиста.
    
    Args:
        message: Telegram сообщение от специалиста
        chat_id: идентификатор чата
    """
    support_session = await crud.get_active_session(chat_id=chat_id)
    
    if support_session is None:
        logger.warning(f"Активная сессия не найдена для chat_id={chat_id}")
        return
    
    await crud.add_message(
        support_session_id=support_session.id,
        content=message.text,
        role=MessageRole.assistant,
        assistant_type=AssistantType.human,
    )