from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.api import health, ingest, sessions
from app.ui import router as ui_router
from app.tasks import start_background_tasks, stop_background_tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_background_tasks()

    yield

    await stop_background_tasks()


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
