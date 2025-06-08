from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "PCSoft Analytics Backend"
    API_V1_STR: str = "/api/v1"
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./pcsoft_analytics.db"
    SECRET_KEY: str = "your-default-super-secret-key-please-change-in-production-or-env" # Ensure this is a new key
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Celery Settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Storage Settings
    PARQUET_STORAGE_BASE_DIR: str = "pcsoft_data_storage/parquet_files"

    class Config:
        env_file = ".env"

settings = Settings()
