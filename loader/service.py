"""Сервис построения эмбеддингов статей."""
import logging
from itertools import islice

from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from sqlalchemy.ext.asyncio import AsyncSession

from loader.config import get_config
from loader.database.repository import (
    get_revisions_needing_embedding,
    delete_embeddings_for_source_article,
    save_embedding,
    upsert_dialogues,
    get_dialogues_needing_embedding,
    save_dialogue_embedding,
)
from loader.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


def _iter_batches(iterable, n):
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _embed_batch(embedding_client: EmbeddingClient, texts: list[str]) -> list[list[float]]:
    return await embedding_client.embed_documents(texts)


async def run_dialogues(
    session: AsyncSession,
    embedding_client: EmbeddingClient,
    items: list[dict],
) -> None:
    """Обработать примеры диалогов: сохранить в БД и построить эмбеддинги."""
    if not items:
        logger.info("Нет примеров диалогов для обработки")
        return

    await upsert_dialogues(session, items)
    await session.commit()

    dialogues = await get_dialogues_needing_embedding(session)

    if not dialogues:
        logger.info("Все примеры диалогов уже имеют эмбеддинги")
        return

    config = get_config()
    logger.info("Найдено примеров диалогов для векторизации: %d", len(dialogues))

    for batch in _iter_batches(dialogues, config.embedding_batch_size):
        questions = [d.question for d in batch]

        try:
            embeddings = await _embed_batch(embedding_client, questions)
        except Exception:
            logger.exception(
                "Батч из %d диалогов не удалось векторизовать после 3 попыток, пропускаем",
                len(batch),
            )
            continue

        for dialogue, embedding in zip(batch, embeddings):
            try:
                await save_dialogue_embedding(session, dialogue.id, embedding)
                await session.commit()
                logger.info("Обработан диалог %d", dialogue.id)
            except Exception:
                await session.rollback()
                logger.exception("Ошибка при обработке диалога %d", dialogue.id)


async def run(session: AsyncSession, embedding_client: EmbeddingClient) -> None:
    """Обработать все статьи, требующие построения или обновления эмбеддингов."""
    revisions = await get_revisions_needing_embedding(session)

    if not revisions:
        logger.info("Нет статей для обработки")
        return

    config = get_config()
    logger.info("Найдено статей для обработки: %d", len(revisions))

    for batch in _iter_batches(revisions, config.embedding_batch_size):
        texts = [revision.content for revision in batch]

        try:
            embeddings = await _embed_batch(embedding_client, texts)
        except Exception:
            logger.exception(
                "Батч из %d ревизий не удалось векторизовать после 3 попыток, пропускаем",
                len(batch),
            )
            continue

        for revision, embedding in zip(batch, embeddings):
            try:
                await delete_embeddings_for_source_article(session, revision.source_article_id)

                await save_embedding(
                    session,
                    article_revision_id=revision.id,
                    content=revision.content,
                    embedding=embedding,
                )

                await session.commit()
                logger.info(
                    "Обработана ревизия %d (статья %d)",
                    revision.id,
                    revision.source_article_id,
                )

            except Exception:
                await session.rollback()
                logger.exception(
                    "Ошибка при обработке ревизии %d (статья %d)",
                    revision.id,
                    revision.source_article_id,
                )
