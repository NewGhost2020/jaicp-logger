from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import app.database as db
from app.models import sessions, events
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, func, or_, select, text

from app.auth import verify_basic_auth, get_bot_names

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

router = APIRouter(tags=["ui"])

MSK = timezone(timedelta(hours=3))


def _moscow_str(iso_str: str | None) -> str:
    """Конвертирует UTC ISO строку в Moscow time (UTC+3), формат DD.MM HH:MM."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_msk = dt.astimezone(MSK)
        return dt_msk.strftime("%d.%m %H:%M")
    except Exception:
        return iso_str[:16] if iso_str else "—"


def _duration_str(ms: int | None) -> str:
    if ms is None:
        return "—"
    s = ms // 1000
    m, s = divmod(s, 60)
    return f"{m}м {s}с" if m else f"{s}с"


def _offset_str(ms: int | None) -> str:
    if ms is None:
        return "+0с"
    s = ms // 1000
    m, s = divmod(s, 60)
    return f"+{m}м {s}с" if m else f"+{s}с"


def _row_to_session_dict(row) -> dict:
    return {
        "id": row.id,
        "bot_id": row.bot_id,
        "channel_type": row.channel_type,
        "user_id": row.user_id,
        "user_from": row.user_from,
        "entry_query": row.entry_query,
        "status": row.status,
        "started_at": row.started_at,
        "last_event_at": row.last_event_at,
        "ended_at": row.ended_at,
        "duration_ms": row.duration_ms,
        "events_count": row.events_count if row.events_count is not None else 0,
        "has_error": bool(row.has_error),
        "transferred_to_operator": bool(row.transferred_to_operator),
        "last_state": row.last_state,
        # computed
        "started_at_msk": _moscow_str(row.started_at),
        "duration_str": _duration_str(row.duration_ms),
    }


def _row_to_event_dict(row) -> dict:
    raw_data = row.data
    if isinstance(raw_data, str):
        try:
            parsed_data = json.loads(raw_data)
        except (json.JSONDecodeError, TypeError):
            parsed_data = {}
    elif isinstance(raw_data, dict):
        parsed_data = raw_data
    else:
        parsed_data = {}

    return {
        "id": row.id,
        "session_id": row.session_id,
        "seq": row.seq,
        "ts": row.ts,
        "t_offset_ms": row.t_offset_ms if row.t_offset_ms is not None else 0,
        "type": row.type,
        "state": row.state,
        "data": parsed_data,
        # computed
        "offset_str": _offset_str(row.t_offset_ms),
    }


def _build_qs(params: dict) -> str:
    """Строит query string, пропуская None и False."""
    filtered = {}
    for k, v in params.items():
        if v is None or v is False:
            continue
        if v is True:
            filtered[k] = "true"
        else:
            filtered[k] = v
    return urlencode(filtered)


@router.get("/", response_class=HTMLResponse)
async def sessions_list(
    request: Request,
    bot_id: str | None = None,
    from_dt: str | None = Query(None, alias="from"),
    to_dt: str | None = Query(None, alias="to"),
    status: str | None = None,
    has_error: bool = False,
    has_operator: bool = False,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    username: str = Depends(verify_basic_auth),
):
    today = datetime.now(MSK).date()
    from_default = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    to_default = today.strftime("%Y-%m-%d")

    conditions = []
    if bot_id:
        conditions.append(sessions.c.bot_id == bot_id)
    if from_dt:
        conditions.append(sessions.c.started_at >= from_dt)
    if to_dt:
        # to_dt включительно: добавляем суффикс "T23:59:59" для сравнения строк
        conditions.append(sessions.c.started_at <= to_dt + "T23:59:59")
    if status:
        conditions.append(sessions.c.status == status)
    if has_error:
        conditions.append(sessions.c.has_error == 1)
    if has_operator:
        conditions.append(sessions.c.transferred_to_operator == 1)
    if search:
        pat = f"%{search}%"
        # FTS5 phrase search: wrap in double-quotes, escape internal quotes
        fts_term = '"' + search.replace('"', '""') + '"'
        fts_q = text("SELECT session_id FROM events_fts WHERE events_fts MATCH :q").bindparams(q=fts_term)
        conditions.append(
            or_(
                sessions.c.entry_query.like(pat),
                sessions.c.user_from.like(pat),
                sessions.c.id.in_(fts_q),
            )
        )

    where_clause = and_(*conditions) if conditions else True

    if db.engine is None:
        await db.init_db()

    async with db.engine.connect() as conn:
        count_query = select(func.count()).select_from(sessions).where(where_clause)
        count_result = await conn.execute(count_query)
        total = count_result.scalar() or 0

        data_query = (
            select(sessions)
            .where(where_clause)
            .order_by(sessions.c.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await conn.execute(data_query)
        session_list = [_row_to_session_dict(row) for row in rows]

        # Список ботов для выпадашки: объединяем реестр имён и реально присутствующие в БД
        bot_rows = await conn.execute(select(sessions.c.bot_id).distinct())
        db_bot_ids = {r.bot_id for r in bot_rows if r.bot_id}

    bot_names = get_bot_names()
    all_bot_ids = sorted(db_bot_ids | set(bot_names.keys()))
    bots = [{"id": bid, "name": bot_names.get(bid, bid)} for bid in all_bot_ids]

    filters = {
        "bot_id": bot_id,
        "from": from_dt,
        "to": to_dt,
        "status": status,
        "has_error": has_error,
        "has_operator": has_operator,
        "search": search,
    }

    # Параметры пагинации (без offset)
    base_params = {
        "bot_id": bot_id,
        "from": from_dt,
        "to": to_dt,
        "status": status,
        "has_error": has_error,
        "has_operator": has_operator,
        "search": search,
        "limit": limit,
    }
    pagination_prev = _build_qs({**base_params, "offset": max(0, offset - limit)})
    pagination_next = _build_qs({**base_params, "offset": offset + limit})

    return templates.TemplateResponse(
        request=request,
        name="sessions.html",
        context={
            "sessions": session_list,
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": filters,
            "bots": bots,
            "bot_names": bot_names,
            "from_default": from_default,
            "to_default": to_default,
            "pagination_prev": pagination_prev,
            "pagination_next": pagination_next,
        },
    )


@router.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(
    request: Request,
    session_id: str,
    username: str = Depends(verify_basic_auth),
):
    if db.engine is None:
        await db.init_db()

    async with db.engine.connect() as conn:
        session_query = select(sessions).where(sessions.c.id == session_id)
        session_result = await conn.execute(session_query)
        session_row = session_result.fetchone()

        if session_row is None:
            return templates.TemplateResponse(
                request=request,
                name="session.html",
                context={"session": None, "events": []},
                status_code=404,
            )

        events_query = (
            select(events)
            .where(events.c.session_id == session_id)
            .order_by(events.c.seq.asc())
        )
        events_result = await conn.execute(events_query)
        event_list = [_row_to_event_dict(row) for row in events_result]

    session_dict = _row_to_session_dict(session_row)

    return templates.TemplateResponse(
        request=request,
        name="session.html",
        context={
            "session": session_dict,
            "events": event_list,
        },
    )
