"""师创智课后端配置。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置：从环境变量或 .env 文件加载。"""

    app_name: str = "EduCreate Smart Class Agent"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    database_url: str = "sqlite:///./data/educreate.db"
    database_auto_create: bool = True
    upload_dir: Path = Path("./uploads")
    max_upload_size_mb: int = 50
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_reasoner_model: str = "deepseek-reasoner"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    auth_required: bool = False
    jwt_secret: str = "change-this-secret-in-production"
    access_token_expire_minutes: int = 480
    demo_username: str = "demo-teacher"
    demo_password: str = "change-me"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例，避免重复读取环境。"""
    return Settings()


def resolve_runtime_path(path: Path) -> Path:
    """Resolve relative runtime paths from the backend package root."""
    if path.is_absolute():
        return path
    return (BACKEND_ROOT / path).resolve()
