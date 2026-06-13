"""Роутер для групповых сообщений."""
import logging

from aiogram import Bot, types, Router, F

from telegram_bot.config import get_config
from telegram_bot.database import crud
from telegram_bot.enums import ChatType
from telegram_bot.utils import get_chat_id
from telegram_bot.message_handlers.client import handle_client_message
from telegram_bot.message_handlers.specialist import handle_specialist_message

logger = logging.getLogger(__name__)

config = get_config()

# Роутер для групповых сообщений
group_router = Router(name="group")


@group_router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(
    message: types.Message,
    bot: Bot,
):
    """Обработка сообщений в группе."""
    # Проверка упоминания бота
    if await _handle_bot_mention(message, bot):
        return

    # Обработка ответа специалиста
    if await _handle_specialist_reply(message):
        return

    # Обработка ответа клиента на сообщение специалиста
    await _handle_client_reply_to_specialist(message, bot)


async def _handle_bot_mention(
    message: types.Message,
    bot: Bot,
) -> bool:
    """Обработка упоминания бота в сообщении. Возвращает True если обработано."""
    if not message.entities:
        return False

    for entity in message.entities:
        if entity.type != "mention":
            continue

        mentioned_text = entity.extract_from(message.text)
        if mentioned_text.lower() == f"{config.bot_username}".lower():
            logger.info("Упоминание бота в группе")
            await message.reply("Уже обрабатываю запрос!")
            chat_id = get_chat_id(message, ChatType.GROUP)

            user_username = message.from_user.username if message.from_user else None
            await crud.get_or_create_chat(chat_id=chat_id, username=user_username, chat_type=ChatType.GROUP)

            await handle_client_message(
                chat_type=ChatType.GROUP,
                chat_id=chat_id,
                bot=bot,
                message=message,
                operator_id=config.operator_id,
            )
            return True

    return False


async def _handle_specialist_reply(message: types.Message) -> bool:
    """Обработка ответа специалиста. Возвращает True если обработано."""
    if str(message.from_user.id) != config.operator_id or not message.reply_to_message:
        return False

    logger.info("Обработка сообщения от специалиста в группе")
    client_message = message.reply_to_message
    chat_id = get_chat_id(client_message, ChatType.GROUP)
    await handle_specialist_message(
        chat_id=chat_id,
        message=message,
    )
    return True


async def _handle_client_reply_to_specialist(
    message: types.Message,
    bot: Bot,
) -> None:
    """Обработка ответа клиента на сообщение специалиста."""
    is_client = str(message.from_user.id) != config.operator_id
    is_human = not message.from_user.is_bot
    has_reply = message.reply_to_message is not None

    if not (is_client and is_human and has_reply):
        return

    replied_message = message.reply_to_message
    if str(replied_message.from_user.id) == config.operator_id:
        logger.info("Обработка ответа клиента на сообщение специалиста в группе")
        chat_id = get_chat_id(message, ChatType.GROUP)

        user_username = message.from_user.username if message.from_user else None
        await crud.get_or_create_chat(chat_id=chat_id, username=user_username, chat_type=ChatType.GROUP)

        await handle_client_message(
            chat_type=ChatType.GROUP,
            chat_id=chat_id,
            bot=bot,
            message=message,
            operator_id=config.operator_id,
        )
