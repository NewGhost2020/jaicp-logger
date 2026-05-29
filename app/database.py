import aiosqlite
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection
from app.config import settings
from app.models import metadata


engine = None


async def init_db():
    """Инициализирует БД и создаёт таблицы."""
    global engine
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def get_db() -> AsyncConnection:
    """Dependency для получения подключения к БД."""
    global engine
    if engine is None:
        await init_db()
    async with engine.connect() as conn:
        yield conn
