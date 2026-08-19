"""OAuth2 + JWT 安全占位。

文档 §3.2 提及 "OAuth2 + JWT 实现教师登录认证和安全访问令牌"。
后续接入 jose / passlib 后实现完整登录与鉴权。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def require_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, str]:
    """占位依赖：校验 Bearer Token。当前未配置 JWT 颁发，恒返回占位用户。"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": "demo-teacher", "role": "teacher"}