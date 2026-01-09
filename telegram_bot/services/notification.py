"""Сервис для работы с уведомлениями и напоминаниями."""
import asyncio

from aiogram import Bot, types

from telegram_bot.database import crud
from telegram_bot.enums import ChatType, MessageRole
from telegram_bot.constants import CHECK_USER_MESSAGE


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


def cancel_followup(chat_id: str, followup_tasks: dict[str, asyncio.Task]) -> None:
    """Отменить запланированное напоминание."""
    if task := followup_tasks.pop(chat_id, None):
        task.cancel()
