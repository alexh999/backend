from datetime import date

import pandas as pd
import pytest

from app.integrations.yahoo_finance import client
from app.integrations.yahoo_finance.client import (
    YahooFinanceClient,
    YahooFinanceIntegrationError,
)


def test_get_daily_bars_converts_a_share_symbol(monkeypatch) -> None:
    requested_symbols: list[str] = []

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            requested_symbols.append(symbol)

        def history(self, **kwargs):
            return pd.DataFrame(
                {
                    "Open": [100.0, 102.0],
                    "High": [105.0, 106.0],
                    "Low": [99.0, 101.0],
                    "Close": [103.0, 104.0],
                    "Volume": [1000.0, 1200.0],
                },
                index=pd.to_datetime(["2026-08-12", "2026-08-13"]),
            )

    monkeypatch.setattr(client.yf, "Ticker", FakeTicker)

    bars = YahooFinanceClient().get_daily_bars(
        "600519",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 14),
    )

    assert requested_symbols == ["600519.SS"]
    assert len(bars) == 2
    assert bars[0].symbol == "600519.SH"
    assert bars[0].trade_date == date(2026, 8, 12)
    assert bars[0].open == 100.0
    assert bars[0].close == 103.0
    assert bars[0].volume == 1000.0


@pytest.mark.parametrize(
    ("input_symbol", "expected_yahoo_symbol", "expected_app_symbol"),
    [
        ("000001", "000001.SZ", "000001.SZ"),
        ("600519.SH", "600519.SS", "600519.SH"),
        ("600519.SS", "600519.SS", "600519.SH"),
        ("0700.HK", "0700.HK", "0700.HK"),
        ("AAPL", "AAPL", "AAPL"),
    ],
)
def test_symbol_conversion(
    monkeypatch,
    input_symbol: str,
    expected_yahoo_symbol: str,
    expected_app_symbol: str,
) -> None:
    requested_symbols: list[str] = []

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            requested_symbols.append(symbol)

        def history(self, **kwargs):
            return pd.DataFrame(
                {
                    "Open": [10.0],
                    "High": [11.0],
                    "Low": [9.0],
                    "Close": [10.5],
                    "Volume": [500.0],
                },
                index=pd.to_datetime(["2026-08-13"]),
            )

    monkeypatch.setattr(client.yf, "Ticker", FakeTicker)

    bars = YahooFinanceClient().get_daily_bars(
        input_symbol,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 14),
    )

    assert requested_symbols == [expected_yahoo_symbol]
    assert bars[0].symbol == expected_app_symbol


def test_rejects_invalid_date_range() -> None:
    with pytest.raises(
        ValueError,
        match="Start date cannot be later than end date",
    ):
        YahooFinanceClient().get_daily_bars(
            "AAPL",
            start_date=date(2026, 8, 14),
            end_date=date(2026, 8, 1),
        )


def test_wraps_yfinance_errors(monkeypatch) -> None:
    class FailingTicker:
        def __init__(self, symbol: str) -> None:
            pass

        def history(self, **kwargs):
            raise RuntimeError("provider failed")

    monkeypatch.setattr(client.yf, "Ticker", FailingTicker)

    with pytest.raises(
        YahooFinanceIntegrationError,
        match="Unable to load Yahoo Finance data for AAPL",
    ):
        YahooFinanceClient().get_daily_bars(
            "AAPL",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 14),
        )