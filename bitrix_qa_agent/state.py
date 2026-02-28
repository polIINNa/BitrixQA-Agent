from pydantic import BaseModel, Field


class InputState(BaseModel):
    """Входные данные"""
    chat_history: str = Field(description="История чата", default="")
    last_user_message: str = Field(description="Последнее сообщение пользователя")


class RAGState(BaseModel):
    """Состояние для rag этапа"""
    query: str = Field(description="Вопрос пользователя")
    fetched_articles: list[dict] = Field(
        description="Статьи, найденные векторным поиском. Каждый элемент: {source_article_id, content}",
        default_factory=list,
    )
    relevant_articles_ids: list[str] = Field(description="IDs релевантных статей для текущего запроса.", default_factory=list)
    context: str | None = Field(description="Контекст для ответа на вопрос", default=None)


class BitrixQAState(InputState):
    """Основное состояние графа"""
    user_message_type: str | None = Field(description="Тип сообщения пользователя", default=None)
    answer: str | None = Field(description="Ответ на вопрос", default=None)
