import os
import httpx

from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel


# Таймаут на запрос к LLM (сек) и потолок токенов — чтобы зависший прокси/OpenRouter
# не блокировал обработку, а генерация не уходила в runaway.
MODEL_REQUEST_TIMEOUT = 60
MODEL_MAX_TOKENS = 2048


def _build_proxy_url() -> str | None:
    """Собрать URL прокси из PROXY_*; None, если переменные не заданы полностью."""
    login = os.getenv("PROXY_LOGIN")
    password = os.getenv("PROXY_PASSWORD")
    host = os.getenv("PROXY_HOST")
    port = os.getenv("PROXY_PORT")
    if all([login, password, host, port]):
        return f"http://{login}:{password}@{host}:{port}"
    return None


# Один httpx-клиент на весь процесс (а не на каждое фото — иначе утечка соединений).
_proxy_url = _build_proxy_url()
_http_async_client = httpx.AsyncClient(proxy=_proxy_url) if _proxy_url else None


class ChatModel(BaseModel):
    """LLM модель с возможностью чата"""
    provider: str = Field(description='Провайдер модели (openai, gigachat, ...)')
    model: str = Field(description='Название модели')
    kwargs: dict = Field(default_factory=dict, description='Параметры инициализации модели')

    @property
    def chat_model(self) -> BaseChatModel:
        self.kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")
        self.kwargs["base_url"] = "https://openrouter.ai/api/v1"
        self.kwargs.setdefault("timeout", MODEL_REQUEST_TIMEOUT)
        self.kwargs.setdefault("max_tokens", MODEL_MAX_TOKENS)
        if _http_async_client is not None:
            self.kwargs["http_async_client"] = _http_async_client
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


# Контекст создаётся один раз на процесс (модели + httpx-клиент переиспользуются).
_context: MediaRecognizerContext | None = None


def get_media_recognizer_context() -> MediaRecognizerContext:
    global _context
    if _context is None:
        _context = MediaRecognizerContext()
    return _context
