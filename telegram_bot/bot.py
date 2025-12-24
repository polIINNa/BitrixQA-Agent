import os
import sys
import asyncio
import logging

from dotenv import load_dotenv
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties

from telegram_bot import group_messages, privet_messages, handle_specialist_messages


load_dotenv()

TOKEN = os.getenv("TELEGRAM_API_TOKEN")
TECH_SUPPORT_ACCOUNT_ID = os.getenv("TECH_SUPPORT_ACCOUNT_ID")
OPERATOR_ID = os.getenv("OPERATOR_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME")

dp = Dispatcher()
bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

followup_tasks = {}

@dp.business_message()
async def handle_business_message(message: types.Message):
    """Обработка сообщений в бизнес-аккаунте"""
    print("Обработка сообщений в бизнес-аккаунте")
    print(message.text)
    if str(message.from_user.id) == TECH_SUPPORT_ACCOUNT_ID:
        print("Обработка сообщения специалиста")
        await handle_specialist_messages.handle_group_specialist_message(
            chat_id=str(message.chat.id),
            message=message,
        )
    else:
        print("Обработка сообщения пользователя")
        await privet_messages.handle_client_message(
            bot=bot,
            message=message,
            followup_tasks=followup_tasks,
            operator_id=OPERATOR_ID,
            tech_support_account_id=TECH_SUPPORT_ACCOUNT_ID
        )

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message):
    """Обработка сообщений в группе"""
    print("Обработка сообщений в группе")
    print(message.text)
    if message.entities:
        print("Обработка сообщения клиента с упоминанием")
        for entity in message.entities:
            if entity.type == "mention":
                mentioned_text = entity.extract_from(message.text)
                if mentioned_text.lower() == f"@{BOT_USERNAME}".lower():
                    print("Упоминание бота")
                    await message.reply(f"Уже обрабатываю запрос!")
                    await group_messages.handle_group_client_message(
                        bot=bot,
                        message=message,
                        followup_tasks=followup_tasks,
                        operator_id=OPERATOR_ID,
                    )
                    break
    if str(message.from_user.id) == OPERATOR_ID and message.reply_to_message:
        print("Обработка сообщения от специалиста")
        # Получаем сообщение, на которое ответили (сообщение клиента)
        client_message = message.reply_to_message
        chat_id = f"{client_message.chat.id}_{client_message.from_user.id}"
        await handle_specialist_messages.handle_group_specialist_message(
            message=message,
            chat_id=chat_id,
        )
        return
    if str(message.from_user.id) != OPERATOR_ID and message.reply_to_message and not message.from_user.is_bot:
        print("Обработка сообщений от клиента, если оно является реплаем")
        replied_message = message.reply_to_message
        # проверка, что сообщение, на которое ответили - от специалиста
        if str(replied_message.from_user.id) == OPERATOR_ID:
            await group_messages.handle_group_client_message(
                bot=bot,
                message=message,
                followup_tasks=followup_tasks,
                operator_id=OPERATOR_ID,
            )


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())