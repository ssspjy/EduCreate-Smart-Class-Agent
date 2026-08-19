"""认证 API：OAuth2 + JWT 占位。

文档 §3.2 API/v1/auth.py。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter()


@router.post("/login", summary="教师登录（占位）")
async def login(form: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    """占位登录：任意 username/password 都返回占位 token。"""
    if not form.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username required",
        )
    return {
        "access_token": f"placeholder-token-{form.username}",
        "token_type": "bearer",
    }


@router.get("/me", summary="当前用户信息（占位）")
async def me() -> dict[str, str]:
    """占位用户信息。"""
    return {"user_id": "demo-teacher", "role": "teacher"}