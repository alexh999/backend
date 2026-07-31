from datetime import date
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from app.integrations.pandaai.client import PandaAIIntegrationError, _decode_parquet_records
from app.integrations.pandaai.schemas import (
    PandaAICompanyProfile,
    PandaAIDailyBar,
    PandaAIValuationSnapshot,
)
from app.main import create_app
from app.modules.market.service import MarketStockService, get_market_stock_service


TEST_MARKET_SYMBOLS = ("AAPL", "000001.SZ")


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

    def get_cn_detail(self, symbol: str) -> PandaAICompanyProfile:
        assert symbol == "000001.SZ"
        return PandaAICompanyProfile(
            symbol="000001.SZ",
            company_name="Ping An Bank",
            local_name="Ping An Bank",
            exchange_label="SZSE",
            listed_date=date(1991, 4, 3),
            website=None,
            business_sector="Financials",
            economic_sector="Financials",
            industry_group="MainBoard",
            office_country="China / Guangdong",
            status=1,
        )

    def get_cn_daily(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PandaAIDailyBar]:
        assert symbol == "000001.SZ"
        assert start_date <= end_date
        return [
            PandaAIDailyBar(
                symbol="000001.SZ",
                trade_date=date(2026, 7, 24),
                open=12.10,
                high=12.26,
                low=12.01,
                close=12.18,
                volume=88_000_000,
                amount=1_070_000_000,
            ),
            PandaAIDailyBar(
                symbol="000001.SZ",
                trade_date=date(2026, 7, 25),
                open=12.18,
                high=12.39,
                low=12.12,
                close=12.31,
                volume=93_000_000,
                amount=1_140_000_000,
            ),
            PandaAIDailyBar(
                symbol="000001.SZ",
                trade_date=date(2026, 7, 28),
                open=12.32,
                high=12.55,
                low=12.29,
                close=12.47,
                volume=101_000_000,
                amount=1_250_000_000,
            ),
        ]

    def get_cn_rt_daily(self, symbol: str) -> PandaAIDailyBar | None:
        assert symbol == "000001.SZ"
        return PandaAIDailyBar(
            symbol="000001.SZ",
            trade_date=date(2026, 7, 29),
            open=12.48,
            high=12.68,
            low=12.41,
            close=12.63,
            volume=106_000_000,
            amount=1_310_000_000,
        )


class MoutaiPandaAIClient(StubPandaAIClient):
    def get_cn_detail(self, symbol: str) -> PandaAICompanyProfile:
        assert symbol == "600519.SH"
        return PandaAICompanyProfile(
            symbol="600519.SH",
            company_name="Kweichow Moutai",
            local_name="贵州茅台",
            exchange_label="SSE",
            listed_date=date(2001, 8, 27),
            website=None,
            business_sector="Consumer Staples",
            economic_sector="Consumer Staples",
            industry_group="MainBoard",
            office_country="China / Guizhou",
            status=1,
        )

    def get_cn_daily(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PandaAIDailyBar]:
        assert symbol == "600519.SH"
        assert start_date <= end_date
        return [
            PandaAIDailyBar(
                symbol="600519.SH",
                trade_date=date(2026, 7, 28),
                open=1480.0,
                high=1502.0,
                low=1475.0,
                close=1495.0,
                volume=2_100_000,
                amount=3_130_000_000,
            ),
            PandaAIDailyBar(
                symbol="600519.SH",
                trade_date=date(2026, 7, 29),
                open=1496.0,
                high=1510.0,
                low=1488.0,
                close=1505.0,
                volume=2_300_000,
                amount=3_450_000_000,
            ),
        ]

    def get_cn_rt_daily(self, symbol: str) -> PandaAIDailyBar | None:
        assert symbol == "600519.SH"
        return None


class FailingPandaAIClient:
    def get_us_detail(self, symbol: str) -> PandaAICompanyProfile:
        raise PandaAIIntegrationError("network blocked")

    def get_us_daily(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PandaAIDailyBar]:
        raise AssertionError("get_us_daily should not be called when get_us_detail fails")

    def get_stock_mktfin_metric(self, symbol: str) -> PandaAIValuationSnapshot:
        raise AssertionError("get_stock_mktfin_metric should not be called when get_us_detail fails")


def test_market_stock_service_builds_chart_and_stats_payload() -> None:
    service = MarketStockService(StubPandaAIClient(), symbols=TEST_MARKET_SYMBOLS)

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


def test_market_stock_service_lists_us_and_a_share_symbols() -> None:
    service = MarketStockService(StubPandaAIClient(), symbols=TEST_MARKET_SYMBOLS)

    payload = service.list_stocks()

    tickers = {item.ticker for item in payload}
    assert "AAPL" in tickers
    assert "000001.SZ" in tickers
    aapl = next(item for item in payload if item.ticker == "AAPL")
    ping_an = next(item for item in payload if item.ticker == "000001.SZ")
    assert aapl.price_text == "220.30"
    assert aapl.reference_value == 218.7
    assert len(aapl.sparkline_values) >= 2
    assert ping_an.company_name == "Ping An Bank"
    assert ping_an.change_percent == 1.28


