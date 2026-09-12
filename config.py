import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Meta Graph API settings
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_VERIFY_TOKEN: str = "my_secure_custom_verify_token_123"
    PAGE_ACCESS_TOKEN: str = ""
    PAGE_ID: str = "1208876282318913"
    INSTAGRAM_ACCOUNT_ID: str = ""
    GRAPH_API_VERSION: str = "v26.0"
    GRAPH_API_BASE: str = "https://graph.facebook.com"

    # Webhook Base URL
    WEBHOOK_BASE_URL: str = ""

    # Dashboard & Auth
    DASHBOARD_PASSWORD: str = "admin123"
    JWT_SECRET: str = "super_secret_jwt_random_key_insta_auto_2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./insta_auto.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
