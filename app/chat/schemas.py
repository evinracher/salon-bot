from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    customer_name: str | None = Field(default=None, min_length=1, max_length=120)
    content: str = Field(min_length=1)


class BotToggle(BaseModel):
    enabled: bool


class ManualAIMessageCreate(BaseModel):
    content: str = Field(min_length=1)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    bot_enabled: bool
    created_at: datetime
    updated_at: datetime


class ChatPostResponse(BaseModel):
    conversation: ConversationRead
    bot_reply: str | None
