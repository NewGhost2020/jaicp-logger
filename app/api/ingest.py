import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text
from app.schemas import IngestRequest
from app.auth import verify_bot_token
from app.models import sessions, events, batches
import app.database as db

router = APIRouter(prefix="/api/v1", tags=["ingest"])

_MAX_BODY_BYTES = 256 * 1024  # 256 KB


@router.post("/events")
async def ingest_events(
    request: Request,
    body: IngestRequest,
    token: str = Depends(verify_bot_token),
):
    if request.headers.get("content-length"):
        if int(request.headers["content-length"]) > _MAX_BODY_BYTES:
            from fastapi import HTTPException
            raise HTTPException(status_code=413, detail="Batch too large (max 256 KB)")

    if db.engine is None:
        await db.init_db()

    async with db.engine.begin() as conn:
        # --- 1. Batch-level dedup ---
        existing_batch = await conn.execute(
            select(batches.c.batch_id).where(batches.c.batch_id == body.batch_id)
        )
        if existing_batch.fetchone():
            return {"ok": True, "accepted": 0, "deduped": len(body.events)}

        # --- 2. Event-level dedup: fetch existing seqs for this session ---
        existing_seqs_result = await conn.execute(
            select(events.c.seq).where(events.c.session_id == body.session_id)
        )
        existing_seqs = {row.seq for row in existing_seqs_result.fetchall()}

        new_events = [e for e in body.events if e.seq not in existing_seqs]
        deduped_count = len(body.events) - len(new_events)

        # --- 3. Session upsert ---
        session_row = await conn.execute(
            select(sessions).where(sessions.c.id == body.session_id)
        )
        session_exists = session_row.fetchone() is not None

        if not session_exists:
            start_event = next((e for e in body.events if e.type == "session_start"), None)
            data = start_event.data if start_event else {}
            first_ts = min((e.ts for e in body.events), default=_now_iso())

            entry_query = data.get("entryQuery") or None
            if not entry_query:
                first_input = next((e for e in body.events if e.type == "user_input" and e.data.get("text")), None)
                if first_input:
                    entry_query = first_input.data["text"]

            user_from = data.get("userFrom") or data.get("userId") or None

            await conn.execute(
                sessions.insert().values(
                    id=body.session_id,
                    bot_id=body.bot_id,
                    channel_type=data.get("channelType"),
                    user_id=data.get("userId"),
                    user_from=user_from,
                    entry_query=entry_query,
                    status="active",
                    started_at=first_ts,
                    last_event_at=first_ts,
                    events_count=0,
                    has_error=0,
                    transferred_to_operator=0,
                )
            )

        # --- 4. Insert new events ---
        if new_events:
            await conn.execute(
                events.insert(),
                [
                    {
                        "session_id": body.session_id,
                        "seq": e.seq,
                        "ts": e.ts,
                        "t_offset_ms": e.t_offset_ms,
                        "type": e.type,
                        "state": e.state,
                        "data": json.dumps(e.data, ensure_ascii=False),
                    }
                    for e in new_events
                ],
            )

        # --- 5. Update session denormalized fields ---
        if new_events:
            has_error_flag = any(e.type == "error" for e in new_events)
            transferred_flag = any(e.type == "operator_transfer" for e in new_events)
            latest_event = max(new_events, key=lambda e: e.seq)
            last_ts = max(e.ts for e in new_events)

            update_vals: dict = {
                "events_count": sessions.c.events_count + len(new_events),
                "last_event_at": last_ts,
                "last_state": latest_event.state,
            }
            if has_error_flag:
                update_vals["has_error"] = 1
            if transferred_flag:
                update_vals["transferred_to_operator"] = 1

            session_end_event = next(
                (e for e in new_events if e.type == "session_end"), None
            )
            if session_end_event:
                update_vals["status"] = "ended"
                update_vals["ended_at"] = session_end_event.ts
                duration = session_end_event.data.get("duration_ms")
                if duration is not None:
                    update_vals["duration_ms"] = duration

            await conn.execute(
                sessions.update()
                .where(sessions.c.id == body.session_id)
                .values(**update_vals)
            )

        # --- 6. Record batch (idempotency guard) ---
        await conn.execute(
            batches.insert().values(
                batch_id=body.batch_id,
                session_id=body.session_id,
                received_at=_now_iso(),
            )
        )

    return {"ok": True, "accepted": len(new_events), "deduped": deduped_count}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
