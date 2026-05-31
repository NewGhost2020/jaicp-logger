import base64
import json
import secrets
import bcrypt
from fastapi import HTTPException, status, Header
from app.config import settings


def _get_bot_registry() -> dict[str, dict]:
    """Реестр ботов из BOT_TOKENS: {bot_id: {"token": str, "name": str}}.

    Значение в JSON может быть объектом {"token", "name"} либо просто строкой-токеном
    (тогда name = bot_id).
    """
    try:
        raw = json.loads(settings.bot_tokens)
    except (json.JSONDecodeError, TypeError):
        raw = {}

    registry: dict[str, dict] = {}
    for bot_id, val in raw.items():
        if isinstance(val, dict):
            token = val.get("token", "")
            name = val.get("name") or bot_id
        else:
            token = val
            name = bot_id
        if token:
            registry[bot_id] = {"token": token, "name": name}
    return registry


def get_bot_names() -> dict[str, str]:
    """{bot_id: отображаемое_имя} для UI."""
    return {bot_id: info["name"] for bot_id, info in _get_bot_registry().items()}


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
    """Проверяет X-Bot-Token и возвращает bot_id, привязанный к токену.

    Возврат '*' означает legacy-общий токен (wildcard): разрешён любой bot_id.
    """
    if x_bot_token:
        for bot_id, info in _get_bot_registry().items():
            if secrets.compare_digest(x_bot_token, info["token"]):
                return bot_id
        if settings.log_ingest_token and secrets.compare_digest(
            x_bot_token, settings.log_ingest_token
        ):
            return "*"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid bot token",
        headers={"WWW-Authenticate": "Bearer"},
    )


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
