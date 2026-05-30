"""Add FTS5 full-text search index for events

Revision ID: 002
Revises: 001
Create Date: 2026-05-30
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE VIRTUAL TABLE events_fts USING fts5(
            data,
            session_id UNINDEXED,
            tokenize='unicode61'
        )
    """)

    op.execute("""
        CREATE TRIGGER events_fts_after_insert AFTER INSERT ON events BEGIN
            INSERT INTO events_fts(rowid, data, session_id)
            VALUES (new.id, new.data, new.session_id);
        END
    """)

    op.execute("""
        CREATE TRIGGER events_fts_before_delete BEFORE DELETE ON events BEGIN
            DELETE FROM events_fts WHERE rowid = old.id;
        END
    """)

    op.execute("""
        CREATE TRIGGER events_fts_after_update AFTER UPDATE ON events BEGIN
            DELETE FROM events_fts WHERE rowid = old.id;
            INSERT INTO events_fts(rowid, data, session_id)
            VALUES (new.id, new.data, new.session_id);
        END
    """)

    # Populate from existing events
    op.execute("""
        INSERT INTO events_fts(rowid, data, session_id)
        SELECT id, COALESCE(data, ''), session_id FROM events
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS events_fts_after_update")
    op.execute("DROP TRIGGER IF EXISTS events_fts_before_delete")
    op.execute("DROP TRIGGER IF EXISTS events_fts_after_insert")
    op.execute("DROP TABLE IF EXISTS events_fts")
