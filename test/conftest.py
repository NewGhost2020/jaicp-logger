import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from pathlib import Path
import tempfile

from app.models import metadata
from app.auth import verify_bot_token, verify_basic_auth
import app.database as db

TEST_TOKEN = "test-secret-token"
TEST_BOT_ID = "test-bot"
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


@pytest_asyncio.fixture
async def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_url = f"sqlite+aiosqlite:///{Path(tmpdir) / 'test.db'}"
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        yield (engine, db_url)
        await engine.dispose()


@pytest_asyncio.fixture
async def setup_test_app(temp_db, monkeypatch):
    engine, db_url = temp_db

    import app.config as cfg
    monkeypatch.setattr(cfg.settings, "log_ingest_token", TEST_TOKEN)
    monkeypatch.setattr(cfg.settings, "database_url", db_url)

    old_engine = db.engine
    db.engine = engine
    yield
    db.engine = old_engine


@pytest_asyncio.fixture
async def client(setup_test_app):
    from app.main import app
    from fastapi import Header

    # Мокаем auth — реальный bcrypt не нужен в unit-тестах.
    # Токен TEST_TOKEN привязан к bot_id TEST_BOT_ID (как в реальном реестре).
    async def _mock_bot_token(x_bot_token: str = Header(None)) -> str:
        if not x_bot_token or x_bot_token != TEST_TOKEN:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot token")
        return TEST_BOT_ID

    async def _mock_basic_auth(authorization: str = Header(None)) -> str:
        import base64
        if not authorization or not authorization.startswith("Basic "):
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        try:
            decoded = base64.b64decode(authorization.split(" ")[1]).decode()
            user, pwd = decoded.split(":", 1)
        except Exception:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad header")
        if user != TEST_USER or pwd != TEST_PASSWORD:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong credentials")
        return user

    app.dependency_overrides[verify_bot_token] = _mock_bot_token
    app.dependency_overrides[verify_basic_auth] = _mock_basic_auth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
