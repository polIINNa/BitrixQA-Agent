import asyncio

from telegram_bot.database.base import engine
from telegram_bot.database.config import Base
from telegram_bot.database.models import User, SupportSession, Message

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Таблицы успешно созданы!")

if __name__ == "__main__":
    asyncio.run(init_db())
