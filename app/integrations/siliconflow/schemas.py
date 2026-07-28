from pydantic import BaseModel, Field


class SiliconFlowResponseMessage(BaseModel):
    content: str


class SiliconFlowChatChoice(BaseModel):
    message: SiliconFlowResponseMessage


class SiliconFlowChatCompletionResponse(BaseModel):
    model: str | None = None
    choices: list[SiliconFlowChatChoice] = Field(min_length=1)
