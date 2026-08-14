from __future__ import annotations

import math
import os
from datetime import date, timedelta

os.environ.setdefault("YF_DISABLE_CURL_CFFI", "1")

import yfinance as yf

from app.integrations.yahoo_finance.schemas import YahooFinanceDailyBar


class YahooFinanceIntegrationError(Exception):
    """Raised when Yahoo Finance market data cannot be loaded."""


class YahooFinanceClient:
    def get_daily_bars(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[YahooFinanceDailyBar]:
        normalized_symbol = _normalize_app_symbol(symbol)

        if not normalized_symbol:
            raise ValueError("Stock symbol cannot be empty.")

        if start_date > end_date:
            raise ValueError("Start date cannot be later than end date.")

        yahoo_symbol = _to_yahoo_symbol(normalized_symbol)

        try:
            history = yf.Ticker(yahoo_symbol).history(
                start=start_date,
                end=end_date + timedelta(days=1),
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:
            raise YahooFinanceIntegrationError(
                f"Unable to load Yahoo Finance data for {normalized_symbol}."
            ) from exc

        if history.empty:
            raise YahooFinanceIntegrationError(
                f"Yahoo Finance returned no data for {normalized_symbol}."
            )

        bars: list[YahooFinanceDailyBar] = []

        for index, row in history.iterrows():
            open_price = _finite_float(row.get("Open"))
            high_price = _finite_float(row.get("High"))
            low_price = _finite_float(row.get("Low"))
            close_price = _finite_float(row.get("Close"))

            if (
                open_price is None
                or high_price is None
                or low_price is None
                or close_price is None
            ):
                continue

            trade_date = index.date() if hasattr(index, "date") else index

            bars.append(
                YahooFinanceDailyBar(
                    symbol=normalized_symbol,
                    trade_date=trade_date,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=_finite_float(row.get("Volume")),
                )
            )

        if not bars:
            raise YahooFinanceIntegrationError(
                f"Yahoo Finance returned no valid daily bars for {normalized_symbol}."
            )

        bars.sort(key=lambda bar: bar.trade_date)
        return bars


def _normalize_app_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()

    if not normalized:
        return ""

    if normalized.endswith(".SS"):
        return f"{normalized[:-3]}.SH"

    if len(normalized) == 6 and normalized.isdigit():
        if normalized.startswith(("5", "6", "9")):
            return f"{normalized}.SH"

        if normalized.startswith(("4", "8")):
            return f"{normalized}.BJ"

        return f"{normalized}.SZ"

    return normalized


def _to_yahoo_symbol(symbol: str) -> str:
    if symbol.endswith(".SH"):
        return f"{symbol[:-3]}.SS"

    return symbol


def _finite_float(value: object) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None

    return converted if math.isfinite(converted) else None