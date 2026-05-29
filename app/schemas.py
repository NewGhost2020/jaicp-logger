from typing import List, Optional
from pydantic import BaseModel


class EventIn(BaseModel):
    seq: int
    ts: str
    t_offset_ms: int
    type: str
    state: Optional[str] = None
    data: dict = {}


class IngestRequest(BaseModel):
    bot_id: str
    session_id: str
    batch_id: str
    events: List[EventIn]


class EventOut(BaseModel):
    id: int
    session_id: str
    seq: int
    ts: str
    t_offset_ms: int
    type: str
    state: Optional[str]
    data: dict


class SessionOut(BaseModel):
    id: str
    bot_id: str
    channel_type: Optional[str]
    user_id: Optional[str]
    user_from: Optional[str]
    entry_query: Optional[str]
    status: str
    started_at: Optional[str]
    last_event_at: Optional[str]
    ended_at: Optional[str]
    duration_ms: Optional[int]
    events_count: int
    has_error: bool
    transferred_to_operator: bool
    last_state: Optional[str]
