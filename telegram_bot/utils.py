"""Утилиты для работы с Telegram."""
from typing import TypedDict

from aiogram import types, Bot
from aiogram.enums import ContentType

from telegram_bot.database.models import Message
from telegram_bot.enums import ChatType, MessageRole, MessageType


class MediaData(TypedDict):
    """Данные медиа-контента из сообщения."""
    text_content: str | None
    media_type: str | None   # значение ContentType или None
    content: bytes | None
    caption: str | None


# Маппинг ContentType → MessageType для сохранения в БД
_CONTENT_TYPE_TO_MESSAGE_TYPE: dict[str, MessageType] = {
    ContentType.PHOTO.value: MessageType.image,
    ContentType.VIDEO.value: MessageType.video,
    ContentType.ANIMATION.value: MessageType.video,
    ContentType.VIDEO_NOTE.value: MessageType.video,
    ContentType.AUDIO.value: MessageType.audio,
    ContentType.VOICE.value: MessageType.audio,
    ContentType.DOCUMENT.value: MessageType.text,
    ContentType.STICKER.value: MessageType.image,
}


def content_type_to_message_type(media_type: str | None) -> MessageType:
    """Преобразовать ContentType строку в MessageType для записи в БД."""
    if media_type is None:
        return MessageType.text
    return _CONTENT_TYPE_TO_MESSAGE_TYPE.get(media_type, MessageType.text)


def get_message_media_type(message: types.Message) -> str | None:
    """Определить тип медиа без загрузки файла. Возвращает ContentType строку или None."""
    if message.photo:
        return ContentType.PHOTO.value
    if message.video:
        return ContentType.VIDEO.value
    if message.animation:
        return ContentType.ANIMATION.value
    if message.audio:
        return ContentType.AUDIO.value
    if message.voice:
        return ContentType.VOICE.value
    if message.video_note:
        return ContentType.VIDEO_NOTE.value
    if message.document:
        return ContentType.DOCUMENT.value
    if message.sticker:
        return ContentType.STICKER.value
    return None


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


async def get_media_content(message: types.Message, bot: Bot) -> MediaData:
    """Получить медиа-контент из сообщения (включая загрузку файла)."""
    media_type: str | None = None

    if message.photo:
        media_type = ContentType.PHOTO.value
        file_info = await bot.get_file(message.photo[-1].file_id)
    elif message.video:
        media_type = ContentType.VIDEO.value
        file_info = await bot.get_file(message.video.file_id)
    elif message.animation:
        media_type = ContentType.ANIMATION.value
        file_info = await bot.get_file(message.animation.file_id)
    elif message.audio:
        media_type = ContentType.AUDIO.value
        file_info = await bot.get_file(message.audio.file_id)
    elif message.voice:
        media_type = ContentType.VOICE.value
        file_info = await bot.get_file(message.voice.file_id)
    elif message.document:
        media_type = ContentType.DOCUMENT.value
        file_info = await bot.get_file(message.document.file_id)
    else:
        return MediaData(text_content=None, media_type=None, content=None, caption=message.caption)

    file_bytes_data = await bot.download_file(file_info.file_path)
    file_bytes = file_bytes_data.getvalue() if hasattr(file_bytes_data, 'getvalue') else file_bytes_data
    return MediaData(text_content=None, media_type=media_type, content=file_bytes, caption=message.caption)


__all__ = [
    "MediaData",
    "content_type_to_message_type",
    "get_message_media_type",
    "get_chat_id",
    "format_chat_from_message",
    "has_media_content",
    "get_media_content",
]
