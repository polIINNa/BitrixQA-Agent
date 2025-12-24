import os
import asyncio
import logging
import re

from dotenv import load_dotenv
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties

from service import get_answer, check_support_session_end
from telegram_bot.constants import CHECK_USER_MESSAGE, NEED_HUMAN_MESSAGE_WITH_GREETINGS, NEED_HUMAN_MESSAGE
from telegram_bot.database import crud
from telegram_bot.database.models import MessageRole, MessageType, AssistantType, SupportSession, Message, SupportStatus
from telegram_bot.utils import get_or_create_support_session, has_media_content, get_media_info, get_chat_history, \
    create_chat

logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.environ["TELEGRAM_API_TOKEN_TEST"]
OPERATOR_ID = os.environ["OPERATOR_ID_TEST"]

bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

BOT_USERNAME = "bitirix_qa_test_bot"

def clean_message_from_mention(message: str) -> str:
    """Очистка сообщения от упоминания бота"""
    return re.sub(fr'@\w{3}\b\s*[,\.!?;:]*', '', message)


@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message):
    """Обработчик сообщений в группе (точка входа)"""
    if message.entities:
        print("Обработка сообщения клиента с упоминанием")
        for entity in message.entities:
            if entity.type == "mention":
                mentioned_text = entity.extract_from(message.text)
                if mentioned_text.lower() == f"@{BOT_USERNAME}".lower():
                    print("Упоминание бота")
                    await message.reply(f"Уже обрабатываю запрос!")
                    await handle_group_client_message(message)
                    break
    if str(message.from_user.id) == OPERATOR_ID and message.reply_to_message:
        print("Обработка сообщения от специалиста")
        # Получаем сообщение, на которое ответили (сообщение клиента)
        client_message = message.reply_to_message
        chat_id = f"{client_message.chat.id}_{client_message.from_user.id}"
        await handle_group_specialist_message(
            message=message,
            chat_id=chat_id,
        )
        return
    if str(message.from_user.id) != OPERATOR_ID and message.reply_to_message and not message.from_user.is_bot:
        print("Обработка сообщений от клиента, если оно является реплаем")
        replied_message = message.reply_to_message
        # проверка, что сообщение, на которое ответили - от специалиста
        if str(replied_message.from_user.id) == OPERATOR_ID:
            await handle_group_client_message(message)


followup_tasks: dict[str, asyncio.Task] = {}
async def schedule_followup(support_session_id: str, message: types.Message) -> None:
    """Отправить сообщение с вопросом 'все ли клиенту понятно'"""
    await asyncio.sleep(1800)
    await crud.add_message(
        support_session_id=support_session_id,
        content=CHECK_USER_MESSAGE,
        role=MessageRole.system
    )
    await message.reply(CHECK_USER_MESSAGE)


async def switch_to_human_specialist(
    support_session: SupportSession,
    message: types.Message,
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
        chat_id=OPERATOR_ID,
        text=f"Бот перевел поддержку на специалиста, сообщение клиента: {message.get_url()}"
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
    message: types.Message,
    answer: str,
    chat_id: str
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



async def handle_group_client_message(message: types.Message):
    """Обработать сообщение клиента в группе"""
    chat_id = f"{message.chat.id}_{message.from_user.id}"
    support_session = await get_or_create_support_session(chat_id=chat_id)
    task = followup_tasks.pop(chat_id, None)
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
            role=MessageRole.user,
            type=media_type
        )
    else:
        await crud.add_message(
            support_session_id=support_session.id,
            content=message.text,
            role=MessageRole.user,
            type=MessageType.text
        )
    # выход, если сессию ведет оператор
    if support_session.assistant_type == AssistantType.human:
        print("Отвечает специалист, выход из функции")
        return
    # получение и отправка сообщения клиенту
    if has_media_content_flag:
        print("Переключение на специалиста из-за наличия медиа-контента")
        await switch_to_human_specialist(
            support_session=support_session,
            message=message,
        )
        return
    print("Попытка ответить от бота")
    session_messages = await crud.get_all_messages(support_session.id)
    answer, chat_history = await get_agent_answer(
        support_session_messages=session_messages,
        user_message=clean_message_from_mention(message.text)
    )
    if answer == "need_human":
        print("Переключение диалога на специалиста")
        await switch_to_human_specialist(
            support_session=support_session,
            message=message,
        )
        return
    else:
        print("Отвечает бот")
        await process_agent_response(
            support_session=support_session,
            message=message,
            answer=answer,
            chat_id=chat_id,
        )


async def handle_group_specialist_message(message: types.Message, chat_id: str):
    """Обработать сообщение специалиста"""
    support_session = await crud.get_active_session(chat_id=chat_id)
    await crud.add_message(
        support_session_id=support_session.id,
        content=message.text,
        role=MessageRole.assistant,
        assistant_type=AssistantType.human
    )
    # Проверка на окончание диалога
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    chat = create_chat(support_session_messages)
    is_support_session_end = await check_support_session_end(chat=chat)
    if is_support_session_end:
        await crud.update_session_status(
            session_id=support_session.id,
            status=SupportStatus.end
        )


# Основная функция
async def main() -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())