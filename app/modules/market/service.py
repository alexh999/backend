from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import re
from datetime import date
from functools import lru_cache

from app.core.errors import ApplicationError
from app.integrations.pandaai.client import (
    PandaAIClient,
    PandaAIIntegrationError,
    get_pandaai_client,
)
from app.integrations.pandaai.schemas import (
    PandaAICompanyProfile,
    PandaAIDailyBar,
    PandaAIIndexProfile,
    PandaAIValuationSnapshot,
)
from app.modules.market.schemas import (
    MarketChartCandleData,
    MarketDailyBarData,
    MarketChartPoint,
    MarketChartRangeData,
    MarketIndexOverviewResponse,
    MarketIndexSnapshotGroupResponse,
    MarketIndexSnapshotItemResponse,
    MarketCompanyProfileData,
    MarketStockDetailResponse,
    MarketStockListItemResponse,
    MarketStockStatData,
)

logger = logging.getLogger(__name__)

RANGE_ORDER = ("1W", "1M", "3M", "YTD", "1Y", "ALL")
A_SHARE_WITH_SUFFIX_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|BJ)$", re.IGNORECASE)
A_SHARE_PLAIN_PATTERN = re.compile(r"^\d{6}$")
DEFAULT_MARKET_SYMBOLS = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "TSLA",
    "000001.SZ",
    "300750.SZ",
    "601318.SH",
    "000858.SZ",
    "600519.SH",
    "601398.SH",
    "600036.SH",
)
LIST_HISTORY_DAYS = 20
DETAIL_HISTORY_DAYS = 400
INDEX_LIST_HISTORY_DAYS = 30
MARKET_PREVIEW_COUNT = 6


@dataclass(frozen=True)
class _MarketIndexGroupConfig:
    id: str
    title: str
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class _BuiltMarketIndexItem:
    group_id: str
    item: MarketIndexSnapshotItemResponse


DEFAULT_MARKET_INDEX_GROUPS = (
    _MarketIndexGroupConfig(
        id="mainland-indexes",
        title="Mainland Indexes",
        symbols=("000001.SH", "399001.SZ", "000300.SH", "399006.SZ"),
    ),
    _MarketIndexGroupConfig(
        id="core-a-share-indexes",
        title="Core A-Share Indexes",
        symbols=("000016.SH", "000905.SH", "000852.SH", "000688.SH"),
    ),
)


