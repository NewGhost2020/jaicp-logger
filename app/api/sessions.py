from fastapi import APIRouter, Depends
from app.schemas import SessionOut
from app.auth import verify_basic_auth

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get("/sessions")
async def list_sessions(
    username: str = Depends(verify_basic_auth),
):
    """
    Список всех сессий.

    Заглушка: возвращает пустой список.
    """
    return {"sessions": []}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    username: str = Depends(verify_basic_auth),
):
    """
    Получить детали сессии.

    Заглушка: возвращает None.
    """
    return {"session": None}
