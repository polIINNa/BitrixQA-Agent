import sys
import asyncio
import logging

from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties

from telegram_bot import handle_specialist_messages, handle_client_messages
from telegram_bot.config import get_config
from telegram_bot.enums import ChatType
from telegram_bot.utils import get_chat_id


config = get_config()

dp = Dispatcher()
bot = Bot(
    config.token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Хранилище задач для отложенных сообщений (напоминаний)
followup_tasks: dict[str, asyncio.Task] = {}

@dp.business_message()
async def handle_business_message(message: types.Message):
    """Обработка сообщений в бизнес-аккаунте."""
    print(f"Обработка бизнес-сообщения: {message.text}")
    
    chat_id = get_chat_id(message, ChatType.PRIVATE)
    
    if str(message.from_user.id) == config.tech_support_account_id:
        print("Обработка сообщения специалиста")
        await handle_specialist_messages.handle_specialist_message(
            chat_id=chat_id,
            message=message,
        )
    else:
        print("Обработка сообщения пользователя")
        await handle_client_messages.handle_client_message(
            chat_type=ChatType.PRIVATE,
            chat_id=chat_id,
            bot=bot,
            message=message,
            followup_tasks=followup_tasks,
            operator_id=config.operator_id,
            tech_support_account_id=config.tech_support_account_id,
        )

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message):
    """Обработка сообщений в группе."""
    print(f"Обработка группового сообщения: {message.text}")
    
    # Проверка упоминания бота
    if await _handle_bot_mention(message):
        return
    
    # Обработка ответа специалиста
    if await _handle_specialist_reply(message):
        return
    
    # Обработка ответа клиента на сообщение специалиста
    await _handle_client_reply_to_specialist(message)


async def _handle_bot_mention(message: types.Message) -> bool:
    """Обработка упоминания бота в сообщении. Возвращает True если обработано."""
    if not message.entities:
        return False
    
    for entity in message.entities:
        if entity.type != "mention":
            continue
        
        mentioned_text = entity.extract_from(message.text)
        if mentioned_text.lower() == f"{config.bot_username}".lower():
            print("Упоминание бота")
            await message.reply("Уже обрабатываю запрос!")
            chat_id = get_chat_id(message, ChatType.GROUP)
            await handle_client_messages.handle_client_message(
                chat_type=ChatType.GROUP,
                chat_id=chat_id,
                bot=bot,
                message=message,
                followup_tasks=followup_tasks,
                operator_id=config.operator_id,
            )
            return True
    
    return False


async def _handle_specialist_reply(message: types.Message) -> bool:
    """Обработка ответа специалиста. Возвращает True если обработано."""
    if str(message.from_user.id) != config.operator_id or not message.reply_to_message:
        return False
    
    print("Обработка сообщения от специалиста")
    # chat_id формируется по сообщению клиента, на которое отвечает специалист
    client_message = message.reply_to_message
    chat_id = get_chat_id(client_message, ChatType.GROUP)
    await handle_specialist_messages.handle_specialist_message(
        chat_id=chat_id,
        message=message,
    )
    return True


async def _handle_client_reply_to_specialist(message: types.Message) -> None:
    """Обработка ответа клиента на сообщение специалиста."""
    is_client = str(message.from_user.id) != config.operator_id
    is_human = not message.from_user.is_bot
    has_reply = message.reply_to_message is not None
    
    if not (is_client and is_human and has_reply):
        return
    
    replied_message = message.reply_to_message
    if str(replied_message.from_user.id) == config.operator_id:
        print("Обработка ответа клиента на сообщение специалиста")
        chat_id = get_chat_id(message, ChatType.GROUP)
        await handle_client_messages.handle_client_message(
            chat_type=ChatType.GROUP,
            chat_id=chat_id,
            bot=bot,
            message=message,
            followup_tasks=followup_tasks,
            operator_id=config.operator_id,
        )


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())