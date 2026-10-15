from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    hg_brasil_key: str
    api_key: str

    hg_brasil_woeid: str = "458410"
    hg_brasil_city: str = "Alvares Machado, SP"
    app_timezone: str = "America/Sao_Paulo"

    database_url: str

    hg_brasil_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()