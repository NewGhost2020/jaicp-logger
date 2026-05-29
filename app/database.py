import aiosqlite
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection
from app.config import settings
from app.models import metadata


engine = None


async def init_db():
    """Инициализирует БД и создаёт таблицы."""
    global engine
    engine = create_async_engine(settings.database_url, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def get_db() -> AsyncConnection:
    """Dependency для получения подключения к БД."""
    global engine
    if engine is None:
        await init_db()
    async with engine.connect() as conn:
        yield conn
