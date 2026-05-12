from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
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

    # Chat agent LLM (groq or openai). Model + API keys are read from env.
    chat_llm_provider: str = Field(
        default="groq",
        description="Chat agent backend: 'groq' or 'openai' (case-insensitive).",
    )
    groq_api_key: str = ""
    groq_model: str = Field(
        default="llama-3.1-8b-instant",
        description="Groq model id (prefer smaller models for cost/latency).",
    )
    openai_api_key: str = ""
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI chat model when chat_llm_provider=openai (prefer small models).",
    )
    groq_fallback_models: str = Field(
        default="",
        description=(
            "Comma-separated Groq model ids to try when the primary model fails with "
            "rate limits (429). Example: llama-3.1-8b-instant,llama-3.3-70b-specdec"
        ),
    )
    chat_max_tool_iters: int = 12

    # Redis / BullMQ (WhatsApp async processing)
    redis_url: str = Field(
        default="",
        description="Redis URL for BullMQ, e.g. redis://127.0.0.1:6379/0",
    )
    whatsapp_queue_name: str = "whatsapp-inbound"
    whatsapp_worker_concurrency: int = Field(default=2, ge=1, le=64)
    whatsapp_job_attempts: int = Field(default=3, ge=1, le=10)

    # Meta WhatsApp Cloud API
    whatsapp_verify_token: str = Field(
        default="",
        description="Must match the Verify Token set in Meta webhook configuration",
    )
    whatsapp_access_token: str = Field(
        default="",
        description="Graph API permanent or system user token with whatsapp business permissions",
    )
    whatsapp_phone_number_id: str = Field(
        default="",
        description="WhatsApp phone number ID from Meta app dashboard",
    )
    whatsapp_graph_api_version: str = "v21.0"
    whatsapp_app_secret: str = Field(
        default="",
        description=(
            "Meta app secret for webhook HMAC (X-Hub-Signature-256). "
            "When empty, signature verification is skipped (dev only)."
        ),
    )

    @field_validator("groq_api_key", "openai_api_key", mode="before")
    @classmethod
    def _strip_llm_api_keys(cls, value: object) -> str:
        """Avoid 401s from accidental spaces or wrapping quotes in ``.env``."""
        if value is None:
            return ""
        text = str(value).strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
            text = text[1:-1].strip()
        return text

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
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            msg = f"Invalid IANA timezone in TIMEZONE: {self.timezone!r}"
            raise ValueError(msg) from exc
        provider = (self.chat_llm_provider or "").strip().lower()
        if provider not in ("groq", "openai"):
            raise ValueError(
                f"chat_llm_provider must be 'groq' or 'openai', got {self.chat_llm_provider!r}",
            )
        self.chat_llm_provider = provider
        return self

    @property
    def business_weekdays(self) -> frozenset[int]:
        return self.parse_business_days(self.business_days)

    @property
    def groq_fallback_model_names(self) -> tuple[str, ...]:
        raw = self.groq_fallback_models.strip()
        if not raw:
            return ()
        return tuple(part.strip() for part in raw.split(",") if part.strip())


settings = Settings()
