from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.auth import verify_basic_auth

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse)
async def list_sessions_ui(
    request: Request,
    username: str = Depends(verify_basic_auth),
):
    """Список сессий в веб-интерфейсе."""
    return templates.TemplateResponse(
        request=request,
        name="sessions.html",
        context={"sessions": []},
    )


@router.get("/session/{session_id}", response_class=HTMLResponse)
async def get_session_ui(
    session_id: str,
    request: Request,
    username: str = Depends(verify_basic_auth),
):
    """Детали сессии в веб-интерфейсе."""
    return templates.TemplateResponse(
        request=request,
        name="session.html",
        context={"session": None, "events": []},
    )
