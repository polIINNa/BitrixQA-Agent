from pydantic import BaseModel, Field


class InputState(BaseModel):
    """Входные данные"""
    chat_history: str = Field(description="История чата", default="")
    last_user_message: str = Field(description="Последнее сообщение пользователя")
    intent_check_only: bool = Field(
        description="Режим только проверки интента (без полной обработки)",
        default=False
    )


class RAGState(BaseModel):
    """Состояние для rag этапа"""
    query: str = Field(description="Вопрос пользователя")
    relevant_articles_ids: list[str] = Field(description="IDs релевантных статей для текущего запроса.", default_factory=list)
    context: str | None = Field(description="Контекст для ответа на вопрос", default=None)


class BitrixQAState(InputState):
    """Основное состояние графа"""
    user_message_type: str | None = Field(description="Тип сообщения пользователя", default=None)
    answer: str | None = Field(description="Ответ на вопрос", default=None)
