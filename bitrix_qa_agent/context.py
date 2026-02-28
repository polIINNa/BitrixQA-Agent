import os

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import async_sessionmaker
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from loader.embedding_client import EmbeddingClient
from loader.database.connection import AsyncSessionLocal


class ChatModel(BaseModel):
    """LLM модель с возможностью чата"""
    provider: str = Field(description='Провайдер модели (openai, gigachat, ...)')
    model: str = Field(description='Название модели')
    kwargs: dict = Field(default_factory=dict, description='Параметры инициализации модели')

    @property
    def chat_model(self) -> BaseChatModel:
        self.kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")
        self.kwargs["base_url"] = "https://openrouter.ai/api/v1"
        return init_chat_model(model_provider=self.provider, model=self.model, **self.kwargs)


class BitrixQAContext(BaseModel):
    """Контекст QA агента"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lite_model: BaseChatModel = Field(
        description="Определение типа сообщения",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash-lite",
            kwargs={
                "temperature": 0
            }
        ).chat_model)
    pro_model: BaseChatModel = Field(
        description="Определение типа сообщения",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash",
            kwargs={
                "temperature": 0
            }
        ).chat_model)
    embedding_client: EmbeddingClient = Field(
        description="Клиент для построения эмбеддингов поискового запроса",
        default_factory=EmbeddingClient,
    )
    db_session_factory: async_sessionmaker = Field(
        description="Фабрика сессий для подключения к БД статей",
        default_factory=lambda: AsyncSessionLocal,
    )
    vector_search_k: int = Field(
        description="Количество ближайших статей, извлекаемых векторным поиском",
        default=20,
    )
    articles_batch_size: int = Field(
        description="Размер батча для количества статей в одном промпте LLM-отбора",
        default=10,
    )
