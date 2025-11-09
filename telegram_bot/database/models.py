from sqlalchemy import (
    Column, Integer, ForeignKey, Enum, Text,
    TIMESTAMP, func
)
from sqlalchemy.orm import relationship
import enum

from telegram_bot.database.config import Base


class SupportStatus(str, enum.Enum):
    end = "end"
    process = "process"


class MessageType(str, enum.Enum):
    text = "text"
    image = "image"
    audio = "audio"
    video = "video"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class AssistantType(str, enum.Enum):
    ai = "ai"
    human = "human"


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)

    sessions = relationship("SupportSession", back_populates="chat", cascade="all, delete-orphan")


class SupportSession(Base):
    __tablename__ = "support_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)

    status = Column(Enum(SupportStatus, native_enum=False), default=SupportStatus.process, nullable=False)
    assistant_type = Column(Enum(AssistantType, native_enum=False), default=AssistantType.ai, nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now())
    edited_at = Column(TIMESTAMP, nullable=True)
    closed_at = Column(TIMESTAMP, nullable=True)

    chat = relationship("Chat", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    support_session_id = Column(Integer, ForeignKey("support_session.id"), nullable=False)

    content = Column(Text, nullable=False)
    type = Column(Enum(MessageType, native_enum=False), nullable=False)
    role = Column(Enum(MessageRole, native_enum=False), nullable=False)
    assistant_type = Column(Enum(AssistantType, native_enum=False), nullable=True)

    session = relationship("SupportSession", back_populates="messages")
