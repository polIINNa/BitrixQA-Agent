"""Конфигурация loader сервиса."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class LoaderConfig:
    knowledge_database_url: str
    openai_api_key: str
    base_url: str
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_batch_size: int = 50

    @classmethod
    def from_env(cls) -> "LoaderConfig":
        knowledge_database_url = os.getenv("KNOWLEDGE_DATABASE_URL")
        openai_api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = os.getenv("BASE_URL")

        missing = []
        if not knowledge_database_url:
            missing.append("KNOWLEDGE_DATABASE_URL")
        if not openai_api_key:
            missing.append("OPENROUTER_API_KEY")
        if not base_url:
            missing.append("BASE_URL")
        if missing:
            raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}")

        return cls(
            knowledge_database_url=knowledge_database_url,
            openai_api_key=openai_api_key,
            base_url=base_url,
        )

_config: LoaderConfig | None = None


def get_config() -> LoaderConfig:
    global _config
    if _config is None:
        _config = LoaderConfig.from_env()
    return _config
