from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Airport Management System"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # Database
    DATABASE_URL: str = Field(
        default="mysql+aiomysql://airport_user:airport_pass@localhost:3307/airport_mgmt",
        env="DATABASE_URL"
    )

    # Security
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production-use-secrets-module-to-generate",
        env="SECRET_KEY"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    )
    
    # API Base URL for serving content (videos, reports, etc.)
    API_BASE_URL: str = Field(default="http://localhost:8001", env="API_BASE_URL")

    # OAuth URLs
    BACKEND_URL: str = Field(default="http://localhost:8001", env="BACKEND_URL")
    FRONTEND_URL: str = Field(default="http://localhost:3001", env="FRONTEND_URL")

    # Google OAuth Credentials
    GOOGLE_CLIENT_ID: str = Field(default="", env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", env="GOOGLE_CLIENT_SECRET")

    # File Storage (local fallback when S3 is disabled)
    DATA_PATH: str = Field(default="/data", env="DATA_PATH")
    VIDEO_PATH: str = Field(default="/data/videos", env="VIDEO_PATH")
    IMAGE_PATH: str = Field(default="/data/images", env="IMAGE_PATH")
    REPORT_PATH: str = Field(default="/data/reports", env="REPORT_PATH")
    TEMP_PATH: str = Field(default="/tmp", env="TEMP_PATH")
    MODEL_PATH: str = Field(default="/data/models", env="MODEL_PATH")

    # S3 Storage Configuration
    USE_S3_STORAGE: bool = Field(default=False, env="USE_S3_STORAGE")
    AWS_ACCESS_KEY_ID: str = Field(default="", env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(default="eu-central-1", env="AWS_REGION")
    S3_BUCKET: str = Field(default="", env="S3_BUCKET")
    S3_PRESIGNED_URL_EXPIRATION: int = Field(default=3600, env="S3_PRESIGNED_URL_EXPIRATION")  # 1 hour
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # External APIs
    OPENAIP_API_KEY: str = Field(default="", env="OPENAIP_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()