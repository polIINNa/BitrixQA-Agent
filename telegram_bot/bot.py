import os
import sys
import asyncio
import logging

from dotenv import load_dotenv
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties

from telegram_bot.database import crud, models
from telegram_bot.utils import create_chat_history
from telegram_bot.constants import NEED_HUMAN_MESSAGE
from service import get_answer, check_support_session_end, get_answer_test


load_dotenv()
TOKEN = os.environ["TELEGRAM_API_TOKEN"]

dp = Dispatcher()
bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


@dp.business_message()
async def handle_business_message(message: types.Message):
    """Обработка сообщений"""
    if message.from_user.id == os.environ["ADMIN_USER_ID"]:
        print("Обработка сообщения специалиста")
        await handle_specialist_message(message=message)
    else:
        print("Обработка сообщения пользователя")
        await handle_client_message(message=message)


async def handle_client_message(message: types.Message):
    """Обработка сообщений от пользователя"""
    print(f"ID чата: {message.chat.id}.\nСообщение пользователя: {message.text}")
    # получение чата и сессии поддержки
    print("Получение или создание чата")
    chat = await crud.get_or_create_chat(message.chat.id)
    print("Получение или создание активной сессии")
    support_session = await crud.get_active_session(chat.id)
    if not support_session:
        support_session = await crud.create_support_session(chat_id=chat.id)
    await crud.add_message(
        support_session_id=support_session.id,
        content=message.text,
        role=models.MessageRole.user
    )
    # получение ответа пользователю
    if support_session.assistant_type == models.AssistantType.human:
        print(f"Отвечает специалист, выход из функции")
        return
    print("Попытка ответить от бота")
    messages = await crud.get_all_messages(support_session_id=support_session.id)
    if len(messages) == 1:
        chat_history = None
    else:
        chat_history = create_chat_history(messages[:-1])
    # answer = await get_answer(chat_history=chat_history, last_user_message=message.text)
    answer = await get_answer_test(chat_history=chat_history, last_user_message=message.text)
    if answer == "need_human":
        print("Переключение диалога на специалиста")
        await crud.update_session_assistant_type(
            session_id=support_session.id,
            assistant_type=models.AssistantType.human
        )
        # TODO: сообщение с тем, что позвоните специалисту, целевое - отправка уведомления специалисту
        await bot.send_message(
            chat_id=message.chat.id,
            text=NEED_HUMAN_MESSAGE,
            business_connection_id=message.business_connection_id
        )
    else:
        print("Отвечает бот")
        # сохранение сообщения
        await crud.add_message(
            support_session_id=support_session.id,
            content=answer,
            role=models.MessageRole.assistant,
            assistant_type=models.AssistantType.ai
        )
        # проверка на окончание диалога
        chat = f"{chat_history}\nАссистент: {answer}"
        is_support_session_end = await check_support_session_end(chat=chat)
        if is_support_session_end:
            await crud.update_session_status(
                session_id=support_session.id,
                status=models.SupportStatus.end
            )
        # отправка ответа пользователю
        await bot.send_message(
            chat_id=message.chat.id,
            text=answer,
            business_connection_id=message.business_connection_id
        )


async def handle_specialist_message(message: types.Message):
    """Обработка сообщений от специалиста"""
    support_session = await crud.get_active_session(message.chat.id)
    await crud.add_message(
        support_session_id=support_session.id,
        content=message.text,
        role=models.MessageRole.assistant,
        assistant_type=models.AssistantType.human
    )
    messages = await crud.get_all_messages(support_session_id=support_session.id)
    chat = create_chat_history(messages)
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