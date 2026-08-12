from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "TeamSync AI Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    GROQ_API_KEY: Optional[str] = None
    AI_MODEL: str = "llama-3.1-70b-versatile"
    AI_TEMPERATURE: float = 0.1
    AI_MAX_TOKENS: int = 4096
    AI_TIMEOUT_SECONDS: int = 60
    
    DATABASE_URL: str = "postgresql+asyncpg://teamsync:teamsync_dev_password@localhost:5432/teamsync"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000", "http://localhost:8001"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()