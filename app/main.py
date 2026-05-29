from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.api import health, ingest, sessions
from app.ui import router as ui_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при запуске и очистка при остановке."""
    # Startup
    await init_db()

    yield

    # Shutdown (заглушки для фоновых задач)
    pass


app = FastAPI(
    title="JAICP Logger",
    description="Сервис логирования сессий JAICP-ботов",
    version="0.1.0",
    lifespan=lifespan,
)

# Регистрация роутеров API
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(sessions.router)

# Регистрация UI-роутера
app.include_router(ui_router.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
