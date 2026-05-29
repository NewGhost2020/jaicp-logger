from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_ingest_token: str
    basic_auth_user: str
    basic_auth_pass_hash: str
    database_url: str = "sqlite+aiosqlite:///data/jaicp_logs.db"
    tz_display: str = "Europe/Moscow"
    session_abandon_hours: int = 2
    retention_days: int = 30
    batches_retention_days: int = 7

    class Config:
        env_file = ".env"


settings = Settings()
