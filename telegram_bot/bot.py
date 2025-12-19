import os
import sys
import asyncio
import logging

from dotenv import load_dotenv
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.methods.read_business_message import ReadBusinessMessage

from telegram_bot.database import crud, models
from telegram_bot.database.models import (
    Message, MessageType, MessageRole, AssistantType, SupportSession, SupportStatus
)
from telegram_bot.utils import (
    create_chat,
    has_media_content,
    get_media_info,
    get_or_create_support_session,
    get_chat_history,
    should_send_auto_reply
)
from service import get_answer, check_support_session_end
from telegram_bot.constants import NEED_HUMAN_MESSAGE, AUTO_REPLY, CHECK_USER_MESSAGE, NEED_HUMAN_MESSAGE_WITH_GREETINGS


load_dotenv()
TOKEN = os.environ["TELEGRAM_API_TOKEN_TEST"]
TECH_SUPPORT_ID = os.environ["TECH_SUPPORT_ID"]
OPERATOR_ID = os.environ["OPERATOR_ID_TEST"]

dp = Dispatcher()
bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


@dp.business_message()
async def handle_business_message(message: types.Message):
    """Обработка сообщений"""
    print(message.text)
    if message.from_user.id == int(TECH_SUPPORT_ID):
        print("Обработка сообщения специалиста")
        await handle_specialist_message(message=message)
    else:
        print("Обработка сообщения пользователя")
        await handle_client_message(message=message)


followup_tasks: dict[str, asyncio.Task] = {}
async def schedule_followup(chat_id: str, business_connection_id: str, support_session_id: str) -> None:
    """Отправить сообщение с вопросом 'все ли клиенту понятно'"""
    await asyncio.sleep(1800)
    await crud.add_message(
        support_session_id=support_session_id,
        content=CHECK_USER_MESSAGE,
        role=MessageRole.system
    )
    await bot.send_message(
        chat_id=chat_id,
        text=CHECK_USER_MESSAGE,
        business_connection_id=business_connection_id
    )

async def switch_to_human_specialist(
    support_session: SupportSession,
    chat_id: str,
    username: str,
    business_connection_id: str | None = None
) -> None:
    """Переключить сессию на специалиста и отправляет сообщение пользователю"""
    # проверяем, первое ли это сообщение клиента
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    user_messages = 0
    for message in support_session_messages:
        if message.role == MessageRole.user:
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
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        business_connection_id=business_connection_id
    )
    # отправка уведомления специалисту
    chat_link = f"https://t.me/{username}"
    await bot.send_message(
        chat_id=OPERATOR_ID,
        text=f"Бот перевел поддержку на специалиста"
    )
    await bot.send_message(
        chat_id=TECH_SUPPORT_ID,
        text=f"Ссылка на чат для специалиста: {chat_link}"
    )


async def get_agent_answer(
    support_session_messages: list[Message],
    user_message: str
) -> tuple[str, str | None]:
    """Получить ответ от агента"""
    chat_history = await get_chat_history(support_session_messages=support_session_messages)
    answer = await get_answer(chat_history=chat_history, last_user_message=user_message)
    return answer, chat_history


async def process_agent_response(
    support_session: SupportSession,
    answer: str,
    chat_id: str,
    business_connection_id: str | None = None
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
            chat_id=chat_id, business_connection_id=business_connection_id, support_session_id=support_session.id
        ))
        followup_tasks[chat_id] = task
    # Отправка ответа пользователю
    await bot.send_message(
        chat_id=chat_id,
        text=answer,
        business_connection_id=business_connection_id
    )


async def handle_client_message(message: types.Message):
    """Обработчик сообщений от пользователя"""
    support_session = await get_or_create_support_session(str(message.chat.id))
    # отключение отправки сообщения через 30 минут от бота
    task = followup_tasks.pop(str(message.chat.id), None)
    if task:
        task.cancel()
    # сохранение сообщения клиента в базе
    has_media_content_flag = False
    if has_media_content(message):
        print("Обнаружен медиа-контент, переключение на специалиста")
        has_media_content_flag  = True
        media_type, content = get_media_info(message)
        await crud.add_message(
            support_session_id=support_session.id,
            content=content,
            role=models.MessageRole.user,
            type=media_type
        )
    else:
        message_text = message.text or ""
        await crud.add_message(
            support_session_id=support_session.id,
            content=message_text,
            role=models.MessageRole.user,
            type=MessageType.text
        )
    # выход, если перевод на оператора
    if support_session.assistant_type == AssistantType.human:
        print("Отвечает специалист, выход из функции")
        return
    # чтение сообщения клиента
    await bot(
        ReadBusinessMessage(
            business_connection_id=message.business_connection_id,
            chat_id=message.chat.id,
            message_id=message.message_id
        )
    )
    # проверка на необходимость отправки сообщения-автоответчика
    should_send_auto_reply_res = await should_send_auto_reply(session_id=support_session.id)
    if should_send_auto_reply_res:
        await bot.send_message(
            chat_id=str(message.chat.id),
            text=AUTO_REPLY,
            business_connection_id=message.business_connection_id
        )
        await crud.add_message(
            support_session_id=support_session.id,
            content=AUTO_REPLY,
            role=models.MessageRole.system
        )
    session_messages = await crud.get_all_messages(support_session.id)
    # получение и отправка сообщения клиенту
    if has_media_content_flag:
        print("Переключение на специалиста из-за наличия медиа-контента")
        await switch_to_human_specialist(
            support_session=support_session,
            chat_id=str(message.chat.id),
            business_connection_id=message.business_connection_id,
            username=message.from_user.username
        )
        return
    print("Попытка ответить от бота")
    answer, chat_history = await get_agent_answer(support_session_messages=session_messages, user_message=message_text)
    if answer == "need_human":
        print("Переключение диалога на специалиста")
        await switch_to_human_specialist(
            support_session=support_session,
            chat_id=str(message.chat.id),
            business_connection_id=message.business_connection_id,
            username=message.from_user.username
        )
        return
    else:
        print("Отвечает бот")
        await process_agent_response(
            support_session=support_session,
            answer=answer,
            chat_id=str(message.chat.id),
            business_connection_id=message.business_connection_id
        )


async def handle_specialist_message(message: types.Message):
    """Обработка сообщений от специалиста"""
    support_session = await crud.get_active_session(str(message.chat.id))
    await crud.add_message(
        support_session_id=support_session.id,
        content=message.text,
        role=models.MessageRole.assistant,
        assistant_type=models.AssistantType.human
    )
    # Проверка на окончание диалога
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    chat = create_chat(support_session_messages)
    is_support_session_end = await check_support_session_end(chat=chat)
    if is_support_session_end:
        await crud.update_session_status(
            session_id=support_session.id,
            status=models.SupportStatus.end
        )


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())