from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from telegram_bot.database.config import DB_URL

engine = create_async_engine(
    DB_URL,
    echo=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)
