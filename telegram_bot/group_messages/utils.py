import asyncio
import re

from aiogram import types, Bot

from service import check_support_session_end
from telegram_bot.constants import NEED_HUMAN_MESSAGE_WITH_GREETINGS, NEED_HUMAN_MESSAGE, CHECK_USER_MESSAGE
from telegram_bot.database import crud
from telegram_bot.database.models import SupportSession, MessageRole, AssistantType, SupportStatus
from telegram_bot.utils import create_chat


async def switch_to_human_specialist(
    bot: Bot,
    support_session: SupportSession,
    message: types.Message,
    operator_id: str
) -> None:
    """Переключить сессию на специалиста и отправляет сообщение пользователю"""
    # проверяем, первое ли это сообщение клиента
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    user_messages = 0
    for support_session_message in support_session_messages:
        if support_session_message.role == MessageRole.user:
            user_messages += 1
    if user_messages == 1:
        text = NEED_HUMAN_MESSAGE_WITH_GREETINGS
    else:
        text = NEED_HUMAN_MESSAGE
    # обновление типа ассистента на human и отправка сообщения
    await crud.update_session_assistant_type(
        session_id=support_session.id,
        assistant_type=AssistantType.human
    )
    await message.reply(text=text)
    # отправка уведомления специалисту
    await bot.send_message(
        chat_id=operator_id,
        text=f"Бот перевел поддержку на специалиста, сообщение клиента ГРУППА: {message.get_url()}"
    )


def clean_message_from_mention(message: str) -> str:
    """Очистка сообщения от упоминания бота"""
    return re.sub(fr'@\w{3}\b\s*[,\.!?;:]*', '', message)


async def schedule_followup(support_session_id: str, message: types.Message) -> None:
    """Отправить сообщение с вопросом 'все ли клиенту понятно'"""
    await asyncio.sleep(1800)
    await crud.add_message(
        support_session_id=support_session_id,
        content=CHECK_USER_MESSAGE,
        role=MessageRole.system
    )
    await message.reply(CHECK_USER_MESSAGE)


async def process_agent_response(
    support_session: SupportSession,
    message: types.Message,
    answer: str,
    chat_id: str,
    followup_tasks: dict[str, asyncio.Task],
) -> None:
    """Обработка ответа агента: сохранение в БД, установка таймера, отправка сообщения клиенту"""
    await crud.add_message(
        support_session_id=support_session.id,
        content=answer,
        role=MessageRole.assistant,
        assistant_type=AssistantType.ai
    )
    # удаление старой задачи с сообщением с напоминанием
    old_task = followup_tasks.pop(chat_id, None)
    if old_task:
        old_task.cancel()
    # Проверка на окончание диалога
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    chat = create_chat(support_session_messages=support_session_messages)
    is_support_session_end = await check_support_session_end(chat=chat)
    if is_support_session_end:
        await crud.update_session_status(
            session_id=support_session.id,
            status=SupportStatus.end
        )
    else:
        # установка таймера 30 мин для отправки уведомления клиенту
        task = asyncio.create_task(schedule_followup(
            support_session_id=support_session.id,
            message=message,
        ))
        followup_tasks[chat_id] = task
    # Отправка ответа пользователю
    await message.reply(text=answer)