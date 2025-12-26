from aiogram import types, Bot
from aiogram.enums import ContentType

from service import get_answer
from telegram_bot.database import crud, models
from telegram_bot.database.models import Message, MessageRole, SupportStatus, AssistantType


def create_chat(support_session_messages: list[Message]) -> str:
    """Сформировать историю сообщений по сообщениям сессии"""
    chat = ""
    for message in support_session_messages:
        if message.role == MessageRole.user:
            chat += f"<Пользователь>\n{message.content}\n</Пользователь>\n\n"
        if message.role == MessageRole.assistant:
            chat += f"<Ассистент>\n{message.content}\n</Ассистент>\n\n"
    return chat


def has_media_content(message: types.Message) -> bool:
    """Проверяет, содержит ли сообщение медиа-контент (не только текст)"""
    return any((
        message.photo, message.video, message.audio, message.voice,
        message.video_note, message.document, message.sticker,
        message.animation, message.location, message.contact, message.poll
    ))


async def get_media_content(message: types.Message, bot: Bot) -> dict:
    """Определяет тип медиа-контента и возвращает его содержимое (как bytes объект)"""
    if message.photo:
        media_type = ContentType.PHOTO
        file_info = await bot.get_file(message.photo[-1].file_id)
    elif message.video:
        media_type = ContentType.VIDEO
        file_info = await bot.get_file(message.video.file_id)
    elif message.animation:
        media_type = ContentType.ANIMATION
        file_info = await bot.get_file(message.animation.file_id)
    elif message.audio:
        media_type = ContentType.AUDIO
        file_info = await bot.get_file(message.audio.file_id)
    elif message.voice:
        media_type = ContentType.VOICE
        file_info = await bot.get_file(message.voice.file_id)
    elif message.document:
        media_type = ContentType.DOCUMENT
        file_info = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    return {
        "media_type": media_type.value,
        "content": file_bytes.getvalue() if hasattr(file_bytes, 'getvalue') else file_bytes,
        "caption": message.caption
    }


async def get_or_create_support_session(chat_id: str) -> models.SupportSession:
    """Получает или создает активную сессию поддержки"""
    chat = await crud.get_or_create_chat(chat_id)
    support_session = await crud.get_active_session(chat.id)
    if not support_session:
        support_session = await crud.create_support_session(chat_id=chat.id)
    return support_session


async def get_chat_history(support_session_messages: list[Message]) -> str | None:
    """Получает историю чата для сессии"""
    if len(support_session_messages) == 1:
        return None
    return create_chat(support_session_messages[:-1])

async def get_agent_answer(
    support_session_messages: list[Message],
    user_message: str
) -> tuple[str, str | None]:
    """Получить ответ от агента"""
    chat_history = await get_chat_history(support_session_messages=support_session_messages)
    answer = await get_answer(chat_history=chat_history, last_user_message=user_message)
    return answer, chat_history
