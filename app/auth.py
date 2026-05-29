from fastapi import HTTPException, status, Header
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль."""
    return pwd_context.verify(plain_password, hashed_password)


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

    import base64
    try:
        encoded_creds = authorization.split(" ")[1]
        decoded = base64.b64decode(encoded_creds).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (IndexError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth header format",
        )

    if username != settings.basic_auth_user or not verify_password(password, settings.basic_auth_pass_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return username
