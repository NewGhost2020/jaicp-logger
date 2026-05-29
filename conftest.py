import os

# Set required env vars before any app modules are imported
os.environ.setdefault("LOG_INGEST_TOKEN", "test-secret-token")
os.environ.setdefault("BASIC_AUTH_USER", "testuser")
os.environ.setdefault("BASIC_AUTH_PASS_HASH", "$2b$12$placeholder_not_used_in_tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///data/test.db")
