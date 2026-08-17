from concurrent.futures import ThreadPoolExecutor
import re

from app.core.errors import ApplicationError
from app.modules.quant.factor_ic import FactorIcResult
from app.modules.quant.factor_ic_analysis import calculate_factor_ic_analysis
from app.modules.quant.factor_scores import SUPPORTED_FACTOR_IDS
from app.modules.quant.market_data import (
    MarketDataProvider,
    normalize_daily_bars,
)
from app.modules.quant.schemas import (
    FactorIcAnalysisRequest,
    FactorIcAnalysisResponse,
    FactorIcPeriodResponse,
    FactorIcResultResponse,
    QuantMarket,
    DailyBar,
)

A_SHARE_SYMBOL_PATTERN = re.compile(
    r"^\d{6}(?:\.(?:SH|SZ|BJ))?$",
    re.IGNORECASE,
)
HONG_KONG_SYMBOL_PATTERN = re.compile(
    r"^\d{1,5}\.HK$",
    re.IGNORECASE,
)
UNITED_STATES_SYMBOL_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9.-]*$",
    re.IGNORECASE,
)


def analyze_real_factor_ic(
    request: FactorIcAnalysisRequest,
    market_data: MarketDataProvider,
) -> FactorIcAnalysisResponse:
    _validate_symbols_for_market(
        market=request.market,
        symbols=request.symbols,
    )

    worker_count = min(4, len(request.symbols))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        loaded_bars = executor.map(
            lambda symbol: _load_stock_bars(
                market_data=market_data,
                symbol=symbol,
                limit=request.history_limit,
            ),
            request.symbols,
        )

        bars_by_stock = dict(loaded_bars)

    factor_results = tuple(
        _build_factor_response(
            calculate_factor_ic_analysis(
                factor_id=factor_id,
                bars_by_stock=bars_by_stock,
                holding_period=request.holding_period,
                minimum_lookback=request.minimum_lookback,
                minimum_sample_size=request.minimum_sample_size,
            )
        )
        for factor_id in SUPPORTED_FACTOR_IDS
    )

    return FactorIcAnalysisResponse(
        market=request.market,
        symbols=request.symbols,
        history_limit=request.history_limit,
        holding_period=request.holding_period,
        minimum_lookback=request.minimum_lookback,
        minimum_sample_size=request.minimum_sample_size,
        factor_results=factor_results,
    )


def _load_stock_bars(
    *,
    market_data: MarketDataProvider,
    symbol: str,
    limit: int,
) -> tuple[str, tuple[DailyBar, ...]]:
    bars = normalize_daily_bars(
        market_data.get_daily_bars(
            symbol=symbol,
            limit=limit,
        )
    )

    if not bars:
        raise ApplicationError(
            f"No market data is available for {symbol}.",
            status_code=404,
        )

    return symbol, bars


def _validate_symbols_for_market(
    market: QuantMarket,
    symbols: tuple[str, ...],
) -> None:
    pattern = {
        QuantMarket.A_SHARE: A_SHARE_SYMBOL_PATTERN,
        QuantMarket.HONG_KONG: HONG_KONG_SYMBOL_PATTERN,
        QuantMarket.UNITED_STATES: UNITED_STATES_SYMBOL_PATTERN,
    }[market]

    invalid_symbols = tuple(
        symbol
        for symbol in symbols
        if pattern.fullmatch(symbol) is None
    )

    if invalid_symbols:
        joined_symbols = ", ".join(invalid_symbols)

        raise ApplicationError(
            f"Stock symbols do not match the selected market: {joined_symbols}.",
            status_code=422,
        )


def _build_factor_response(
    result: FactorIcResult,
) -> FactorIcResultResponse:
    return FactorIcResultResponse(
        factor_id=result.factor_id,
        periods=tuple(
            FactorIcPeriodResponse(
                date=period.date,
                sample_size=period.sample_size,
                information_coefficient=period.information_coefficient,
                rank_information_coefficient=(
                    period.rank_information_coefficient
                ),
            )
            for period in result.periods
        ),
        available_period_count=len(result.available_periods),
        average_information_coefficient=(
            result.average_information_coefficient
        ),
        average_rank_information_coefficient=(
            result.average_rank_information_coefficient
        ),
        positive_information_coefficient_rate=(
            result.positive_information_coefficient_rate
        ),
        positive_rank_information_coefficient_rate=(
            result.positive_rank_information_coefficient_rate
        ),
        ic_information_ratio=result.ic_information_ratio,
        rank_ic_information_ratio=result.rank_ic_information_ratio,
        average_sample_size=result.average_sample_size,
        reliability=result.reliability.value,
    )
