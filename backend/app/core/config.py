"""师创智课后端配置。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    material_async_enabled: bool = False
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    material_task_soft_limit_seconds: int = Field(default=1800, ge=60, le=7200)
    material_task_hard_limit_seconds: int = Field(default=1860, ge=90, le=7260)
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
    embedding_provider: str = "hash"
    embedding_dimension: int = 1024
    bge_model_name: str = "BAAI/bge-m3"
    ocr_enabled: bool = True
    ocr_language: str = "chi_sim"
    ocr_dpi: int = Field(default=200, ge=72, le=400)
    ocr_timeout_seconds: int = Field(default=30, ge=1, le=120)
    ocr_max_pages: int = Field(default=30, ge=1, le=100)
    ocr_max_pixels: int = Field(default=20_000_000, ge=1_000_000, le=50_000_000)
    video_transcription_enabled: bool = False
    video_whisper_model: str = "tiny"
    video_whisper_model_path: str = ""
    video_whisper_model_cache_dir: str = "./data/whisper-models"
    video_allow_model_download: bool = False
    video_whisper_device: str = "cpu"
    video_whisper_compute_type: str = "int8"
    video_whisper_language: str = "zh"
    video_max_duration_seconds: int = Field(default=1800, ge=10, le=7200)
    video_transcription_timeout_seconds: int = Field(default=300, ge=30, le=3600)

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
