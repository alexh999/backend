from __future__ import annotations

from typing import List, Optional, Union

import pandas as pd
from panda_data.exceptions import ServiceError, ServiceErrorCode

from panda_data.core.service import fetch_dataframe, request_service
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_date_format,
    validate_date_range,
    validate_param_types,
    validate_exchange,
    validate_is_trading_day,
    validate_no_duplicates, validate_not_empty, validate_positive_integer, validate_extra_params, validate_symbol_format
)

CALENDAR_ENDPOINT = "/tradeCalendar"

STOCK_ENDPOINT = "/stock"
PATH_GET_STOCK_SPECIAL_TREATMENT = "/getStockSpecialTreatmentData"
PATH_GET_TRADING_STOCK_LIST = "/getTradingStockList"
PATH_GET_CURRENCY_DATA = "/getCurrencyData"


def _normalise_list(value: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value] if value != "" else None


def get_trade_cal(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exchange: Optional[str] = "SH",
        is_trading_day: Optional[int] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取交易日历

    Args:
        start_date (str, optional): 开始日期，格式为 YYYYMMDD，非必填
        end_date (str, optional): 结束日期，格式为 YYYYMMDD，非必填
        exchange (str, optional): 交易所代码，默认为 "SH"，目前支持"SH"，"HK"和"US"，非必填
        is_trading_day (int, optional): 是否为交易日，1=交易日，0=非交易日，None=全部，非必填
        fields (str or list of str, optional): 需要返回的字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_trade_cal(
        ...     start_date="20250101",
        ...     end_date="20250115",
        ...     exchange="SH",
        ...     is_trading_day=None,
        ...     fields=[],
        ... )
    """
    validate_extra_params(kwargs)
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 验证交易所参数
    validated_exchange = validate_exchange(exchange, "exchange") if exchange is not None else exchange

    # 验证是否为交易日参数
    validated_is_trading_day = validate_is_trading_day(is_trading_day,
                                                       "is_trading_day") if is_trading_day is not None else is_trading_day

    # 验证fields参数类型
    params = {'fields': fields}
    type_config = {'fields': str}
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['fields']
    )

    # 验证fields参数中的重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_exchange is not None:
        payload["exchange"] = validated_exchange
    if validated_is_trading_day is not None:
        payload["isTradingDay"] = validated_is_trading_day
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    path = "/getTradeCalendarData"
    df = fetch_dataframe(build_endpoint(CALENDAR_ENDPOINT, path), payload=payload)

    if not df.empty and "nature_date" in df.columns:
        df = df.sort_values(by="nature_date", ascending=True).reset_index(drop=True)

    # 清理内部列
    if "_id" in df.columns:
        df = df.drop(columns=["_id"])
    if "month" in df.columns:
        df = df.drop(columns=["month"])
    if "insert_time" in df.columns:
        df = df.drop(columns=["insert_time"])

    return df


def get_prev_trade_date(
        date: str,
        exchange: Optional[str] = "SH",
        n: Optional[int] = 1,
) -> str:
    """
    获取指定日期的前第n个交易日

    Args:
        date (str): 基准日期，格式为 "YYYYMMDD"，非必填
        exchange (str, optional): 交易所代码，默认为 "SH"，目前支持"SH"，"HK"和"US"，非必填
        n (int, optional): 前第n个交易日，默认为1，非必填

    Returns:
        str

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_prev_trade_date(
        ...     date="20250102",
        ...     exchange="SH",
        ...     n=5,
        ... )
    """
    validate_not_empty(date, "date")
    # 验证日期格式
    validated_date = validate_date_format(date, "date")

    # 验证交易所参数
    validated_exchange = validate_exchange(exchange, "exchange") if exchange is not None else exchange

    # 验证n参数为正整数
    validated_n = validate_positive_integer(n, "n") if n is not None else n

    payload = {"date": validated_date, "n": validated_n}
    if validated_exchange is not None:
        payload["exchange"] = validated_exchange
    path = "/getPreviousNthTradingDay"
    result = request_service(build_endpoint(CALENDAR_ENDPOINT, path), payload=payload)
    return str(result.get("date")) if result is not None else None


def get_last_trade_date(exchange: Optional[str] = "SH") -> Optional[str]:
    """
    获取最新交易日

    Args:
        exchange (str, optional): 交易所代码，默认为 "SH"，目前支持"SH"，"HK"和"US"，非必填

    Returns:
        str or None

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_last_trade_date(
        ...     exchange="SH"
        ... )
    """
    # 验证交易所参数
    validated_exchange = validate_exchange(exchange, "exchange") if exchange is not None else exchange

    payload = {}
    if validated_exchange is not None:
        payload["exchange"] = validated_exchange
    path = "/getLatestTradingDay"
    result = request_service(build_endpoint(CALENDAR_ENDPOINT, path), payload=payload)
    return str(result.get("date")) if result is not None else None


def get_stock_status_change(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取合约特殊处理数据

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        start_date (str, optional): 开始日期，格式为 YYYYMMDD，非必填
        end_date (str, optional): 结束日期，格式为 YYYYMMDD，非必填
        fields (str or list of str, optional): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_status_change(
        ...     symbol="002217.SZ",
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=[],
        ... )
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    # 2. 验证参数类型
    params = {
        'symbol': symbol,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'fields']
    )

    # 3. 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 6. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_SPECIAL_TREATMENT), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_trade_list(
        date: Union[str, List[str]],
        exchange: Optional[str] = "SH",
        **kwargs
) -> pd.DataFrame:
    """
    获取指定日期的在售股票列表

    Args:
        date (str or list of str): 日期，格式为 YYYYMMDD，非必填
        exchange (str, optional): 交易所代码，默认为 "SH"，目前支持"SH"，"HK"和"US"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_trade_list(
        ...     date="20251211"
        ... )
    """
    # 验证额外参数
    validate_extra_params(kwargs)
    # 1. 验证date参数不为空
    from panda_data.utils.param_check_utils import validate_not_empty
    validate_not_empty(date, "date")

    # 2. 将date转换为列表形式以便统一处理
    if isinstance(date, str):
        date_list = [date]
    else:
        date_list = date

    # 3. 验证列表不为空（处理包含空字符串的列表）
    if len(date_list) == 0 or all(d == "" for d in date_list):
        from panda_data.exceptions import ServiceError, ServiceErrorCode
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] date参数不能为空列表或全空字符串列表"
        )

    # 4. 验证date列表中是否有重复值
    from panda_data.utils.param_check_utils import validate_no_duplicates
    validate_no_duplicates(date_list, "date")

    # 5. 验证每个日期的格式
    validated_dates = []
    for d in date_list:
        validated_date = validate_date_format(d, "date")
        if validated_date is not None:  # 确保不是None（即非空）
            validated_dates.append(validated_date)

    # 6. 验证交易所参数
    validated_exchange = validate_exchange(exchange, "exchange") if exchange is not None else exchange

    payload = {}
    if validated_dates:
        payload["date"] = validated_dates
    if validated_exchange is not None:
        payload["exchange"] = validated_exchange

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_TRADING_STOCK_LIST), payload=payload)
    if not df.empty:
        sort_cols = [col for col in ["date", "symbol"] if col in df.columns]
        if sort_cols:
            ascending = [False if col == "date" else True for col in sort_cols]
            df = df.sort_values(by=sort_cols, ascending=ascending).reset_index(drop=True)
    return df


def get_currency(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取汇率数据

    Args:
        start_date (Optional[str]): 开始日期 YYYYMMDD，非必填
        end_date (Optional[str]): 结束日期 YYYYMMDD，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填

    Returns:
    pd.DataFrame


    请求示例:
    import tqx_data
    result = tqx_data.get_currency(
    field=[],
    )
    print(result)
    """
    validate_extra_params(kwargs)

    # 验证fields参数类型
    params = {'fields': fields}
    type_config = {'fields': str}
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['fields']
    )

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    if validated_start_date is not None and validated_end_date is not None:
        validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(CALENDAR_ENDPOINT, PATH_GET_CURRENCY_DATA), payload=payload)

    # 返回列优先 date 在前，按 date 升序（最新一条时后端已返回单行）
    if not df.empty and "date" in df.columns:
        priority_cols = ["date"]
        other_cols = [col for col in df.columns if col not in priority_cols]
        df = df[priority_cols + other_cols]
        if validated_start_date is not None or validated_end_date is not None:
            df = df.sort_values(by="date", ascending=True).reset_index(drop=True)

    return df
