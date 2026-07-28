from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.siliconflow.schemas import SiliconFlowChatCompletionResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SiliconFlowMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class SiliconFlowChatResult:
    text: str
    provider_model: str | None = None
    status_code: int | None = None


class SiliconFlowIntegrationError(Exception):
    """Base class for safe, project-internal SiliconFlow errors."""


class SiliconFlowConfigurationError(SiliconFlowIntegrationError):
    pass


class SiliconFlowAuthenticationError(SiliconFlowIntegrationError):
    pass


class SiliconFlowRateLimitError(SiliconFlowIntegrationError):
    pass


class SiliconFlowTimeoutError(SiliconFlowIntegrationError):
    pass


class SiliconFlowServiceUnavailableError(SiliconFlowIntegrationError):
    pass


class SiliconFlowRequestRejectedError(SiliconFlowIntegrationError):
    pass


class SiliconFlowInvalidResponseError(SiliconFlowIntegrationError):
    pass


class SiliconFlowClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> SiliconFlowClient:
        api_key = (
            settings.siliconflow_api_key.get_secret_value()
            if settings.siliconflow_api_key is not None
            else None
        )
        return cls(
            api_key=api_key,
            base_url=settings.siliconflow_base_url,
            model=settings.siliconflow_model,
            timeout_seconds=settings.siliconflow_timeout_seconds,
            max_tokens=settings.siliconflow_max_tokens,
        )

    async def chat(
        self,
        messages: Sequence[SiliconFlowMessage],
    ) -> SiliconFlowChatResult:
        if not self._api_key or not self._base_url or not self._model:
            raise SiliconFlowConfigurationError

        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
            "max_tokens": self._max_tokens,
        }
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        logger.info("Calling SiliconFlow chat completions endpoint")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout_seconds),
                transport=self._transport,
            ) as http_client:
                response = await http_client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise SiliconFlowTimeoutError from exc
        except httpx.RequestError as exc:
            raise SiliconFlowServiceUnavailableError from exc

        if response.status_code != httpx.codes.OK:
            self._raise_for_status(response.status_code)

        try:
            parsed = SiliconFlowChatCompletionResponse.model_validate(
                response.json()
            )
        except (ValueError, ValidationError) as exc:
            raise SiliconFlowInvalidResponseError from exc

        text = parsed.choices[0].message.content.strip()
        if not text:
            raise SiliconFlowInvalidResponseError
        return SiliconFlowChatResult(
            text=text,
            provider_model=parsed.model,
            status_code=response.status_code,
        )

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if status_code in (401, 403):
            raise SiliconFlowAuthenticationError
        if status_code == 429:
            raise SiliconFlowRateLimitError
        if status_code == 504:
            raise SiliconFlowTimeoutError
        if status_code >= 500:
            raise SiliconFlowServiceUnavailableError
        raise SiliconFlowRequestRejectedError
