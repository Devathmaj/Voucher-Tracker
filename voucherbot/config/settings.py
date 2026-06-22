from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    
    # Placeholders for future use
    smtp_host: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: Optional[str] = None
    reddit_fetch_interval_minutes: int = 3
    reddit_concurrency_limit: int = 5
    reddit_fetch_limit: int = 25
    gemini_api_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
