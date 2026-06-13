from sqlalchemy import (
    Column, Integer, ForeignKey, Enum, Text, String,
    TIMESTAMP, func
)
from sqlalchemy.orm import relationship

from telegram_bot.database.config import Base
from telegram_bot.enums import SupportStatus, MessageType, MessageRole, AssistantType, ChatType, FollowupStatus


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True)
    username = Column(String, nullable=True, index=True)
    chat_type = Column(Enum(ChatType, native_enum=False), nullable=True)
    sessions = relationship("SupportSession", back_populates="chat", cascade="all, delete-orphan")


class SupportSession(Base):
    __tablename__ = "support_session"

    id = Column(String, primary_key=True)  # формат: <chat_id>_<уникальный сессии>
    chat_id = Column(String, ForeignKey("chats.id"), nullable=False)

    status = Column(Enum(SupportStatus, native_enum=False), default=SupportStatus.process, nullable=False)
    assistant_type = Column(Enum(AssistantType, native_enum=False), default=AssistantType.ai, nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now())
    edited_at = Column(TIMESTAMP, nullable=True)
    closed_at = Column(TIMESTAMP, nullable=True)

    chat = relationship("Chat", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    support_session_id = Column(String, ForeignKey("support_session.id"), nullable=False)

    content = Column(Text, nullable=True)
    created_at_str = Column(String, nullable=True)
    type = Column(Enum(MessageType, native_enum=False), nullable=False)
    role = Column(Enum(MessageRole, native_enum=False), nullable=False)
    assistant_type = Column(Enum(AssistantType, native_enum=False), nullable=True)

    session = relationship("SupportSession", back_populates="messages")


class Followup(Base):
    """Отложенное напоминание клиенту ("всё ли понятно?").

    Раньше жило только в памяти (asyncio.Task) и терялось при рестарте.
    Теперь персистентно: фоновый sweep досылает наступившие записи.
    """
    __tablename__ = "followups"

    id = Column(String, primary_key=True)
    support_session_id = Column(String, ForeignKey("support_session.id"), nullable=False)

    chat_id = Column(String, nullable=False, index=True)        # системный chat_id (для отмены)
    send_chat_id = Column(String, nullable=False)               # telegram chat id для отправки
    business_connection_id = Column(String, nullable=True)      # для личных (бизнес) сообщений
    reply_to_message_id = Column(Integer, nullable=True)        # для ответа в группе
    text = Column(Text, nullable=False)

    scheduled_at = Column(TIMESTAMP, nullable=False, index=True)
    status = Column(Enum(FollowupStatus, native_enum=False), default=FollowupStatus.pending, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
