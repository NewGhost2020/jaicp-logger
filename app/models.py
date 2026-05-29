from sqlalchemy import Table, Column, String, Integer, Text, MetaData, Index, ForeignKey, DateTime
from sqlalchemy.sql import func

metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("bot_id", String(255), nullable=False),
    Column("channel_type", String(50)),
    Column("user_id", String(255)),
    Column("user_from", String(255)),
    Column("entry_query", Text),
    Column("status", String(50), default="active"),
    Column("started_at", String(50)),
    Column("last_event_at", String(50)),
    Column("ended_at", String(50)),
    Column("duration_ms", Integer),
    Column("events_count", Integer, default=0),
    Column("has_error", Integer, default=0),
    Column("transferred_to_operator", Integer, default=0),
    Column("last_state", String(255)),
)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String(255), ForeignKey("sessions.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("ts", String(50), nullable=False),
    Column("t_offset_ms", Integer),
    Column("type", String(50), nullable=False),
    Column("state", String(255)),
    Column("data", Text),
)

batches = Table(
    "batches",
    metadata,
    Column("batch_id", String(255), primary_key=True),
    Column("session_id", String(255), ForeignKey("sessions.id")),
    Column("received_at", String(50), nullable=False),
)

# Indices
Index("idx_events_session_id", events.c.session_id)
Index("idx_events_ts", events.c.ts)
Index("idx_sessions_bot_id", sessions.c.bot_id)
Index("idx_sessions_status", sessions.c.status)
Index("idx_sessions_started_at", sessions.c.started_at)
