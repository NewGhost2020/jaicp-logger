import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from pathlib import Path
import tempfile
import os

from app.models import metadata
from app.auth import verify_bot_token, verify_basic_auth
import app.database as db


TEST_TOKEN = "test-secret-token"
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


@pytest.fixture(scope="session")
def anyio_backend():
    """Настройка anyio backend для pytest-asyncio."""
    return "asyncio"


@pytest_asyncio.fixture
async def temp_db():
    """Создаёт временную SQLite БД для каждого теста."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite+aiosqlite:///{str(db_path)}"

        engine = create_async_engine(db_url, echo=False)

        # Создаём все таблицы
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

        yield (engine, db_url)

        await engine.dispose()


@pytest_asyncio.fixture
async def setup_test_app(temp_db, monkeypatch):
    """Настраивает тестовое приложение с мок-аутентификацией."""
    engine, db_url = temp_db

    # Генерируем bcrypt-хэш для testpassword
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash(TEST_PASSWORD)

    # Патчим конфиг напрямую (уже загруженный модуль)
    import app.config
    old_settings = app.config.settings

    # Создаём новые settings с переменными окружения
    monkeypatch.setenv("LOG_INGEST_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("BASIC_AUTH_USER", TEST_USER)
    monkeypatch.setenv("BASIC_AUTH_PASS_HASH", hashed_password)
    monkeypatch.setenv("DATABASE_URL", db_url)

    from app.config import Settings
    new_settings = Settings()
    app.config.settings = new_settings

    # Патчим глобальный движок БД
    old_engine = db.engine
    db.engine = engine

    yield new_settings

    # Восстанавливаем старые значения
    db.engine = old_engine
    app.config.settings = old_settings


@pytest_asyncio.fixture
async def client(setup_test_app, monkeypatch):
    """Создаёт тестовый AsyncClient с переопределённой аутентификацией."""
    from app.main import app

    # Переопределяем зависимости для обхода реальной аутентификации в тестах
    async def mock_verify_bot_token(x_bot_token: str = None) -> str:
        if not x_bot_token or x_bot_token != TEST_TOKEN:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bot token",
            )
        return x_bot_token

    async def mock_verify_basic_auth(authorization: str = None) -> str:
        if not authorization or not authorization.startswith("Basic "):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid auth",
            )

        import base64
        try:
            encoded_creds = authorization.split(" ")[1]
            decoded = base64.b64decode(encoded_creds).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (IndexError, ValueError):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid auth header format",
            )

        if username != TEST_USER or password != TEST_PASSWORD:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        return username

    app.dependency_overrides[verify_bot_token] = mock_verify_bot_token
    app.dependency_overrides[verify_basic_auth] = mock_verify_basic_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    # Очищаем переопределённые зависимости
    app.dependency_overrides.clear()
