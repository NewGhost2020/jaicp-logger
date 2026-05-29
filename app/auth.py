import base64
import json
import bcrypt
from fastapi import HTTPException, status, Header
from app.config import settings


def _get_users() -> dict[str, str]:
    """Возвращает словарь {логин: хэш} из BASIC_AUTH_USERS, с fallback на старые переменные."""
    try:
        users = json.loads(settings.basic_auth_users)
        if users:
            return users
    except (json.JSONDecodeError, TypeError):
        pass
    if settings.basic_auth_user and settings.basic_auth_pass_hash:
        return {settings.basic_auth_user: settings.basic_auth_pass_hash}
    return {}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


async def verify_bot_token(x_bot_token: str = Header(None)) -> str:
    """Проверяет X-Bot-Token в заголовке."""
    if not x_bot_token or x_bot_token != settings.log_ingest_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return x_bot_token


async def verify_basic_auth(authorization: str = Header(None)) -> str:
    """Проверяет Basic Auth."""
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth",
            headers={"WWW-Authenticate": "Basic"},
        )

    try:
        encoded_creds = authorization.split(" ")[1]
        decoded = base64.b64decode(encoded_creds).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (IndexError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth header format",
        )

    users = _get_users()
    user_hash = users.get(username)
    if not user_hash or not verify_password(password, user_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return username
