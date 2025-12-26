import os
import httpx

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
        self.kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY_TEST")
        self.kwargs["base_url"] = "https://openrouter.ai/api/v1"
        self.kwargs["http_async_client"] = httpx.AsyncClient(
            proxy=f"http://{os.getenv('PROXY_LOGIN')}:{os.getenv('PROXY_PASSWORD')}@{os.getenv('PROXY_HOST')}:{os.getenv('PROXY_PORT')}"
        )
        return init_chat_model(model_provider=self.provider, model=self.model, **self.kwargs)


class MediaRecognizerContext(BaseModel):
    """Контекст графа"""
    image_recognizer_model: BaseChatModel = Field(
        description="Модель для обработки изображений",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash",
            kwargs={
                "temperature": 0
            }
        ).chat_model)
    image_caption_summarize_model: BaseChatModel = Field(
        description="Модель для суммаризации описания изображения и подписи к изображению",
        default_factory=lambda: ChatModel(
            provider="openai",
            model="google/gemini-2.5-flash",
            kwargs={
                "temperature": 0
            }
        ).chat_model
    )

