"""Тесты сервиса построения эмбеддингов."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from loader.database.models import ArticleRevision
from loader.service import run

FAKE_EMBEDDING = [0.1] * 1536


def make_revision(id: int, source_article_id: int, content: str) -> ArticleRevision:
    revision = MagicMock(spec=ArticleRevision)
    revision.id = id
    revision.source_article_id = source_article_id
    revision.content = content
    return revision


@pytest.fixture
def session():
    s = MagicMock()
    s.commit = AsyncMock()
    s.rollback = AsyncMock()
    return s


@pytest.fixture
def embedding_client():
    return AsyncMock()


async def test_no_revisions(session, embedding_client):
    """Нет статей для обработки — ранний выход, никаких вызовов."""
    with patch("loader.service.get_revisions_needing_embedding", new_callable=AsyncMock, return_value=[]):
        await run(session, embedding_client)

    embedding_client.embed_documents.assert_not_called()
    session.commit.assert_not_called()


async def test_new_article(session, embedding_client):
    """Новая статья — эмбеддинг создаётся и сохраняется."""
    revision = make_revision(id=1, source_article_id=100, content="Новая статья")

    with (
        patch("loader.service.get_revisions_needing_embedding", new_callable=AsyncMock, return_value=[revision]),
        patch("loader.service._embed_batch", new_callable=AsyncMock, return_value=[FAKE_EMBEDDING]),
        patch("loader.service.delete_embeddings_for_source_article", new_callable=AsyncMock) as mock_delete,
        patch("loader.service.save_embedding", new_callable=AsyncMock) as mock_save,
    ):
        await run(session, embedding_client)

    mock_delete.assert_awaited_once_with(session, 100)
    mock_save.assert_awaited_once_with(
        session,
        article_revision_id=1,
        content="Новая статья",
        embedding=FAKE_EMBEDDING,
    )
    session.commit.assert_awaited_once()


async def test_updated_article(session, embedding_client):
    """Обновлённая статья — старый эмбеддинг удаляется, сохраняется новый."""
    revision = make_revision(id=2, source_article_id=100, content="Обновлённый контент")
    new_embedding = [0.2] * 1536

    with (
        patch("loader.service.get_revisions_needing_embedding", new_callable=AsyncMock, return_value=[revision]),
        patch("loader.service._embed_batch", new_callable=AsyncMock, return_value=[new_embedding]),
        patch("loader.service.delete_embeddings_for_source_article", new_callable=AsyncMock) as mock_delete,
        patch("loader.service.save_embedding", new_callable=AsyncMock) as mock_save,
    ):
        await run(session, embedding_client)

    # Сначала удаляем старые эмбеддинги по source_article_id, затем сохраняем новый
    mock_delete.assert_awaited_once_with(session, 100)
    mock_save.assert_awaited_once_with(
        session,
        article_revision_id=2,
        content="Обновлённый контент",
        embedding=new_embedding,
    )
    session.commit.assert_awaited_once()


async def test_failed_batch_is_skipped_others_continue(session, embedding_client):
    """Батч упал — пропускается, следующий батч обрабатывается."""
    revision1 = make_revision(id=1, source_article_id=1, content="Статья 1")
    revision2 = make_revision(id=2, source_article_id=2, content="Статья 2")

    mock_embed = AsyncMock(side_effect=[RuntimeError("API недоступен"), [FAKE_EMBEDDING]])

    with (
        patch("loader.service.get_revisions_needing_embedding", new_callable=AsyncMock, return_value=[revision1, revision2]),
        patch("loader.service._embed_batch", mock_embed),
        patch("loader.service.delete_embeddings_for_source_article", new_callable=AsyncMock),
        patch("loader.service.save_embedding", new_callable=AsyncMock) as mock_save,
        patch("loader.service.get_config") as mock_config,
    ):
        mock_config.return_value.embedding_batch_size = 1  # по одной, батчи раздельные
        await run(session, embedding_client)

    # Первый батч упал — статья 1 не сохранена
    # Второй батч прошёл — статья 2 сохранена
    mock_save.assert_awaited_once_with(
        session,
        article_revision_id=2,
        content="Статья 2",
        embedding=FAKE_EMBEDDING,
    )


async def test_db_error_rollback_continues(session, embedding_client):
    """Ошибка БД при сохранении одной ревизии — откат + продолжение обработки."""
    revision1 = make_revision(id=1, source_article_id=1, content="Статья 1")
    revision2 = make_revision(id=2, source_article_id=2, content="Статья 2")
    embeddings = [[0.1] * 1536, [0.2] * 1536]

    saved_ids = []

    async def save_side_effect(session, *, article_revision_id, content, embedding):
        saved_ids.append(article_revision_id)
        if article_revision_id == 1:
            raise RuntimeError("DB error")

    with (
        patch("loader.service.get_revisions_needing_embedding", new_callable=AsyncMock, return_value=[revision1, revision2]),
        patch("loader.service._embed_batch", new_callable=AsyncMock, return_value=embeddings),
        patch("loader.service.delete_embeddings_for_source_article", new_callable=AsyncMock),
        patch("loader.service.save_embedding", side_effect=save_side_effect),
    ):
        await run(session, embedding_client)

    assert saved_ids == [1, 2]             # обе ревизии были попытаны
    session.rollback.assert_awaited_once()  # откат только для упавшей
    session.commit.assert_awaited_once()    # коммит только для успешной
