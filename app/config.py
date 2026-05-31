from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_ingest_token: str = ""  # legacy общий токен (wildcard), fallback
    bot_tokens: str = "{}"  # JSON: {"bot_id": {"token": "...", "name": "..."}} или {"bot_id": "token"}
    basic_auth_user: str = ""
    basic_auth_pass_hash: str = ""
    basic_auth_users: str = "{}"  # JSON: {"login": "bcrypt_hash", ...}
    database_url: str = "sqlite+aiosqlite:///data/jaicp_logs.db"
    tz_display: str = "Europe/Moscow"
    session_abandon_hours: float = 2
    retention_days: int = 30
    batches_retention_days: int = 7

    class Config:
        env_file = ".env"


settings = Settings()
