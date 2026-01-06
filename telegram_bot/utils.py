"""Утилиты для работы с Telegram сообщениями."""
import sys
from pathlib import Path

# Для запуска файла напрямую (python utils.py)
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import types, Bot
from aiogram.enums import ContentType

from telegram_bot.database.models import Message
from telegram_bot.enums import ChatType, MessageRole


def get_chat_id(message: types.Message, chat_type: ChatType) -> str:
    """
    Сформировать chat_id на основе типа чата.
    
    Для личных сообщений: chat.id
    Для групп: chat.id_user.id (для идентификации конкретного пользователя в группе)
    """
    if chat_type == ChatType.PRIVATE:
        return str(message.chat.id)
    return f"{message.chat.id}_{message.from_user.id}"


def format_chat_from_message(support_session_messages: list[Message]) -> str:
    """Сформировать историю сообщений в текстовом формате."""
    parts = []
    for msg in support_session_messages:
        if msg.role == MessageRole.user:
            parts.append(f"<Пользователь>\n{msg.content}\n</Пользователь>")
        elif msg.role == MessageRole.assistant:
            parts.append(f"<Ассистент>\n{msg.content}\n</Ассистент>")
    return "\n\n".join(parts)


def has_media_content(message: types.Message) -> bool:
    """Проверяет, содержит ли сообщение медиа-контент."""
    return any((
        message.photo, message.video, message.audio, message.voice,
        message.video_note, message.document, message.sticker,
        message.animation, message.location, message.contact, message.poll
    ))


async def get_media_content(message: types.Message, bot: Bot) -> dict:
    """Получить медиа-контент из сообщения."""
    media_type: ContentType
    file_info = None
    
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
    else:
        raise ValueError("Неподдерживаемый тип медиа-контента")
    
    file_bytes = await bot.download_file(file_info.file_path)
    return {
        "media_type": media_type.value,
        "content": file_bytes.getvalue() if hasattr(file_bytes, 'getvalue') else file_bytes,
        "caption": message.caption,
    }


if __name__ == "__main__":
    print(format_chat_from_message(support_session_messages=[]))