from pydantic_settings import BaseSettings
import os
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    APP_NAME: str = "PCSoft Analytics Backend"
    API_V1_STR: str = "/api/v1"
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./pcsoft_analytics.db"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-default-super-secret-key-please-change-in-production-or-env")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    DATASOURCE_ENCRYPTION_KEY: str = os.getenv("DATASOURCE_ENCRYPTION_KEY", f"generated_{Fernet.generate_key().decode('utf-8')}")

    class Config:
        env_file = ".env"
        # For Pydantic V2, to load .env file if it exists.
        # Pydantic V1 used 'env_file_encoding' and 'env_file'.
        # For Pydantic-settings, it should automatically try to load from .env if present.
        # Ensure .env is in the root of the 'backend' directory or where the app is run from.
        extra = 'ignore' # Pydantic V2: ignore extra fields from .env not defined in Settings

settings = Settings()
