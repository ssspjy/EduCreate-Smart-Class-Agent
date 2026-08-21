"""OAuth2 + JWT security helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional

from app.core.config import get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def require_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict[str, str]:
    """Validate a bearer token, with an explicit local-demo escape hatch."""
    settings = get_settings()
    if not token:
        if not settings.auth_required:
            return {"user_id": settings.demo_username, "role": "teacher"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = str(payload.get("sub") or "")
        role = str(payload.get("role") or "teacher")
        if not user_id:
            raise ValueError("missing subject")
        return {"user_id": user_id, "role": role}
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def create_access_token(user_id: str, role: str = "teacher") -> str:
    """Create a short-lived signed access token."""
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expires},
        settings.jwt_secret,
        algorithm="HS256",
    )
