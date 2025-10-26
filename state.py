import operator
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class BitrixQAState(BaseModel):
    """Основное состояние графа"""
    query: str = Field(description="Вопрос пользователя")
    user_message_type: str | None = Field(description="Тип сообщения пользователя", default=None)
    relevant_articles_ids: Annotated[list[str], operator.add] = Field(description="IDs релевантных статей")
    context: str | None = Field(description="Контекст для ответа на вопрос", default=None)
    answer: str | None = Field(description="Ответ на вопрос", default=None)

    messages: Annotated[list[AnyMessage], add_messages] = Field(description="История сообщения ЧАТА")


class GetRelevantArticlesState(BaseModel):
    """Состояние для нахождения релевантных статей из одного батча"""
    articles_metadata: str = Field(description="Метаданные о статьях (номер, тема, проблема")
    query: str = Field(description="Вопрос пользователя")