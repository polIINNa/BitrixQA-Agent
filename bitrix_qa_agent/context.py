import os
import httpx
from pathlib import Path

from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel


class ChatModel(BaseModel):
    """LLM модель с возможностью чата"""
    provider: str = Field(description='Провайдер модели (openai, gigachat, ...)')
    model: str = Field(description='Название модели')
    kwargs: dict = Field(default_factory=dict, description='Параметры инициализации модели')

    @property
    def chat_model(self) -> BaseChatModel:
        self.kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY_TEST")
        self.kwargs["base_url"] = "https://openrouter.ai/api/v1"
        self.kwargs["http_async_client"] = httpx.AsyncClient(
            proxy=f"http://{os.getenv('PROXY_LOGIN')}:{os.getenv('PROXY_PASSWORD')}@{os.getenv('PROXY_HOST')}:{os.getenv('PROXY_PORT')}"
        )
        return init_chat_model(model_provider=self.provider, model=self.model, **self.kwargs)


class BitrixQAContext(BaseModel):
    """Контекст графа"""
    classify_message_model: BaseChatModel = Field(
        description="Определение типа сообщения",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash-lite",
            kwargs={
                "temperature": 0
            }
        ).chat_model)
    prepare_query_model: BaseChatModel = Field(
        description="Определение сутевого вопроса из диалога",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash-lite",
            kwargs={
                "temperature": 0
            }
        ).chat_model)
    get_relevant_articles_model: BaseChatModel = Field(
        description="Выбор релевантных статей",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash-lite",
            kwargs={
                "temperature": 0
            }
        ).chat_model)
    generate_answer_model: BaseChatModel = Field(
        description="Генерация ответа на вопрос",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash-lite",
            kwargs={
                "temperature": 0
            }
        ).chat_model)

    admin_answer_model: BaseChatModel = Field(
        description="Модель для валидации или формирования ответа с учетом tone of voice",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash",
            kwargs={
                "temperature": 0
            }
        ).chat_model)

    articles_metadata_path: Path = Field(
        description="Путь до метаданных статей из документации",
        default_factory=lambda: Path(__file__).parent / "qa_data" / "opensource_articles" / "articles_metadata.json"
    )
    articles_files_path: Path = Field(
        description="Путь до хранилище с файлами со статьями",
        default_factory=lambda: Path(__file__).parent / "qa_data" / "opensource_articles" / "source_content"
    )
    articles_batch_size: int = Field(description="Размер батча для количества статей в одном промпте", default=10)
