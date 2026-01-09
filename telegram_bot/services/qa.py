"""Сервис для работы с QA агентом."""
from typing import Literal

from pydantic import BaseModel

from telegram_bot.database import crud
from telegram_bot.utils import format_chat_from_message
from bitrix_qa_agent.api import invoke_graph


# Типы сообщений, возвращаемые QA агентом
MessageType = Literal[
    "negative",
    "no_need_reply", 
    "positive_acknowledgement",
    "knowledge_required",
    "chat",
    "intent_changed",
    "no_intent_change",
]


class QAResponse(BaseModel):
    """Ответ от QA агента."""
    message_type: MessageType
    answer: str | None = None


async def get_response(
    user_message: str,
    session_id: str,
    intent_check_only: bool = False,
) -> QAResponse:
    """
    Получить ответ от QA агента.
    
    Args:
        user_message: сообщение пользователя
        session_id: ID сессии для получения истории
        intent_check_only: только проверка смены интента
        
    Returns:
        QAResponse с типом сообщения и ответом
    """
    session_messages = await crud.get_all_messages(session_id)
    chat_history = format_chat_from_message(support_session_messages=session_messages)
    
    result = await invoke_graph(
        chat_history=chat_history,
        last_user_message=user_message,
        intent_check_only=intent_check_only,
    )
    
    return QAResponse(
        message_type=result["message_type"],
        answer=result.get("answer"),
    )


async def check_intent_change(session_id: str, user_message: str) -> bool:
    """
    Проверить, изменился ли интент в сообщении.
    
    Args:
        session_id: ID сессии
        user_message: сообщение пользователя
        
    Returns:
        True если интент изменился
    """
    response = await get_response(
        user_message=user_message,
        session_id=session_id,
        intent_check_only=True,
    )
    print(f"Проверка интента: {response.message_type}")
    return response.message_type == "intent_changed"
