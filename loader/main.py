"""Точка входа loader сервиса. Запускается как cron-задача (раз в неделю после парсинга)."""
import asyncio
import logging
from dotenv import load_dotenv
load_dotenv()

from loader.database.connection import AsyncSessionLocal
from loader.embedding_client import EmbeddingClient
from loader.service import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Loader стартовал")

    embedding_client = EmbeddingClient()

    async with AsyncSessionLocal() as session:
        await run(session, embedding_client)

    logger.info("Loader завершил работу")


if __name__ == "__main__":
    asyncio.run(main())