def test_market_detail_endpoint_returns_payload() -> None:
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: MarketStockService(
        StubPandaAIClient(),
        symbols=TEST_MARKET_SYMBOLS,
    )
    client = TestClient(app)

    response = client.get("/api/v1/market/stocks/aapl/detail")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["company_name"] == "Apple Inc."
    assert payload["latest_close"] == 220.3
    assert payload["available_chart_ranges"] == ["1W", "1M", "3M", "YTD", "1Y", "ALL"]


def test_market_list_endpoint_returns_payload() -> None:
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: MarketStockService(
        StubPandaAIClient(),
        symbols=TEST_MARKET_SYMBOLS,
    )
    client = TestClient(app)

    response = client.get("/api/v1/market/stocks")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["ticker"] == "AAPL" for item in payload)
    assert any(item["ticker"] == "000001.SZ" for item in payload)


def test_market_stock_service_supports_a_share_symbols() -> None:
    service = MarketStockService(StubPandaAIClient(), symbols=TEST_MARKET_SYMBOLS)

    payload = service.get_stock_detail("000001")

    assert payload.ticker == "000001.SZ"
    assert payload.company_name == "Ping An Bank"
    assert payload.exchange_label == "SZSE"
    assert payload.latest_close == 12.63
    assert payload.change_value == 0.16
    assert payload.change_percent == 1.28
    assert payload.stats[0].value == "CNY 12.48"
    assert payload.stats[7].value == "--"


def test_market_detail_endpoint_normalizes_a_share_symbol() -> None:
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: MarketStockService(
        StubPandaAIClient(),
        symbols=TEST_MARKET_SYMBOLS,
    )
    client = TestClient(app)

    response = client.get("/api/v1/market/stocks/000001/detail")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "000001.SZ"
    assert payload["latest_close"] == 12.63
    assert payload["exchange_label"] == "SZSE"


def test_market_detail_endpoint_returns_safe_error_when_provider_fails() -> None:
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: MarketStockService(
        FailingPandaAIClient(),
        symbols=TEST_MARKET_SYMBOLS,
    )
    client = TestClient(app)

    response = client.get("/api/v1/market/stocks/aapl/detail")

    assert response.status_code == 502


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


def test_market_stock_service_returns_daily_bars_for_quant() -> None:
    service = MarketStockService(
        StubPandaAIClient(),
        symbols=TEST_MARKET_SYMBOLS,
    )

    bars = service.get_daily_bars("aapl", limit=3)

    assert len(bars) == 3
    assert bars[0].ticker == "AAPL"
    assert bars[0].trade_date == date(2026, 7, 24)
    assert bars[0].previous_close == 215.2
    assert bars[-1].close == 220.3
    assert bars[-1].volume == 67_000_000
    assert bars[-1].amount == 13_700_000_000


def test_market_stock_service_returns_lightweight_stock_snapshot() -> None:
    service = MarketStockService(
        StubPandaAIClient(),
        symbols=TEST_MARKET_SYMBOLS,
    )

    snapshot = service.get_stock_snapshot("aapl")

    assert snapshot.ticker == "AAPL"
    assert snapshot.company_name == "Apple Inc."
    assert snapshot.latest_trading_date == date(2026, 7, 28)
    assert snapshot.latest_close == 220.3
    assert snapshot.previous_close == 218.7
    assert snapshot.change_value == 1.6
    assert snapshot.change_percent == 0.73
    assert snapshot.open == 218.7
    assert snapshot.high == 221.4
    assert snapshot.low == 217.9
    assert snapshot.volume == 67_000_000
    assert snapshot.amount == 13_700_000_000
    assert snapshot.market_cap == 3_300_000_000_000
    assert snapshot.pe_ratio == 31.245
    assert snapshot.valuation_date == date(2026, 7, 28)


def test_market_stock_snapshot_uses_existing_a_share_symbol_routing() -> None:
    service = MarketStockService(MoutaiPandaAIClient())

    snapshot = service.get_stock_snapshot("600519")

    assert snapshot.ticker == "600519.SH"
    assert snapshot.company_name == "Kweichow Moutai"
    assert snapshot.exchange_label == "SSE"
    assert snapshot.latest_trading_date == date(2026, 7, 29)
    assert snapshot.latest_close == 1505.0
    assert snapshot.open == 1496.0
    assert snapshot.high == 1510.0
    assert snapshot.low == 1488.0
    assert snapshot.volume == 2_300_000
    assert snapshot.amount == 3_450_000_000
    assert snapshot.market_cap is None
    assert snapshot.pe_ratio is None


def test_market_stock_snapshot_keeps_sz_a_share_routing() -> None:
    service = MarketStockService(StubPandaAIClient())

    snapshot = service.get_stock_snapshot("000001")

    assert snapshot.ticker == "000001.SZ"
    assert snapshot.exchange_label == "SZSE"
    assert snapshot.latest_trading_date == date(2026, 7, 29)
    assert snapshot.amount == 1_310_000_000
    assert snapshot.market_cap is None
