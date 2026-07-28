from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIChatRole(str, Enum):
    user = "user"
    assistant = "assistant"


class AIChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: AIChatRole
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message content must not be blank")
        return value


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    history: list[AIChatMessage] = Field(default_factory=list, max_length=9)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class AIChatResponse(BaseModel):
    reply: str = Field(min_length=1)
