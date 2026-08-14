from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import re

from app.core.errors import ApplicationError


SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+(?:\.[A-Z]{1,4})?$")


@dataclass(frozen=True)
class PaperTradingQuote:
    symbol: str
    name: str
    price: Decimal
    currency: str
    timestamp: datetime


class PaperTradingQuoteProvider:
    def get_quote(self, symbol: str) -> PaperTradingQuote:
        raise NotImplementedError


class MockPaperTradingQuoteProvider(PaperTradingQuoteProvider):
    def __init__(self, quotes: dict[str, PaperTradingQuote] | None = None) -> None:
        now = datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc)
        self._quotes = quotes or {
            "00700.HK": PaperTradingQuote(
                symbol="00700.HK",
                name="Tencent Holdings",
                price=Decimal("380.00"),
                currency="HKD",
                timestamp=now,
            ),
            "AAPL": PaperTradingQuote(
                symbol="AAPL",
                name="Apple Inc.",
                price=Decimal("215.20"),
                currency="USD",
                timestamp=now,
            ),
            "600519.SH": PaperTradingQuote(
                symbol="600519.SH",
                name="Kweichow Moutai",
                price=Decimal("1505.00"),
                currency="CNY",
                timestamp=now,
            ),
            "000001.SZ": PaperTradingQuote(
                symbol="000001.SZ",
                name="Ping An Bank",
                price=Decimal("12.63"),
                currency="CNY",
                timestamp=now,
            ),
        }

    def get_quote(self, symbol: str) -> PaperTradingQuote:
        normalized = normalize_symbol(symbol)
        quote = self._quotes.get(normalized)
        if quote is None:
            raise ApplicationError(
                f"Unknown paper trading symbol: {normalized}.",
                status_code=404,
            )
        return quote


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.startswith("$"):
        normalized = normalized[1:]
    if re.fullmatch(r"\d{5}", normalized):
        normalized = f"{normalized}.HK"
    elif re.fullmatch(r"\d{6}", normalized):
        if normalized.startswith(("5", "6", "9")):
            normalized = f"{normalized}.SH"
        elif normalized.startswith(("4", "8")):
            normalized = f"{normalized}.BJ"
        else:
            normalized = f"{normalized}.SZ"
    if not normalized or not SYMBOL_PATTERN.fullmatch(normalized):
        raise ApplicationError("Malformed paper trading symbol.", status_code=422)
    return normalized


def get_paper_trading_quote_provider() -> PaperTradingQuoteProvider:
    return MockPaperTradingQuoteProvider()
