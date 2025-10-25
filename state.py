import operator
from typing import Annotated

from pydantic import BaseModel, Field


class BitrixQAState(BaseModel):
    """Основное состояние графа"""
    query: str = Field(description="Вопрос пользователя")
    relevant_articles_ids: Annotated[list[str], operator.add] = Field(description="IDs релевантных статей")
    context: str = Field(description="Контекст для ответа на вопрос")
    answer: str = Field(description="Ответ на вопрос")


class GetRelevantArticlesState(BaseModel):
    """Состояние для нахождения релевантных статей из одного батча"""
    articles_metadata: str = Field(description="Метаданные о статьях (номер, тема, проблема")
    query: str = Field(description="Вопрос пользователя")