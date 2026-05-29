from fastapi import APIRouter, Depends
from app.schemas import IngestRequest
from app.auth import verify_bot_token

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/events")
async def ingest_events(
    request: IngestRequest,
    token: str = Depends(verify_bot_token),
):
    """
    Приём батча событий от JAICP-бота.

    Заглушка: принимает запрос и возвращает {"ok": true}.
    """
    return {"ok": True}
