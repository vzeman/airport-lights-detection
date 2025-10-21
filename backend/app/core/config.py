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
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # Celery
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    
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
    API_BASE_URL: str = Field(default="http://localhost:8002", env="API_BASE_URL")
    
    # File Storage
    DATA_PATH: str = Field(default="/data", env="DATA_PATH")
    VIDEO_PATH: str = Field(default="/data/videos", env="VIDEO_PATH")
    IMAGE_PATH: str = Field(default="/data/images", env="IMAGE_PATH")
    REPORT_PATH: str = Field(default="/data/reports", env="REPORT_PATH")
    TEMP_PATH: str = Field(default="/data/temp", env="TEMP_PATH")
    MODEL_PATH: str = Field(default="/data/models", env="MODEL_PATH")
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # External APIs
    OPENAIP_API_KEY: str = Field(default="", env="OPENAIP_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()