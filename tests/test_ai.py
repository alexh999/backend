import asyncio
import json
from collections.abc import Sequence
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.integrations.siliconflow.client import (
    SiliconFlowChatResult,
    SiliconFlowClient,
    SiliconFlowMessage,
    SiliconFlowTimeoutError,
)
from app.main import create_app
from app.modules.ai.router import get_ai_service
from app.modules.ai.schemas import AIChatMessage, AIChatRequest, AIChatRole
from app.modules.ai.service import AIService, extract_stock_symbol
from app.modules.market.schemas import MarketStockSnapshotData

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


class FakeMarketService:
    def __init__(
        self,
        *,
        snapshot: MarketStockSnapshotData | None = None,
        error: ApplicationError | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls: list[str] = []

    def get_stock_snapshot(self, symbol: str) -> MarketStockSnapshotData:
        self.calls.append(symbol)
        if self.error is not None:
            raise self.error
        if self.snapshot is not None:
            return self.snapshot
        return _build_market_snapshot(ticker=symbol)


def _build_market_snapshot(
    *,
    ticker: str,
    company_name: str = "Example Corp.",
    exchange_label: str | None = "NASDAQ",
    volume: float | None = 12_000_000,
    amount: float | None = 2_500_000_000,
    market_cap: float | None = 3_000_000_000_000,
    pe_ratio: float | None = 30.5,
) -> MarketStockSnapshotData:
    return MarketStockSnapshotData(
        ticker=ticker,
        company_name=company_name,
        exchange_label=exchange_label,
        latest_trading_date=date(2026, 7, 30),
        latest_close=210.5,
        previous_close=208.0,
        change_value=2.5,
        change_percent=1.2,
        open=208.5,
        high=212.0,
        low=207.8,
        volume=volume,
        amount=amount,
        market_cap=market_cap,
        pe_ratio=pe_ratio,
        valuation_date=(date(2026, 7, 30) if market_cap is not None else None),
    )


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
    market_service = FakeMarketService()
    app = create_app(Settings(cors_origins="", siliconflow_model=TEST_MODEL))
    app.dependency_overrides[get_ai_service] = lambda: AIService(
        integration,
        market_service=market_service,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "什么是市盈率？",
                "history": [
                    {"role": "user", "content": "Earlier question"},
                    {"role": "assistant", "content": "Earlier answer"},
                ],
            },
        )

    assert response.status_code == 200
    assert response.json() == {"reply": "Hello from the fake integration."}
    assert market_service.calls == []
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


def test_ai_service_skips_market_for_ordinary_question() -> None:
    integration = FakeAIIntegration()
    market_service = FakeMarketService()
    service = AIService(integration, market_service=market_service)

    reply = asyncio.run(service.chat(AIChatRequest(message="什么是市盈率？")))

    assert reply == "A concise answer."
    assert market_service.calls == []
    assert integration.calls == 1
    assert [message.role for message in integration.messages] == ["user"]


def test_ai_router_adds_market_context_for_current_symbol() -> None:
    integration = FakeAIIntegration(reply="AAPL is up based on the supplied data.")
    market_service = FakeMarketService()
    app = create_app(Settings(cors_origins="", siliconflow_model=TEST_MODEL))
    app.dependency_overrides[get_ai_service] = lambda: AIService(
        integration,
        market_service=market_service,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "AAPL 当前表现怎么样？", "history": []},
        )

    assert response.status_code == 200
    assert response.json() == {"reply": "AAPL is up based on the supplied data."}
    assert market_service.calls == ["AAPL"]
    assert integration.calls == 1
    assert integration.messages[0].role == "system"
    assert "股票代码：AAPL" in integration.messages[0].content
    assert "最新可用日线收盘价：210.5" in integration.messages[0].content
    assert "涨跌幅：1.2%" in integration.messages[0].content
    assert "数据日期：2026-07-30" in integration.messages[0].content
    assert "不代表盘中实时行情" in integration.messages[0].content
    assert integration.messages[-1].content == "AAPL 当前表现怎么样？"


def test_ai_service_normalizes_dollar_prefixed_us_symbol() -> None:
    integration = FakeAIIntegration()
    market_service = FakeMarketService()
    service = AIService(integration, market_service=market_service)

    asyncio.run(service.chat(AIChatRequest(message="$AAPL 现在怎么样？")))

    assert market_service.calls == ["AAPL"]
    assert integration.calls == 1


def test_ai_service_uses_latest_user_history_symbol() -> None:
    integration = FakeAIIntegration()
    market_service = FakeMarketService()
    service = AIService(integration, market_service=market_service)
    request = AIChatRequest(
        message="它现在怎么样？",
        history=[
            AIChatMessage(role=AIChatRole.user, content="先看看 AAPL"),
            AIChatMessage(role=AIChatRole.assistant, content="好的。"),
        ],
    )

    asyncio.run(service.chat(request))

    assert market_service.calls == ["AAPL"]
    assert integration.calls == 1
    assert integration.messages[0].role == "system"
    assert "股票代码：AAPL" in integration.messages[0].content


