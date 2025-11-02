import operator
from typing import Annotated
from pydantic import BaseModel, Field

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class InputState(BaseModel):
    """Входные данные"""
    query: str = Field(description="Вопрос пользователя")
    messages: Annotated[list[AnyMessage], add_messages] = Field(description="История сообщения ЧАТА")


class RAGState(BaseModel):
    """Состояние для rag этапа"""
    query: str = Field(description="Вопрос пользователя")
    relevant_articles_ids: list[str] = Field(description="IDs релевантных статей для текущего запроса.", default_factory=list)
    context: str | None = Field(description="Контекст для ответа на вопрос", default=None)


class BitrixQAState(InputState):
    """Основное состояние графа"""
    user_message_type: str | None = Field(description="Тип сообщения пользователя", default=None)
    answer: str | None = Field(description="Ответ на вопрос", default=None)
