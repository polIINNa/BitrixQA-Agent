import os
from pathlib import Path

from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel


class ChatModel(BaseModel):
    """LLM модель с возьможностью чата"""

    provider: str = Field(description='Провайдер модели (openai, gigachat, ...)')
    model: str = Field(description='Название модели')
    kwargs: dict = Field(default_factory=dict, description='Параметры инициализации модели')

    @property
    def chat_model(self) -> BaseChatModel:
        return init_chat_model(model_provider=self.provider, model=self.model, **self.kwargs)


class BitrixQAContext(BaseModel):
    """Контекст графа"""

    model: BaseChatModel = Field(
        description="LLM",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash-lite",
            kwargs={
                "api_key": os.getenv("OPENROUTER_API_KEY"),
                "base_url":"https://openrouter.ai/api/v1",
                "temperature": 0
            }
        ).chat_model)

    pro_model: BaseChatModel = Field(
        description="LLM",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash",
            kwargs={
                "api_key": os.getenv("OPENROUTER_API_KEY"),
                "base_url":"https://openrouter.ai/api/v1",
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