class MarketStockService:
    def __init__(
        self,
        pandaai_client: PandaAIClient,
        symbols: tuple[str, ...] = DEFAULT_MARKET_SYMBOLS,
    ) -> None:
        self._pandaai_client = pandaai_client
        self._symbols = symbols

    def get_market_index_overview(self) -> MarketIndexOverviewResponse:
        symbols = [
            symbol
            for group in DEFAULT_MARKET_INDEX_GROUPS
            for symbol in group.symbols
        ]
        list_start_date = _recent_history_start_date(INDEX_LIST_HISTORY_DAYS)
        try:
            profiles = self._pandaai_client.get_cn_index_details(symbols)
            histories = self._pandaai_client.get_cn_index_daily_batch(
                symbols,
                start_date=list_start_date,
                end_date=date.today(),
            )
        except PandaAIIntegrationError as exc:
            raise ApplicationError(
                "Unable to load live market indexes.",
                status_code=502,
            ) from exc

        items_by_group: dict[str, list[MarketIndexSnapshotItemResponse]] = {
            group.id: [] for group in DEFAULT_MARKET_INDEX_GROUPS
        }
        for group in DEFAULT_MARKET_INDEX_GROUPS:
            for symbol in group.symbols:
                profile = profiles.get(symbol.upper())
                history = histories.get(symbol.upper(), [])
                built_item = self._build_market_index_item(
                    group_id=group.id,
                    symbol=symbol,
                    profile=profile,
                    history=history,
                )
                if built_item is not None:
                    items_by_group[group.id].append(built_item.item)

        groups: list[MarketIndexSnapshotGroupResponse] = []
        for group in DEFAULT_MARKET_INDEX_GROUPS:
            group_items = items_by_group[group.id]
            if not group_items:
                continue
            groups.append(
                MarketIndexSnapshotGroupResponse(
                    id=group.id,
                    title=group.title,
                    items=group_items,
                )
            )

        if not groups:
            raise ApplicationError("Unable to load live market indexes.", status_code=502)

        preview_items = [item for group in groups for item in group.items][:MARKET_PREVIEW_COUNT]
        return MarketIndexOverviewResponse(
            preview_items=preview_items,
            groups=groups,
        )

    def get_daily_bars(
        self,
        symbol: str,
        limit: int,
    ) -> list[MarketDailyBarData]:
        ticker = _normalize_market_symbol(symbol)

        if not ticker:
            raise ApplicationError("Stock symbol is required.", status_code=400)

        if limit <= 0:
            raise ApplicationError(
                "Daily bar limit must be greater than zero.",
                status_code=400,
            )

        start_date = _recent_history_start_date(max(limit * 2 + 10, 30))

        try:
            if _is_a_share_symbol(ticker):
                history = self._pandaai_client.get_cn_daily(
                    ticker,
                    start_date=start_date,
                    end_date=date.today(),
                )
                latest_bar = self._pandaai_client.get_cn_rt_daily(ticker)
                if latest_bar is not None:
                    history = _merge_latest_bar(history, latest_bar)
            else:
                history = self._pandaai_client.get_us_daily(
                    ticker,
                    start_date=start_date,
                    end_date=date.today(),
                )
        except PandaAIIntegrationError as exc:
            raise ApplicationError(
                f"Unable to load market data for {ticker}.",
                status_code=502,
            ) from exc

        history = sorted(history, key=lambda item: item.trade_date)
        selected_history = history[-limit:]

        result: list[MarketDailyBarData] = []
        for bar in selected_history:
            bar_index = history.index(bar)
            previous_close = (
                history[bar_index - 1].close
                if bar_index > 0
                else None
            )
            result.append(
                MarketDailyBarData(
                    ticker=ticker,
                    trade_date=bar.trade_date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    previous_close=previous_close,
                    volume=bar.volume,
                )
            )

        return result

    def list_stocks(self) -> list[MarketStockListItemResponse]:
        max_workers = min(len(self._symbols), 6) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            items = list(executor.map(self._build_stock_list_item, self._symbols))

        items = [item for item in items if item is not None]
        if not items:
            raise ApplicationError("Unable to load live stock list.", status_code=502)
        return items

    def _build_stock_list_item(self, raw_symbol: str) -> MarketStockListItemResponse | None:
        ticker = _normalize_market_symbol(raw_symbol)
        list_start_date = _recent_history_start_date(LIST_HISTORY_DAYS)
        try:
            if _is_a_share_symbol(ticker):
                profile = self._pandaai_client.get_cn_detail(ticker)
                history = self._pandaai_client.get_cn_daily(
                    ticker,
                    start_date=list_start_date,
                    end_date=date.today(),
                )
                latest_realtime_bar = self._pandaai_client.get_cn_rt_daily(ticker)
                if latest_realtime_bar is not None:
                    history = _merge_latest_bar(history, latest_realtime_bar)
            else:
                profile = self._pandaai_client.get_us_detail(ticker)
                history = self._pandaai_client.get_us_daily(
                    ticker,
                    start_date=list_start_date,
                    end_date=date.today(),
                )
        except PandaAIIntegrationError as exc:
            logger.warning("pandaai_stock_list_skip symbol=%s error=%s", ticker, exc)
            return None

        if len(history) < 2:
            return None

        latest_bar = history[-1]
        previous_bar = history[-2]
        change_percent = round(
            ((latest_bar.close - previous_bar.close) / previous_bar.close) * 100,
            2,
        ) if previous_bar.close else 0.0

        sparkline_values = [round(bar.close, 2) for bar in history[-10:]]
        if len(sparkline_values) < 2:
            return None

        return MarketStockListItemResponse(
            id=ticker.lower(),
            ticker=ticker,
            company_name=profile.company_name,
            exchange_label=profile.exchange_label,
            price_text=f"{latest_bar.close:.2f}",
            latest_close=round(latest_bar.close, 2),
            change_percent=change_percent,
            reference_value=round(previous_bar.close, 2),
            sparkline_values=sparkline_values,
        )

    def _build_market_index_item(
        self,
        *,
        group_id: str,
        symbol: str,
        profile: PandaAIIndexProfile | None,
        history: list[PandaAIDailyBar],
    ) -> _BuiltMarketIndexItem | None:
        ticker = symbol.strip().upper()
        if profile is None:
            logger.warning("pandaai_index_skip symbol=%s error=missing_profile", ticker)
            return None

        if len(history) < 2:
            return None

        latest_bar = history[-1]
        previous_bar = history[-2]
        if previous_bar.close == 0:
            change_percent = 0.0
        else:
            change_percent = round(
                ((latest_bar.close - previous_bar.close) / previous_bar.close) * 100,
                2,
            )

        sparkline_values = [round(bar.close, 2) for bar in history[-10:]]
        if len(sparkline_values) < 2:
            return None

        return _BuiltMarketIndexItem(
            group_id=group_id,
            item=MarketIndexSnapshotItemResponse(
                id=ticker.lower(),
                symbol=ticker,
                display_name=_index_display_name(profile),
                value_text=f"{latest_bar.close:,.2f}",
                latest_close=round(latest_bar.close, 2),
                change_percent=change_percent,
                reference_value=round(previous_bar.close, 2),
                sparkline_values=sparkline_values,
            ),
        )

    def get_stock_detail(self, symbol: str) -> MarketStockDetailResponse:
        ticker = _normalize_market_symbol(symbol)
        if not ticker:
            raise ApplicationError("Stock symbol is required.", status_code=400)

        if _is_a_share_symbol(ticker):
            profile, history, metric_snapshot, currency_symbol = self._load_cn_stock_detail(ticker)
        else:
            profile, history, metric_snapshot, currency_symbol = self._load_us_stock_detail(ticker)

        if len(history) < 2:
            raise ApplicationError(f"No sufficient daily data found for {ticker}.", status_code=404)

        latest_bar = history[-1]
        previous_bar = history[-2]
        change_value = round(latest_bar.close - previous_bar.close, 2)
        change_percent = round((change_value / previous_bar.close) * 100, 2) if previous_bar.close else 0.0

        chart_ranges = _build_chart_ranges(history)
        if not chart_ranges:
            raise ApplicationError(f"No chart data could be built for {ticker}.", status_code=404)

        available_ranges = [item.range for item in chart_ranges]
        default_range = "1W" if "1W" in available_ranges else available_ranges[0]
        stats = _build_stats(
            history,
            latest_bar,
            metric_snapshot,
            currency_symbol=currency_symbol,
        )

        return MarketStockDetailResponse(
            id=ticker.lower(),
            ticker=ticker,
            company_name=profile.company_name,
            exchange_label=profile.exchange_label,
            price_text=f"{latest_bar.close:.2f}",
            latest_close=round(latest_bar.close, 2),
            latest_trading_date=latest_bar.trade_date,
            change_value=change_value,
            change_percent=change_percent,
            change_label="Latest close",
            default_chart_range=default_range,
            available_chart_ranges=available_ranges,
            chart_ranges=chart_ranges,
            stats=stats,
            profile=MarketCompanyProfileData.model_validate(profile.model_dump()),
            news_articles=[],
        )

    def _load_us_stock_detail(
        self,
        ticker: str,
    ) -> tuple[PandaAICompanyProfile, list[PandaAIDailyBar], PandaAIValuationSnapshot | None, str]:
        try:
            profile = self._pandaai_client.get_us_detail(ticker)
            history_start_date = _detail_history_start_date(profile)
            history = self._pandaai_client.get_us_daily(
                ticker,
                start_date=history_start_date,
                end_date=date.today(),
            )
        except PandaAIIntegrationError as exc:
            raise ApplicationError(
                f"Unable to load market data for {ticker}.",
                status_code=502,
            ) from exc

        metric_snapshot: PandaAIValuationSnapshot | None = None
        try:
            metric_snapshot = self._pandaai_client.get_stock_mktfin_metric(ticker)
        except PandaAIIntegrationError as exc:
            logger.warning("pandaai_metric_fallback symbol=%s error=%s", ticker, exc)

        return profile, history, metric_snapshot, "$"

    def _load_cn_stock_detail(
        self,
        ticker: str,
    ) -> tuple[PandaAICompanyProfile, list[PandaAIDailyBar], PandaAIValuationSnapshot | None, str]:
        try:
            profile = self._pandaai_client.get_cn_detail(ticker)
            history_start_date = _detail_history_start_date(profile)
            history = self._pandaai_client.get_cn_daily(
                ticker,
                start_date=history_start_date,
                end_date=date.today(),
            )
            latest_realtime_bar = self._pandaai_client.get_cn_rt_daily(ticker)
        except PandaAIIntegrationError as exc:
            raise ApplicationError(
                f"Unable to load market data for {ticker}.",
                status_code=502,
            ) from exc

        if latest_realtime_bar is not None:
            history = _merge_latest_bar(history, latest_realtime_bar)

        return profile, history, None, "CNY "


