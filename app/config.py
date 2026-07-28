from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://127.0.0.1:27017"
    database_name: str = "zynmail"
    cors_origins: str = "http://localhost:3000"
    app_name: str = "Zynmail"
    debug: bool = True
    groq_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
