from pydantic import BaseSettings
from typing import List

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    ADMIN_USER_IDS: List[int] = []
    DATABASE_URL: str = "sqlite:///./lunch.db"
    ADMIN_PANEL_SECRET: str = "secret"

    class Config:
        env_file = ".env"

settings = Settings()
