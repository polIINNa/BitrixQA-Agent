"""SQLAlchemy ORM модели для loader сервиса."""
from __future__ import annotations

from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from loader.database.connection import Base


class ArticleRevision(Base):
    """Версия исходной статьи на момент парсинга."""
    __tablename__ = "article_revision"
    id = Column(Integer, primary_key=True)
    source_article_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    embedding_index = relationship(
        "ArticleEmbeddingIndex",
        back_populates="article_revision",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ArticleEmbeddingIndex(Base):
    """Индекс эмбеддингов статей для RAG-поиска. Заполняется loader сервисом."""
    __tablename__ = 'article_embedding_index'
    id = Column(Integer, primary_key=True)
    article_revision_id = Column(
        Integer,
        ForeignKey("article_revision.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    article_revision = relationship("ArticleRevision", back_populates="embedding_index")


class DialogueKnowledgeItem(Base):
    """Кураторский пример диалога для RAG-поиска. Заполняется loader сервисом."""
    __tablename__ = "dialogue_knowledge_item"
    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False, unique=True)
    answer = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
