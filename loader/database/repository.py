"""Запросы к БД статей."""
from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from loader.database.models import ArticleRevision, ArticleEmbeddingIndex


async def vector_search_articles(
    session: AsyncSession,
    query_embedding: list[float],
    k: int = 20,
) -> list[tuple[int, int, str]]:
    """Векторный поиск k ближайших статей по косинусному расстоянию.

    Возвращает список (article_revision_id, source_article_id, content).
    Дедупликация по source_article_id: берётся ближайший чанк/ревизия.
    """
    stmt = (
        select(
            ArticleEmbeddingIndex.article_revision_id,
            ArticleRevision.source_article_id,
            ArticleRevision.content,
        )
        .join(ArticleRevision, ArticleRevision.id == ArticleEmbeddingIndex.article_revision_id)
        .order_by(ArticleEmbeddingIndex.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    result = await session.execute(stmt)

    seen_source_ids: set[int] = set()
    articles: list[tuple[int, int, str]] = []
    for row in result.all():
        if row.source_article_id not in seen_source_ids:
            seen_source_ids.add(row.source_article_id)
            articles.append((row.article_revision_id, row.source_article_id, row.content))
    return articles


async def get_revisions_needing_embedding(session: AsyncSession) -> list[ArticleRevision]:
    """Найти последние ревизии статей, у которых нет эмбеддинга.

    Покрывает два кейса:
    - новые статьи (ни одна ревизия не имеет эмбеддинга)
    - обновлённые статьи (появилась новая ревизия без эмбеддинга)
    """
    latest_subq = (
        select(
            ArticleRevision.source_article_id,
            func.max(ArticleRevision.created_at).label("max_created_at"),
        )
        .group_by(ArticleRevision.source_article_id)
        .subquery()
    )

    stmt = (
        select(ArticleRevision)
        .join(
            latest_subq,
            and_(
                ArticleRevision.source_article_id == latest_subq.c.source_article_id,
                ArticleRevision.created_at == latest_subq.c.max_created_at,
            ),
        )
        .outerjoin(
            ArticleEmbeddingIndex,
            ArticleEmbeddingIndex.article_revision_id == ArticleRevision.id,
        )
        .where(ArticleEmbeddingIndex.id.is_(None))
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_embeddings_for_source_article(
    session: AsyncSession,
    source_article_id: int,
) -> None:
    """Удалить все эмбеддинги по всем ревизиям указанной статьи."""
    stmt = delete(ArticleEmbeddingIndex).where(
        ArticleEmbeddingIndex.article_revision_id.in_(
            select(ArticleRevision.id).where(
                ArticleRevision.source_article_id == source_article_id
            )
        )
    )
    await session.execute(stmt)


async def save_embedding(
    session: AsyncSession,
    article_revision_id: int,
    content: str,
    embedding: list[float],
) -> None:
    """Сохранить эмбеддинг для ревизии статьи."""
    index = ArticleEmbeddingIndex(
        article_revision_id=article_revision_id,
        content=content,
        embedding=embedding,
    )
    session.add(index)
