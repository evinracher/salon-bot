from datetime import time
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
    timezone: str = "America/Bogota"
    slot_interval_minutes: int = 30
    business_open_time: time = time(hour=10, minute=0)
    business_close_time: time = time(hour=19, minute=0)
    business_days: str = "mon,tue,wed,thu,fri,sat"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    chat_max_tool_iters: int = 12

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

    @staticmethod
    def parse_business_days(value: str) -> frozenset[int]:
        labels = {
            "mon": 0,
            "tue": 1,
            "wed": 2,
            "thu": 3,
            "fri": 4,
            "sat": 5,
            "sun": 6,
        }
        parsed: set[int] = set()
        for part in value.split(","):
            key = part.strip().lower()
            if not key:
                continue
            if key not in labels:
                raise ValueError(f"Invalid business day: {part}")
            parsed.add(labels[key])
        return frozenset(parsed)

    @model_validator(mode="after")
    def validate_business_config(self) -> "Settings":
        if self.slot_interval_minutes <= 0:
            raise ValueError("slot_interval_minutes must be greater than 0")
        if self.business_close_time <= self.business_open_time:
            raise ValueError("business_close_time must be after business_open_time")
        if not self.parse_business_days(self.business_days):
            raise ValueError("business_days must not be empty")
        return self

    @property
    def business_weekdays(self) -> frozenset[int]:
        return self.parse_business_days(self.business_days)


settings = Settings()
