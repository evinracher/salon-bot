from datetime import time

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        min_length=1,
        description="SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host:port/dbname",
    )

    app_port: int = 8000
    timezone: str = "America/Bogota"
    slot_interval_minutes: int = 30
    business_open_time: time = time(hour=10, minute=0)
    business_close_time: time = time(hour=19, minute=0)
    business_days: str = "mon,tue,wed,thu,fri,sat"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    chat_max_tool_iters: int = 12

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
