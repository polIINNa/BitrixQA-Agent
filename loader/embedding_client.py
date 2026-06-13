"""Клиент для построения эмбеддингов через OpenAI."""
import httpx
from langchain_openai import OpenAIEmbeddings

from loader.config import get_config


class EmbeddingClient:
    def __init__(self) -> None:
        config = get_config()
        http_async_client = (
            httpx.AsyncClient(proxy=config.proxy_url)
            if config.proxy_url
            else None
        )
        self._embeddings = OpenAIEmbeddings(
            model=config.embedding_model,
            api_key=config.openai_api_key,
            base_url=config.base_url,
            timeout=60,  # чтобы зависший прокси/OpenRouter не вешал граф и loader
            **({"http_async_client": http_async_client} if http_async_client else {}),
        )

    async def embed(self, text: str) -> list[float]:
        """Построить эмбеддинг для поискового запроса."""
        return await self._embeddings.aembed_query(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Построить эмбеддинги для списка документов."""
        return await self._embeddings.aembed_documents(texts)
