"""认证 API：OAuth2 + JWT 占位。

文档 §3.2 API/v1/auth.py。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import get_settings
from app.core.security import create_access_token, require_user

router = APIRouter()


@router.post("/login", summary="教师登录（占位）")
async def login(form: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    """Issue a signed token for the configured demo teacher."""
    settings = get_settings()
    if form.username != settings.demo_username or form.password != settings.demo_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(form.username),
        "token_type": "bearer",
    }


@router.get("/me", summary="当前用户信息（占位）")
async def me(user: dict[str, str] = Depends(require_user)) -> dict[str, str]:
    """Return the authenticated teacher identity."""
    return user
