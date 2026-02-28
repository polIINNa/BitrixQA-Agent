"""Клиент для построения эмбеддингов через OpenAI."""
from langchain_openai import OpenAIEmbeddings

from loader.config import get_config


class EmbeddingClient:
    def __init__(self) -> None:
        config = get_config()
        self._embeddings = OpenAIEmbeddings(
            model=config.embedding_model,
            api_key=config.openai_api_key,
            base_url=config.base_url,
        )

    async def embed(self, text: str) -> list[float]:
        """Построить эмбеддинг для поискового запроса."""
        return await self._embeddings.aembed_query(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Построить эмбеддинги для списка документов."""
        return await self._embeddings.aembed_documents(texts)
