"""Сервис для работы с QA агентом."""
import logging
from typing import Literal

from pydantic import BaseModel

from telegram_bot.database import crud
from telegram_bot.utils import format_chat_from_message
from bitrix_qa_agent.api import invoke_graph

logger = logging.getLogger(__name__)

# Типы сообщений, возвращаемые QA агентом
MessageType = Literal[
    "negative",
    "no_need_reply",
    "positive_acknowledgement",
    "knowledge_required",
    "chat",
    "intent_changed",
]


class QAResponse(BaseModel):
    """Ответ от QA агента."""
    message_type: MessageType
    answer: str | None = None


async def get_response(
    user_message: str,
    session_id: str,
    exclude_message_id: str | None = None,
) -> QAResponse:
    """
    Получить ответ от QA агента.

    Args:
        user_message: сообщение пользователя
        session_id: ID сессии для получения истории
        exclude_message_id: id сообщения, которое нужно исключить из истории
            (текущее сообщение уже сохранено при входе — в историю графа оно
            передаётся отдельно как last_user_message, а не как часть chat_history)

    Returns:
        QAResponse с типом сообщения и ответом
    """
    session_messages = await crud.get_all_messages(session_id)
    if exclude_message_id is not None:
        session_messages = [m for m in session_messages if m.id != exclude_message_id]
    chat_history = format_chat_from_message(support_session_messages=session_messages)

    result = await invoke_graph(
        chat_history=chat_history,
        last_user_message=user_message,
    )

    logger.info(f"QA агент вернул тип: {result['message_type']}")
    return QAResponse(
        message_type=result["message_type"],
        answer=result.get("answer"),
    )
