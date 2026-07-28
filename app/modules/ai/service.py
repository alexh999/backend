from collections.abc import Sequence
from typing import Protocol

from app.core.errors import ApplicationError
from app.integrations.siliconflow.client import (
    SiliconFlowAuthenticationError,
    SiliconFlowChatResult,
    SiliconFlowConfigurationError,
    SiliconFlowIntegrationError,
    SiliconFlowInvalidResponseError,
    SiliconFlowMessage,
    SiliconFlowRateLimitError,
    SiliconFlowRequestRejectedError,
    SiliconFlowServiceUnavailableError,
    SiliconFlowTimeoutError,
)
from app.modules.ai.schemas import AIChatRequest

MAX_CONTEXT_MESSAGES = 10
MAX_CONTEXT_CHARACTERS = 12_000


class AIChatIntegration(Protocol):
    async def chat(
        self,
        messages: Sequence[SiliconFlowMessage],
    ) -> SiliconFlowChatResult: ...


class AIService:
    def __init__(self, integration: AIChatIntegration) -> None:
        self._integration = integration

    async def chat(self, request: AIChatRequest) -> str:
        messages = [
            SiliconFlowMessage(
                role=message.role.value,
                content=message.content,
            )
            for message in request.history[-(MAX_CONTEXT_MESSAGES - 1) :]
        ]
        messages.append(SiliconFlowMessage(role="user", content=request.message))

        if sum(len(message.content) for message in messages) > MAX_CONTEXT_CHARACTERS:
            raise ApplicationError(
                "Conversation context is too long.",
                status_code=422,
            )

        try:
            result = await self._integration.chat(messages)
        except (SiliconFlowConfigurationError, SiliconFlowAuthenticationError) as exc:
            raise ApplicationError(
                "AI service is unavailable.",
                status_code=503,
            ) from exc
        except SiliconFlowRateLimitError as exc:
            raise ApplicationError(
                "AI service is temporarily busy. Please try again later.",
                status_code=503,
            ) from exc
        except SiliconFlowTimeoutError as exc:
            raise ApplicationError(
                "AI service timed out. Please try again.",
                status_code=504,
            ) from exc
        except SiliconFlowInvalidResponseError as exc:
            raise ApplicationError(
                "AI service returned an invalid response.",
                status_code=502,
            ) from exc
        except SiliconFlowRequestRejectedError as exc:
            raise ApplicationError(
                "AI service rejected the request.",
                status_code=502,
            ) from exc
        except SiliconFlowServiceUnavailableError as exc:
            raise ApplicationError(
                "AI service is temporarily unavailable.",
                status_code=503,
            ) from exc
        except SiliconFlowIntegrationError as exc:
            raise ApplicationError(
                "AI service request failed.",
                status_code=502,
            ) from exc

        return result.text
