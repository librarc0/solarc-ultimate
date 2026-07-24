from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App — 统一元数据，改名或升版只修改此处
    APP_NAME: str = "SolArc-Ultimate"
    APP_NAME_CN: str = "极限飞盘队伍管理&战力评分系统"
    APP_VERSION: str = "0.9.8"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/eaglespower.db"

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8080",
    ]

    # OpenSkill defaults
    OPENSKILL_MU: float = 25.0
    OPENSKILL_SIGMA: float = 8.333

    # SMTP (optional — leave empty to disable password reset via email)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    APP_BASE_URL: str = "http://localhost:5173"

    # Rating weights
    RATING_ALPHA: float = 0.3    # personal contribution adjustment amplitude
    RATING_BETA: float = 0.6     # goal weight
    RATING_GAMMA: float = 0.4    # assist weight
    COMPOSITE_TS_WEIGHT: float = 0.85
    COMPOSITE_PERF_WEIGHT: float = 0.15

    # WeChat miniprogram
    WX_APP_ID: str = ""
    WX_APP_SECRET: str = ""


settings = Settings()

