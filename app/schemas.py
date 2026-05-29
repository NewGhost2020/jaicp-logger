from pydantic import BaseModel


class EventIn(BaseModel):
    seq: int
    ts: str
    t_offset_ms: int
    type: str
    state: str | None = None
    data: dict = {}


class IngestRequest(BaseModel):
    bot_id: str
    session_id: str
    batch_id: str
    events: list[EventIn]


class EventOut(BaseModel):
    id: int
    session_id: str
    seq: int
    ts: str
    t_offset_ms: int
    type: str
    state: str | None
    data: dict


class SessionOut(BaseModel):
    id: str
    bot_id: str
    channel_type: str | None
    user_id: str | None
    user_from: str | None
    entry_query: str | None
    status: str
    started_at: str | None
    last_event_at: str | None
    ended_at: str | None
    duration_ms: int | None
    events_count: int
    has_error: bool
    transferred_to_operator: bool
    last_state: str | None
