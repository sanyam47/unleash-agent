from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

class Settings(BaseSettings):
    USE_OPENAI: bool = False
    OPENAI_API_KEY: str = "FILL_ME_IN"
    GEMINI_API_KEY: str = "FILL_ME_IN"
    SERP_API_KEY: str = "FILL_ME_IN"
    
    # Prefer REDIS_URL in cloud, fallback to local filesystem/sqlite setup.
    BROKER_URL: str = os.getenv("REDIS_URL", "filesystem://")
    RESULT_BACKEND: str = os.getenv("REDIS_URL", "db+sqlite:///./celery_results.db")
    DATABASE_URL: str = "sqlite:///./jobs.db"
    
    model_config = SettingsConfigDict(env_file=_ENV_PATH if _ENV_PATH.exists() else ".env", extra="ignore")

settings = Settings()
