import asyncio
import json
from collections.abc import Sequence

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.siliconflow.client import (
    SiliconFlowChatResult,
    SiliconFlowClient,
    SiliconFlowMessage,
    SiliconFlowTimeoutError,
)
from app.main import create_app
from app.modules.ai.router import get_ai_service
from app.modules.ai.schemas import AIChatMessage, AIChatRequest, AIChatRole
from app.modules.ai.service import AIService

TEST_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


class FakeAIIntegration:
    def __init__(
        self,
        *,
        reply: str = "A concise answer.",
        error: Exception | None = None,
    ) -> None:
        self.reply = reply
        self.error = error
        self.calls = 0
        self.messages: Sequence[SiliconFlowMessage] = ()

    async def chat(
        self,
        messages: Sequence[SiliconFlowMessage],
    ) -> SiliconFlowChatResult:
        self.calls += 1
        self.messages = messages
        if self.error is not None:
            raise self.error
        return SiliconFlowChatResult(text=self.reply)


def test_ai_chat_schema_rejects_blank_and_excess_history() -> None:
    with pytest.raises(ValidationError):
        AIChatRequest(message="   ")

    history = [
        AIChatMessage(role=AIChatRole.user, content=f"message {index}")
        for index in range(10)
    ]
    with pytest.raises(ValidationError):
        AIChatRequest(message="current", history=history)


def test_ai_router_returns_standardized_reply() -> None:
    integration = FakeAIIntegration(reply="Hello from the fake integration.")
    app = create_app(Settings(cors_origins="", siliconflow_model=TEST_MODEL))
    app.dependency_overrides[get_ai_service] = lambda: AIService(integration)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Hello",
                "history": [
                    {"role": "user", "content": "Earlier question"},
                    {"role": "assistant", "content": "Earlier answer"},
                ],
            },
        )

    assert response.status_code == 200
    assert response.json() == {"reply": "Hello from the fake integration."}
    assert integration.calls == 1


def test_ai_router_converts_timeout_to_safe_error() -> None:
    integration = FakeAIIntegration(error=SiliconFlowTimeoutError())
    app = create_app(Settings(cors_origins="", siliconflow_model=TEST_MODEL))
    app.dependency_overrides[get_ai_service] = lambda: AIService(integration)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "Hello"},
        )

    assert response.status_code == 504
    assert response.json() == {"detail": "AI service timed out. Please try again."}
    assert integration.calls == 1


def test_ai_service_calls_integration_once() -> None:
    integration = FakeAIIntegration()
    service = AIService(integration)
    request = AIChatRequest(
        message="Current question",
        history=[
            AIChatMessage(role=AIChatRole.user, content="Earlier question"),
            AIChatMessage(role=AIChatRole.assistant, content="Earlier answer"),
        ],
    )

    reply = asyncio.run(service.chat(request))

    assert reply == "A concise answer."
    assert integration.calls == 1
    assert [message.role for message in integration.messages] == [
        "user",
        "assistant",
        "user",
    ]


def test_siliconflow_client_sends_official_non_streaming_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.siliconflow.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload == {
            "model": TEST_MODEL,
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
            "max_tokens": 32,
        }
        return httpx.Response(
            200,
            json={
                "id": "test-completion",
                "model": TEST_MODEL,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello back",
                        }
                    }
                ],
            },
        )

    client = SiliconFlowClient(
        api_key="test-api-key",
        base_url="https://api.siliconflow.com/v1",
        model=TEST_MODEL,
        timeout_seconds=1,
        max_tokens=32,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.chat([SiliconFlowMessage(role="user", content="Hello")])
    )

    assert result.text == "Hello back"
    assert result.provider_model == TEST_MODEL
    assert result.status_code == 200


def test_siliconflow_client_converts_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timeout detail", request=request)

    client = SiliconFlowClient(
        api_key="test-api-key",
        base_url="https://api.siliconflow.com/v1",
        model=TEST_MODEL,
        timeout_seconds=1,
        max_tokens=32,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(SiliconFlowTimeoutError):
        asyncio.run(
            client.chat([SiliconFlowMessage(role="user", content="Hello")])
        )
