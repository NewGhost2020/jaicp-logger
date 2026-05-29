from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check():
    """Проверка здоровья сервиса."""
    return {"status": "ok"}
