"""
Alembic env для loader сервиса (Articles DB).

Зависимость от внешнего сервиса:
    Loader управляет только таблицей `article_embedding_index`.
    Таблица `article_revision` создаётся и управляется сервисом-парсером.

    Порядок деплоя на чистую БД:
        1. Применить миграции парсера (создаёт `article_revision`)
        2. Применить миграции loader'а (создаёт `article_embedding_index`)

    Если `article_revision` отсутствует, миграция завершится с ошибкой.
"""
import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import inspect, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

load_dotenv()

from loader.database.connection import Base
from loader.database.models import ArticleRevision, ArticleEmbeddingIndex, DialogueKnowledgeItem  # noqa: F401

config = context.config

_raw_url = os.getenv("KNOWLEDGE_DATABASE_URL", "")
KNOWLEDGE_DB_URL = (
    _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if _raw_url.startswith("postgresql://")
    else _raw_url
)
config.set_main_option("sqlalchemy.url", KNOWLEDGE_DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Loader управляет только своей таблицей — остальные игнорируем при autogenerate
LOADER_TABLES = {"article_embedding_index", "dialogue_knowledge_item"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name not in LOADER_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        version_table="alembic_version_loader",
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("article_revision"):
        raise RuntimeError(
            "Таблица 'article_revision' не найдена в БД. "
            "Убедитесь, что сервис-парсер применил свои миграции перед запуском loader."
        )

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        version_table="alembic_version_loader",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