def _history_start_date(profile: PandaAICompanyProfile) -> date:
    today = date.today()
    try:
        five_years_ago = today.replace(year=today.year - 5)
    except ValueError:
        five_years_ago = today.replace(month=2, day=28, year=today.year - 5)
    if profile.listed_date is None:
        return five_years_ago
    return max(profile.listed_date, five_years_ago)


def _recent_history_start_date(days: int) -> date:
    return date.fromordinal(date.today().toordinal() - days)


def _detail_history_start_date(profile: PandaAICompanyProfile) -> date:
    return max(_history_start_date(profile), _recent_history_start_date(DETAIL_HISTORY_DAYS))


def _build_chart_ranges(history: list[PandaAIDailyBar]) -> list[MarketChartRangeData]:
    today = date.today()
    ytd_start = date(today.year, 1, 1)
    windows = {
        "1W": history[-5:],
        "1M": history[-21:],
        "3M": history[-63:],
        "YTD": [item for item in history if item.trade_date >= ytd_start],
        "1Y": history[-252:],
        "ALL": history,
    }

    result: list[MarketChartRangeData] = []
    for range_label in RANGE_ORDER:
        bars = windows[range_label]
        if len(bars) < 2:
            continue
        result.append(
            MarketChartRangeData(
                range=range_label,
                line_points=[
                    MarketChartPoint(date=bar.trade_date, close=round(bar.close, 2))
                    for bar in bars
                ],
                candle_points=[
                    MarketChartCandleData(
                        date=bar.trade_date,
                        open=round(bar.open, 2),
                        high=round(bar.high, 2),
                        low=round(bar.low, 2),
                        close=round(bar.close, 2),
                    )
                    for bar in bars
                ],
            )
        )
    return result


