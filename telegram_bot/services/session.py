"""Сервис для работы с сессиями поддержки."""
from telegram_bot.database import crud
from telegram_bot.database.models import SupportSession
from telegram_bot.enums import SupportStatus, AssistantType


async def get_or_create_active_session(chat_id: str) -> SupportSession:
    """
    Получить активную сессию или создать новую.
    
    Args:
        chat_id: идентификатор чата
        
    Returns:
        Активная или новая сессия поддержки
    """
    chat = await crud.get_or_create_chat(chat_id)
    active_session = await crud.get_active_session(chat.id)
    
    if active_session is None:
        print("Нет действующей сессии, создание новой")
        return await crud.create_support_session(chat_id=chat_id)
    
    print("Есть действующая сессия, продолжение")
    return active_session


async def close_session(session_id: str) -> None:
    """Завершить сессию."""
    await crud.update_session_status(session_id=session_id, status=SupportStatus.end)


async def switch_to_human(session_id: str) -> None:
    """Переключить сессию на специалиста."""
    await crud.update_session_assistant_type(
        session_id=session_id,
        assistant_type=AssistantType.human
    )


async def create_new_session(chat_id: str) -> SupportSession:
    """Создать новую сессию."""
    return await crud.create_support_session(chat_id=chat_id)
