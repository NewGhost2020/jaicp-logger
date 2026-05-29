from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update, select, func

import app.database as db
from app.config import settings
from app.models import sessions, events, batches

logger = logging.getLogger(__name__)

_background_tasks: list[asyncio.Task] = []


def start_background_tasks() -> None:
    _background_tasks.append(asyncio.create_task(_abandoned_loop()))
    _background_tasks.append(asyncio.create_task(_retention_loop()))


async def stop_background_tasks() -> None:
    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()


async def _abandoned_loop() -> None:
    while True:
        try:
            await asyncio.sleep(10 * 60)  # every 10 min
            await _mark_abandoned()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("abandoned_loop error")


async def _retention_loop() -> None:
    # Run once at startup (offset by 30s to not block boot), then every 24h
    await asyncio.sleep(30)
    while True:
        try:
            await _run_retention()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("retention_loop error")
        try:
            await asyncio.sleep(24 * 60 * 60)
        except asyncio.CancelledError:
            break


async def _mark_abandoned() -> None:
    if db.engine is None:
        return
    cutoff = _utc_iso(hours_ago=settings.session_abandon_hours)
    async with db.engine.begin() as conn:
        result = await conn.execute(
            update(sessions)
            .where(sessions.c.status == "active")
            .where(sessions.c.last_event_at < cutoff)
            .values(status="abandoned")
        )
    if result.rowcount:
        logger.info("Marked %d sessions as abandoned", result.rowcount)


async def _run_retention() -> None:
    if db.engine is None:
        return
    sessions_cutoff = _utc_iso(days_ago=settings.retention_days)
    batches_cutoff = _utc_iso(days_ago=settings.batches_retention_days)

    async with db.engine.begin() as conn:
        # events deleted via CASCADE when session is deleted — requires foreign_keys=ON
        # Sessions table has the date anchor; events are linked via FK
        old_ids_q = select(sessions.c.id).where(sessions.c.started_at < sessions_cutoff)
        old_ids = [row.id for row in (await conn.execute(old_ids_q)).fetchall()]

        if old_ids:
            await conn.execute(delete(events).where(events.c.session_id.in_(old_ids)))
            await conn.execute(delete(sessions).where(sessions.c.id.in_(old_ids)))
            logger.info("Retention: deleted %d old sessions", len(old_ids))

        batch_del = await conn.execute(
            delete(batches).where(batches.c.received_at < batches_cutoff)
        )
        if batch_del.rowcount:
            logger.info("Retention: deleted %d old batch records", batch_del.rowcount)


def _utc_iso(*, hours_ago: int = 0, days_ago: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago, days=days_ago)
    return dt.isoformat().replace("+00:00", "Z")