def _build_stats(
    history: list[PandaAIDailyBar],
    latest_bar: PandaAIDailyBar,
    metric_snapshot: PandaAIValuationSnapshot | None,
    *,
    currency_symbol: str,
) -> list[MarketStockStatData]:
    trailing_year = history[-252:] if len(history) >= 252 else history
    trailing_month = history[-30:] if len(history) >= 30 else history

    high_52w = max(bar.high for bar in trailing_year)
    low_52w = min(bar.low for bar in trailing_year)
    average_volume = _average([bar.volume for bar in trailing_month if bar.volume is not None])

    market_cap = metric_snapshot.market_cap if metric_snapshot is not None else None
    pe_ratio = metric_snapshot.pe_ratio if metric_snapshot is not None else None
    dividend_yield = metric_snapshot.dividend_yield if metric_snapshot is not None else None

    return [
        MarketStockStatData(label="Open", value=_format_currency(latest_bar.open, currency_symbol)),
        MarketStockStatData(label="Today's High", value=_format_currency(latest_bar.high, currency_symbol)),
        MarketStockStatData(label="Today's Low", value=_format_currency(latest_bar.low, currency_symbol)),
        MarketStockStatData(label="52 Wk High", value=_format_currency(high_52w, currency_symbol)),
        MarketStockStatData(label="52 Wk Low", value=_format_currency(low_52w, currency_symbol)),
        MarketStockStatData(label="Volume", value=_format_compact_number(latest_bar.volume)),
        MarketStockStatData(label="Average Volume", value=_format_compact_number(average_volume)),
        MarketStockStatData(label="Market Cap", value=_format_compact_currency(market_cap, currency_symbol)),
        MarketStockStatData(label="P/E Ratio", value=_format_decimal(pe_ratio)),
        MarketStockStatData(label="Div/Yield", value=_format_decimal(dividend_yield)),
    ]


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _format_currency(value: float | None, currency_symbol: str) -> str:
    if value is None:
        return "--"
    return f"{currency_symbol}{value:,.2f}"


def _format_decimal(value: float | None) -> str:
    if value is None:
        return "--"
    text = f"{value:.3f}"
    return text.rstrip("0").rstrip(".")


def _format_compact_currency(value: float | None, currency_symbol: str) -> str:
    if value is None:
        return "--"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000_000:
        return f"{currency_symbol}{value / 1_000_000_000_000:.2f}T"
    if abs_value >= 1_000_000_000:
        return f"{currency_symbol}{value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{currency_symbol}{value / 1_000_000:.2f}M"
    return f"{currency_symbol}{value:,.0f}"


def _format_compact_number(value: float | None) -> str:
    if value is None:
        return "--"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def _normalize_market_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not A_SHARE_PLAIN_PATTERN.fullmatch(normalized):
        return normalized

    if normalized.startswith(("5", "6", "9")):
        return f"{normalized}.SH"
    if normalized.startswith(("4", "8")):
        return f"{normalized}.BJ"
    return f"{normalized}.SZ"


def _is_a_share_symbol(symbol: str) -> bool:
    return bool(A_SHARE_WITH_SUFFIX_PATTERN.fullmatch(symbol))


def _merge_latest_bar(history: list[PandaAIDailyBar], latest_bar: PandaAIDailyBar) -> list[PandaAIDailyBar]:
    merged_history = [bar for bar in history if bar.trade_date != latest_bar.trade_date]
    merged_history.append(latest_bar)
    merged_history.sort(key=lambda item: item.trade_date)
    return merged_history


def _index_display_name(profile: PandaAIIndexProfile) -> str:
    return profile.index_name.strip() or profile.symbol.upper()


@lru_cache
def get_market_stock_service() -> MarketStockService:
    return MarketStockService(get_pandaai_client())
