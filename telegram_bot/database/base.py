import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from telegram_bot.database.config import DB_URL

# echo по умолчанию выключен: при echo=True в прод-логи течёт весь SQL вместе
# с биндами (включая текст сообщений клиентов — PII) и огромный шум.
# Для отладки можно временно включить через DB_ECHO=true.
_DB_ECHO = os.getenv("DB_ECHO", "false").lower() in ("1", "true", "yes")

engine = create_async_engine(
    DB_URL,
    echo=_DB_ECHO,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)
