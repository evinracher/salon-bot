from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.chat.models.message import MessageRole


class MessageCreate(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    role: MessageRole
    content: str = Field(min_length=1)
    customer_name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_message_id: str | None = Field(default=None, max_length=128)


class BotToggle(BaseModel):
    enabled: bool
    pause_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 7)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phone: str
    customer_name: str | None
    bot_enabled: bool
    bot_paused_until: datetime | None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_phone: str
    role: MessageRole
    content: str
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    provider_message_id: str | None
    created_at: datetime


class ChatPostResponse(BaseModel):
    conversation: ConversationRead
    accepted_message: MessageRead
    bot_reply: str | None = None
