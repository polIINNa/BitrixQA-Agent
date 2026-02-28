"""Подключение к БД со статьями (Articles DB)."""
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

load_dotenv()

Base = declarative_base()

_raw_url = os.getenv("KNOWLEDGE_DATABASE_URL", "")
KNOWLEDGE_DB_URL = (
    _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if _raw_url.startswith("postgresql://")
    else _raw_url
)

engine = create_async_engine(KNOWLEDGE_DB_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)
