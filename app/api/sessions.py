import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_

import app.database as db
from app.models import sessions, events
from app.schemas import SessionOut, EventOut
from app.auth import verify_basic_auth

router = APIRouter(prefix="/api/v1", tags=["sessions"])


async def _get_conn():
    if db.engine is None:
        await db.init_db()
    async with db.engine.connect() as conn:
        yield conn


def _row_to_session_out(row) -> SessionOut:
    return SessionOut(
        id=row.id,
        bot_id=row.bot_id,
        channel_type=row.channel_type,
        user_id=row.user_id,
        user_from=row.user_from,
        entry_query=row.entry_query,
        status=row.status,
        started_at=row.started_at,
        last_event_at=row.last_event_at,
        ended_at=row.ended_at,
        duration_ms=row.duration_ms,
        events_count=row.events_count if row.events_count is not None else 0,
        has_error=bool(row.has_error),
        transferred_to_operator=bool(row.transferred_to_operator),
        last_state=row.last_state,
    )


def _row_to_event_out(row) -> EventOut:
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

    return EventOut(
        id=row.id,
        session_id=row.session_id,
        seq=row.seq,
        ts=row.ts,
        t_offset_ms=row.t_offset_ms if row.t_offset_ms is not None else 0,
        type=row.type,
        state=row.state,
        data=parsed_data,
    )


@router.get("/sessions")
async def list_sessions(
    bot_id: str | None = None,
    from_dt: str | None = Query(None, alias="from"),
    to_dt: str | None = Query(None, alias="to"),
    status: str | None = None,
    has_error: bool = False,
    has_operator: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    username: str = Depends(verify_basic_auth),
):
    """Список сессий с фильтрацией и пагинацией."""
    conditions = []

    if bot_id is not None:
        conditions.append(sessions.c.bot_id == bot_id)
    if from_dt is not None:
        conditions.append(sessions.c.started_at >= from_dt)
    if to_dt is not None:
        conditions.append(sessions.c.started_at <= to_dt)
    if status is not None:
        conditions.append(sessions.c.status == status)
    if has_error:
        conditions.append(sessions.c.has_error == 1)
    if has_operator:
        conditions.append(sessions.c.transferred_to_operator == 1)

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
        session_list = [_row_to_session_out(row) for row in rows]

    return {
        "sessions": session_list,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    username: str = Depends(verify_basic_auth),
):
    """Детальная информация по сессии вместе со всеми событиями."""
    if db.engine is None:
        await db.init_db()

    async with db.engine.connect() as conn:
        session_query = select(sessions).where(sessions.c.id == session_id)
        session_result = await conn.execute(session_query)
        session_row = session_result.fetchone()

        if session_row is None:
            raise HTTPException(status_code=404, detail="Session not found")

        events_query = (
            select(events)
            .where(events.c.session_id == session_id)
            .order_by(events.c.seq.asc())
        )
        events_result = await conn.execute(events_query)
        event_list = [_row_to_event_out(row) for row in events_result]

    return {
        "session": _row_to_session_out(session_row),
        "events": event_list,
    }