def test_ai_service_does_not_choose_symbol_when_none_is_explicit() -> None:
    integration = FakeAIIntegration()
    market_service = FakeMarketService()
    service = AIService(integration, market_service=market_service)

    asyncio.run(service.chat(AIChatRequest(message="帮我分析一下这只股票")))

    assert market_service.calls == []
    assert integration.calls == 1
    assert [message.role for message in integration.messages] == ["user"]


@pytest.mark.parametrize(
    ("message", "raw_symbol", "ticker", "exchange"),
    [
        ("分析一下 600519", "600519", "600519.SH", "SSE"),
        ("000001 最近表现如何？", "000001", "000001.SZ", "SZSE"),
    ],
)
def test_ai_service_adds_a_share_market_context(
    message: str,
    raw_symbol: str,
    ticker: str,
    exchange: str,
) -> None:
    integration = FakeAIIntegration()
    snapshot = _build_market_snapshot(
        ticker=ticker,
        company_name="A-share company",
        exchange_label=exchange,
        market_cap=None,
        pe_ratio=None,
    )
    market_service = FakeMarketService(snapshot=snapshot)
    service = AIService(integration, market_service=market_service)

    asyncio.run(service.chat(AIChatRequest(message=message)))

    assert market_service.calls == [raw_symbol]
    assert integration.calls == 1
    context = integration.messages[0].content
    assert f"股票代码：{ticker}" in context
    assert f"交易所：{exchange}" in context
    assert "最新可用日线收盘价：210.5" in context
    assert "开盘价：208.5" in context
    assert "最高价：212.0" in context
    assert "最低价：207.8" in context
    assert "成交量：12000000" in context
    assert "成交额：2500000000" in context
    assert "市值：" not in context
    assert "市盈率：" not in context


def test_ai_service_handles_multiple_symbols_without_market_call() -> None:
    integration = FakeAIIntegration()
    market_service = FakeMarketService()
    service = AIService(integration, market_service=market_service)

    asyncio.run(service.chat(AIChatRequest(message="比较 AAPL 和 TSLA")))

    assert market_service.calls == []
    assert integration.calls == 1
    context = integration.messages[0]
    assert context.role == "system"
    assert "一次只支持一只明确股票" in context.content
    assert "请要求用户一次指定一只股票代码" in context.content


@pytest.mark.parametrize(
    ("ticker", "exchange"),
    [("AAPL", ""), ("600519.SH", None)],
)
def test_ai_market_context_omits_missing_optional_fields(
    ticker: str,
    exchange: str | None,
) -> None:
    integration = FakeAIIntegration()
    snapshot = _build_market_snapshot(
        ticker=ticker,
        exchange_label=exchange,
        volume=None,
        amount=None,
        market_cap=None,
        pe_ratio=None,
    )
    service = AIService(
        integration,
        market_service=FakeMarketService(snapshot=snapshot),
    )

    asyncio.run(service.chat(AIChatRequest(message=f"{ticker} 怎么样？")))

    context = integration.messages[0].content
    assert "交易所：" not in context
    assert "成交量：" not in context
    assert "成交额：" not in context
    assert "市值：" not in context
    assert "市盈率：" not in context
    assert "None" not in context
    assert "null" not in context


def test_ai_service_handles_market_failure_without_fabricated_values() -> None:
    integration = FakeAIIntegration(reply="实时行情暂不可用。")
    market_service = FakeMarketService(
        error=ApplicationError("Unable to load market data for TSLA.", status_code=502)
    )
    app = create_app(Settings(cors_origins="", siliconflow_model=TEST_MODEL))
    app.dependency_overrides[get_ai_service] = lambda: AIService(
        integration,
        market_service=market_service,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "TSLA 当前价格是多少？", "history": []},
        )

    assert response.status_code == 200
    assert response.json() == {"reply": "实时行情暂不可用。"}
    assert market_service.calls == ["TSLA"]
    assert integration.calls == 1
    context = integration.messages[0]
    assert context.role == "system"
    assert "当前无法获取该股票的市场数据" in context.content
    assert "不得猜测实时价格" in context.content
    assert "210.5" not in context.content


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("AAPL 当前表现怎么样？", "AAPL"),
        ("看看 $AAPL", "AAPL"),
        ("TSLA 最近如何？", "TSLA"),
        ("分析一下 600519", "600519"),
        ("000001 最近表现如何？", "000001"),
        ("什么是市盈率？", None),
        ("AI", None),
        ("RSI", None),
        ("MACD", None),
        ("ETF", None),
        ("PE", None),
        ("PB", None),
        ("比较 AAPL 和 TSLA", None),
    ],
)
def test_extract_stock_symbol(text: str, expected: str | None) -> None:
    assert extract_stock_symbol(text) == expected


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
