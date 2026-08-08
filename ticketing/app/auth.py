from fastapi import Header, HTTPException, status

from ticketing.app.config import get_settings


async def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    """Validate the Authorization bearer token against settings.ticketing_api_token.

    Args:
        authorization: raw Authorization header, e.g. "Bearer <token>".

    Returns:
        None
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != get_settings().ticketing_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
