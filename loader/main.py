"""Точка входа loader сервиса. Запускается как cron-задача (раз в неделю после парсинга)."""
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from loader.database.connection import AsyncSessionLocal
from loader.dialogue_reader import read_dialogues_from_excel
from loader.embedding_client import EmbeddingClient
from loader.service import run, run_dialogues

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_DIALOGUE_EXCEL_PATH = Path(__file__).parent.parent / "база_знаний_диалоги.xlsx"


async def main() -> None:
    logger.info("Loader стартовал")

    embedding_client = EmbeddingClient()

    async with AsyncSessionLocal() as session:
        await run(session, embedding_client)

    dialogue_items = read_dialogues_from_excel(str(_DIALOGUE_EXCEL_PATH))
    async with AsyncSessionLocal() as session:
        await run_dialogues(session, embedding_client, dialogue_items)

    logger.info("Loader завершил работу")


if __name__ == "__main__":
    asyncio.run(main())
