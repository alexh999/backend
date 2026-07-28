from io import BytesIO
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from app.integrations.pandaai.client import _decode_parquet_records
from app.integrations.pandaai.schemas import (
    PandaAICompanyProfile,
    PandaAIDailyBar,
    PandaAIValuationSnapshot,
)
from app.main import create_app
from app.modules.market.service import MarketStockService, get_market_stock_service


class StubPandaAIClient:
    def get_us_detail(self, symbol: str) -> PandaAICompanyProfile:
        assert symbol == "AAPL"
        return PandaAICompanyProfile(
            symbol="AAPL",
            company_name="Apple Inc.",
            local_name="APPLE INC.",
            exchange_label="NASDAQ",
            listed_date=date(1980, 12, 12),
            website="https://www.apple.com/",
            business_sector="Technology Equipment",
            economic_sector="Technology",
            industry_group="Computers, Phones & Household Electronics",
            office_country="United States of America",
            status=1,
        )

    def get_us_daily(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PandaAIDailyBar]:
        assert symbol == "AAPL"
        assert start_date <= end_date
        return [
            PandaAIDailyBar(
                symbol="AAPL",
                trade_date=date(2026, 7, 21),
                open=210.0,
                high=214.0,
                low=208.0,
                close=212.0,
                volume=58_000_000,
                amount=12_000_000_000,
            ),
            PandaAIDailyBar(
                symbol="AAPL",
                trade_date=date(2026, 7, 22),
                open=212.0,
                high=215.0,
                low=211.0,
                close=214.5,
                volume=61_000_000,
                amount=12_400_000_000,
            ),
            PandaAIDailyBar(
                symbol="AAPL",
                trade_date=date(2026, 7, 23),
                open=214.5,
                high=216.0,
                low=213.0,
                close=215.2,
                volume=59_000_000,
                amount=12_200_000_000,
            ),
            PandaAIDailyBar(
                symbol="AAPL",
                trade_date=date(2026, 7, 24),
                open=215.2,
                high=218.0,
                low=214.8,
                close=217.9,
                volume=62_000_000,
                amount=12_800_000_000,
            ),
            PandaAIDailyBar(
                symbol="AAPL",
                trade_date=date(2026, 7, 27),
                open=217.9,
                high=219.8,
                low=216.5,
                close=218.7,
                volume=64_000_000,
                amount=13_100_000_000,
            ),
            PandaAIDailyBar(
                symbol="AAPL",
                trade_date=date(2026, 7, 28),
                open=218.7,
                high=221.4,
                low=217.9,
                close=220.3,
                volume=67_000_000,
                amount=13_700_000_000,
            ),
        ]

    def get_stock_mktfin_metric(self, symbol: str) -> PandaAIValuationSnapshot:
        assert symbol == "AAPL"
        return PandaAIValuationSnapshot(
            symbol="AAPL",
            as_of_date=date(2026, 7, 28),
            market_cap=3_300_000_000_000,
            pe_ratio=31.245,
            dividend_yield=0.53,
        )


def test_market_stock_service_builds_chart_and_stats_payload() -> None:
    service = MarketStockService(StubPandaAIClient())

    payload = service.get_stock_detail("aapl")

    assert payload.ticker == "AAPL"
    assert payload.company_name == "Apple Inc."
    assert payload.latest_close == 220.3
    assert payload.change_value == 1.6
    assert payload.change_percent == 0.73
    assert payload.available_chart_ranges == ["1W", "1M", "3M", "YTD", "1Y", "ALL"]
    assert payload.default_chart_range == "1W"
    assert payload.chart_ranges[0].line_points[-1].close == 220.3
    assert payload.stats[0].label == "Open"
    assert payload.stats[7].value == "$3.30T"
    assert payload.stats[8].value == "31.245"


def test_market_detail_endpoint_returns_payload() -> None:
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: MarketStockService(StubPandaAIClient())
    client = TestClient(app)

    response = client.get("/api/v1/market/stocks/aapl/detail")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["company_name"] == "Apple Inc."
    assert payload["latest_close"] == 220.3
    assert payload["available_chart_ranges"] == ["1W", "1M", "3M", "YTD", "1Y", "ALL"]


def test_decode_parquet_records_returns_pylist() -> None:
    table = pa.table(
        {
            "symbol": ["TSLA"],
            "date": ["20260728"],
            "open": [321.15],
            "high": [327.80],
            "low": [318.44],
            "close": [325.22],
            "volume": [88_000_000.0],
        }
    )
    buffer = BytesIO()
    pq.write_table(table, buffer)

    records = _decode_parquet_records(buffer.getvalue())

    assert records == [
        {
            "symbol": "TSLA",
            "date": "20260728",
            "open": 321.15,
            "high": 327.8,
            "low": 318.44,
            "close": 325.22,
            "volume": 88_000_000.0,
        }
    ]
