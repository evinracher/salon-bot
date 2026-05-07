from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_user: str = "user"
    db_password: str = "password"
    db_host: str = "127.0.0.1"
    db_port: int = 5433
    app_port: int = 8000
    db_name: str = "salon_bot"
    test_db_name: str = "salon_bot_test"

    # Optional explicit env var overrides; computed if omitted.
    database_url: str = ""
    test_database_url: str = ""

    @model_validator(mode="before")
    @classmethod
    def build_database_urls(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        db_user = payload.get("db_user", "user")
        db_password = payload.get("db_password", "password")
        db_host = payload.get("db_host", "127.0.0.1")
        db_port = payload.get("db_port", 5433)
        db_name = payload.get("db_name", "salon_bot")
        test_db_name = payload.get("test_db_name", "salon_bot_test")

        if not payload.get("database_url"):
            payload["database_url"] = (
                f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            )

        if not payload.get("test_database_url"):
            payload["test_database_url"] = (
                f"postgresql+asyncpg://{db_user}:{db_password}"
                f"@{db_host}:{db_port}/{test_db_name}"
            )
        return payload


settings = Settings()
