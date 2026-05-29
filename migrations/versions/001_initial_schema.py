"""Initial schema: sessions, events, batches

Revision ID: 001
Revises: None
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("bot_id", sa.String(255), nullable=False),
        sa.Column("channel_type", sa.String(50)),
        sa.Column("user_id", sa.String(255)),
        sa.Column("user_from", sa.String(255)),
        sa.Column("entry_query", sa.Text),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("started_at", sa.String(50)),
        sa.Column("last_event_at", sa.String(50)),
        sa.Column("ended_at", sa.String(50)),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("events_count", sa.Integer, default=0),
        sa.Column("has_error", sa.Integer, default=0),
        sa.Column("transferred_to_operator", sa.Integer, default=0),
        sa.Column("last_state", sa.String(255)),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(255), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("ts", sa.String(50), nullable=False),
        sa.Column("t_offset_ms", sa.Integer),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("state", sa.String(255)),
        sa.Column("data", sa.Text),
    )

    op.create_table(
        "batches",
        sa.Column("batch_id", sa.String(255), primary_key=True),
        sa.Column("session_id", sa.String(255), sa.ForeignKey("sessions.id")),
        sa.Column("received_at", sa.String(50), nullable=False),
    )

    op.create_index("idx_events_session_id", "events", ["session_id"])
    op.create_index("idx_events_ts", "events", ["ts"])
    op.create_index("idx_sessions_bot_id", "sessions", ["bot_id"])
    op.create_index("idx_sessions_status", "sessions", ["status"])
    op.create_index("idx_sessions_started_at", "sessions", ["started_at"])


def downgrade() -> None:
    op.drop_index("idx_sessions_started_at", table_name="sessions")
    op.drop_index("idx_sessions_status", table_name="sessions")
    op.drop_index("idx_sessions_bot_id", table_name="sessions")
    op.drop_index("idx_events_ts", table_name="events")
    op.drop_index("idx_events_session_id", table_name="events")

    op.drop_table("events")
    op.drop_table("batches")
    op.drop_table("sessions")
