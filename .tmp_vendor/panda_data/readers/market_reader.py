from __future__ import annotations

from typing import List, Optional, Tuple, Union

import pandas as pd

from panda_data.core.service import fetch_dataframe
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_param_types,
    validate_symbol_format,
    validate_future_symbol_format,
    validate_no_duplicates,
    validate_date_format,
    validate_market_data_type,
    validate_indicator,
    validate_bool_type,
    validate_time_zone,
    validate_frequency,
    validate_index_frequency, validate_date_range, validate_date_interval, validate_not_empty, validate_extra_params,
    validate_data_volume_limit, validate_hk_symbol_format
)

MULTI_ENDPOINT = "/multi"
INDEX_ENDPOINT = "/index"
FUTURE_ENDPOINT = "/future"

PATH_GET_MARKET_DATA = "/getMultiMarketData"
PATH_GET_STOCK_DAILY = "/getStockDaily"
PATH_GET_INDEX_DAILY = "/getIndexDaily"
PATH_GET_FUTURE_DAILY = "/getFutureDaily"
PATH_GET_STOCK_DAILY_POST = "/getStockDailyPost"
PATH_GET_STOCK_DAILY_PRE = "/getStockDailyPre"
PATH_GET_STOCK_RT_DAILY = "/getStockRtDaily"
PATH_GET_MARKET_MIN_DATA = "/getMultiMarketMinData"
PATH_GET_STOCK_MIN = "/getStockMin"
PATH_GET_INDEX_MIN = "/getIndexMin"
PATH_GET_FUTURE_MIN = "/getFutureMin"
PATH_GET_STOCK_RT_MIN = "/getStockRtMin"
# 期货 / 指数 分钟 K 的 path 可与多行情一致，也可通过环境变量覆盖
PATH_GET_FUTURE_MARKET_MIN_DATA = "/getMultiMarketMinData"
PATH_GET_INDEX_MARKET_MIN_DATA = "/getMultiMarketMinData"

TICK_ENDPOINT = "/tick"
FUTURE_TICK_ENDPOINT = "/future"
PATH_GET_STOCK_HK_TICK = "/getStockHKTickData"
PATH_GET_FUTURE_TICK = "/getFutureTickData"


def _normalise_symbols(symbol: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if symbol is None or symbol == "":
        return None
    if isinstance(symbol, list):
        return symbol
    return [symbol]


def get_market_data(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        type: Optional[str] = "stock",
        fields: Optional[Union[str, List[str]]] = None,
        indicator: Optional[str] = "",
        st: Optional[bool] = True,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
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

    # 验证symbol格式（根据type类型）
    if validated_params['symbol'] is not None:
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

        # 根据type类型验证symbol格式
        validated_type = validate_market_data_type(type, "type")
        if validated_type == "stock":
            validate_symbol_format(validated_params['symbol'])
        elif validated_type == "future":
            validate_future_symbol_format(validated_params['symbol'])
        elif validated_type == "index":
            # 对于index类型，暂时不进行特殊格式验证
            pass

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 验证日期间隔不能超过5年
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    # 验证type参数
    validated_type = validate_market_data_type(type, "type")

    # 验证indicator参数
    validated_indicator = validate_indicator(indicator, "indicator")

    # 验证st参数
    validated_st = validate_bool_type(st, "st") if st is not None else st

    if validated_indicator == "000985":
        validated_indicator = ""

    payload = {"type": validated_type}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbols"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_indicator:
        payload["indicator"] = validated_indicator
    if validated_st is not None:
        payload["st"] = validated_st

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_MARKET_DATA), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_daily(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        indicator: Optional[str] = "",
        st: Optional[bool] = True,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股日线数据

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，与结束日期间不超过5年，非必填
        end_date (str): 结束日期，格式为 YYYYMMDD，与开始日期间不超过5年，非必填
        fields (str or list of str, optional): 返回字段，非必填
        indicator (str, optional): 股票池，默认为空表示查询所有，非必填
        st (bool, optional): 是否包含ST股，默认True表示包含，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_daily(
        ...     symbol=["000001.SZ"],
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=[],
        ...     indicator="000300",
        ...     st=True,
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
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

    # 股票日频接口固定按股票代码格式校验
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 验证日期间隔不能超过5年
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    # 验证indicator参数
    validated_indicator = validate_indicator(indicator, "indicator")

    # 验证st参数
    validated_st = validate_bool_type(st, "st") if st is not None else st

    if validated_indicator == "000985":
        validated_indicator = ""

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbols"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_indicator:
        payload["indicator"] = validated_indicator
    if validated_st is not None:
        payload["st"] = validated_st

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_STOCK_DAILY), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_rt_daily(
        symbol: Optional[Union[str, List[str]]] = "",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股当日日线

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        fields (str or list of str, optional): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_rt_daily(
        ...     symbol=[],
        ...     fields=[],
        ... )
    """

    validate_extra_params(kwargs)
    # 验证参数类型
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

    # 股票实时日频接口固定按股票代码格式校验
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_STOCK_RT_DAILY), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_index_daily(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取指数日线

    Args:
        symbol (str or list of str, optional): 指数代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，与结束日期间不超过5年，非必填
        end_date (str): 结束日期，格式为 YYYYMMDD，与开始日期间不超过5年，非必填
        fields (str or list of str, optional): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_index_daily(
        ...     symbol=["000001.SH"],
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=[],
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
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

    # 验证symbol列表中是否有重复值；index类型暂时不进行特殊格式验证
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 验证日期间隔不能超过5年
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbols"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_INDEX_DAILY), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_daily(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货日线

    Args:
        symbol (str or list of str, optional): 期货代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，与结束日期间不超过5年，非必填
        end_date (str): 结束日期，格式为 YYYYMMDD，与开始日期间不超过5年，非必填
        fields (str or list of str, optional): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_daily(
        ...     symbol=["A_DOMINANT.DCE"],
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=[],
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
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

    # 期货日频接口固定按期货代码格式校验
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_future_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 验证日期间隔不能超过5年
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbols"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_FUTURE_DAILY), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_daily_post(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        indicator: Optional[str] = "",
        st: Optional[bool] = True,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股后复权日线数据

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，与结束日期间不超过5年，必填
        end_date (str): 结束日期，格式为 YYYYMMDD，与开始日期间不超过5年，必填
        fields (str or list of str, optional): 返回字段，非必填
        indicator (str, optional): 股票池，默认为空表示查询所有，非必填
        st (bool, optional): 是否包含ST股，默认True表示包含，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_daily_post(
        ...     symbol=["000001.SZ"],
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=[],
        ...     indicator="000300",
        ...     st=True,
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
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

    # 复权行情只有股票，固定按股票代码格式校验
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 验证日期间隔不能超过5年
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    # 验证indicator参数
    validated_indicator = validate_indicator(indicator, "indicator")

    # 验证st参数
    validated_st = validate_bool_type(st, "st") if st is not None else st

    if validated_indicator == "000985":
        validated_indicator = ""

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbols"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_indicator:
        payload["indicator"] = validated_indicator
    if validated_st is not None:
        payload["st"] = validated_st

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_STOCK_DAILY_POST), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_daily_pre(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        indicator: Optional[str] = "",
        st: Optional[bool] = True,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股前复权日线数据

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，与结束日期间不超过5年，必填
        end_date (str): 结束日期，格式为 YYYYMMDD，与开始日期间不超过5年，必填
        fields (str or list of str, optional): 返回字段，非必填
        indicator (str, optional): 股票池，默认为空表示查询所有，非必填
        st (bool, optional): 是否包含ST股，默认True表示包含，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_daily_pre(
        ...     symbol=["000001.SZ"],
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=[],
        ...     indicator="000300",
        ...     st=True,
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
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

    # 复权行情只有股票，固定按股票代码格式校验
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 验证日期间隔不能超过5年
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    # 验证indicator参数
    validated_indicator = validate_indicator(indicator, "indicator")

    # 验证st参数
    validated_st = validate_bool_type(st, "st") if st is not None else st

    if validated_indicator == "000985":
        validated_indicator = ""

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbols"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_indicator:
        payload["indicator"] = validated_indicator
    if validated_st is not None:
        payload["st"] = validated_st

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_STOCK_DAILY_PRE), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_rt_min(
        symbol: Optional[Union[str, List[str]]] = "",
        fields: Optional[Union[str, List[str]]] = None,
        time_zone: Optional[Tuple[str, str]] = None,
        frequency: Optional[str] = "1m",
        **kwargs
) -> pd.DataFrame:
    """
    获取A股当日分钟线

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        fields (str or list of str, optional): 返回字段，非必填
        time_zone (tuple, optional): 时间段过滤，格式为("HH:MM", "HH:MM")，例如("10:00", "23:00")，非必填
        frequency (str, optional): 频率，支持 "1m"，默认为"1m"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_rt_min(
        ...     symbol="000001.SZ",
        ...     fields=["symbol", "date", "num_trades", "amount", "volume"],
        ...     time_zone=("10:00", "11:00"),
        ... )
    """

    validate_extra_params(kwargs)
    # 验证参数类型
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

    # 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证time_zone参数
    validated_time_zone = validate_time_zone(time_zone, "timeZone") if time_zone is not None else time_zone

    # 验证frequency参数
    validated_frequency = validate_frequency(frequency, "frequency")

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_time_zone is not None:
        payload["timeZone"] = list(validated_time_zone)
    if validated_frequency:
        payload["frequency"] = validated_frequency

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_STOCK_RT_MIN), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_min(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        time_zone: Optional[Tuple[str, str]] = None,
        frequency: Optional[str] = "1m",
        **kwargs
) -> pd.DataFrame:
    """
    获取A股分钟线

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD，必填
        fields (str or list of str, optional): 返回字段，非必填
        time_zone (tuple, optional): 时间段过滤，格式为("HH:MM", "HH:MM")，例如("10:00", "23:00")，非必填
        frequency (str, optional): 频率，支持 "1m", "5m", "15m", "60m"，默认为"1m"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_min(
        ...     symbol="000001.SZ",
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=["symbol", "date", "num_trades", "amount", "volume"],
        ...     frequency="1m",
        ...     time_zone=("10:00", "11:00"),
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
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

    # 股票分钟线接口固定按股票代码格式校验
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 验证time_zone参数
    validated_time_zone = validate_time_zone(time_zone, "timeZone") if time_zone is not None else time_zone

    # 验证frequency参数
    validated_frequency = validate_frequency(frequency, "frequency")

    # 添加数据量限制验证
    validate_data_volume_limit(
        validated_params['symbol'] if validated_params['symbol'] != [""] else None,
        validated_start_date,
        validated_end_date,
        "stock",
        validated_time_zone,
        validated_frequency
    )

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_time_zone is not None:
        payload["timeZone"] = list(validated_time_zone)
    if validated_frequency:
        payload["frequency"] = validated_frequency

    # 排序已在读取 Parquet 时通过 DuckDB ORDER BY 完成，返回的 DataFrame 索引已是 0..n-1，无需 reset_index
    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_STOCK_MIN), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_index_min(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        time_zone: Optional[Tuple[str, str]] = None,
        frequency: Optional[str] = "1m",
        **kwargs
) -> pd.DataFrame:
    """
    获取指数分钟线

    Args:
        symbol (str or list of str, optional): 指数代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD，必填
        fields (str or list of str, optional): 返回字段，非必填
        time_zone (tuple, optional): 时间段过滤，格式为("HH:MM", "HH:MM")，例如("10:00", "23:00")，非必填
        frequency (str, optional): 频率，支持 "1m"，默认为"1m"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_index_min(
        ...     symbol="000001.SH",
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=["symbol", "date", "amount", "volume"],
        ...     frequency="1m",
        ...     time_zone=("10:00", "11:00"),
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
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

    # 验证symbol列表中是否有重复值；index类型暂时不进行特殊格式验证
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 验证time_zone参数
    validated_time_zone = validate_time_zone(time_zone, "timeZone") if time_zone is not None else time_zone

    # 验证frequency参数
    validated_frequency = validate_index_frequency(frequency, "frequency")

    # 添加数据量限制验证
    validate_data_volume_limit(
        validated_params['symbol'] if validated_params['symbol'] != [""] else None,
        validated_start_date,
        validated_end_date,
        "index",
        validated_time_zone,
        validated_frequency
    )

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_time_zone is not None:
        payload["timeZone"] = list(validated_time_zone)
    if validated_frequency:
        payload["frequency"] = validated_frequency

    # 排序已在读取 Parquet 时通过 DuckDB ORDER BY 完成，返回的 DataFrame 索引已是 0..n-1，无需 reset_index
    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_INDEX_MIN), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_min(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[Union[str, List[str]]] = None,
        time_zone: Optional[Tuple[str, str]] = None,
        frequency: Optional[str] = "1m",
        **kwargs
) -> pd.DataFrame:
    """
    获取期货分钟线

    Args:
        symbol (str or list of str, optional): 期货代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD，必填
        fields (str or list of str, optional): 返回字段，非必填
        time_zone (tuple, optional): 时间段过滤，格式为("HH:MM", "HH:MM")，例如("10:00", "23:00")，非必填
        frequency (str, optional): 频率，支持 "1m", "5m", "15m", "60m"，默认为"1m"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_min(
        ...     symbol="A2501.DCE",
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=["symbol", "date", "amount", "volume"],
        ...     frequency="1m",
        ...     time_zone=("10:00", "11:00"),
        ... )
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
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

    # 期货分钟线接口固定按期货代码格式校验
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_future_symbol_format(validated_params['symbol'])

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 验证time_zone参数
    validated_time_zone = validate_time_zone(time_zone, "timeZone") if time_zone is not None else time_zone

    # 验证frequency参数
    validated_frequency = validate_frequency(frequency, "frequency")

    # 添加数据量限制验证
    validate_data_volume_limit(
        validated_params['symbol'] if validated_params['symbol'] != [""] else None,
        validated_start_date,
        validated_end_date,
        "future",
        validated_time_zone,
        validated_frequency
    )

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_time_zone is not None:
        payload["timeZone"] = list(validated_time_zone)
    if validated_frequency:
        payload["frequency"] = validated_frequency

    # 排序已在读取 Parquet 时通过 DuckDB ORDER BY 完成，返回的 DataFrame 索引已是 0..n-1，无需 reset_index
    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_FUTURE_MIN), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_market_min_data(
        symbol: Optional[Union[str, List[str]]] = "",
        start_date: str = "",
        end_date: str = "",
        symbol_type: Optional[str] = "stock",
        fields: Optional[Union[str, List[str]]] = None,
        time_zone: Optional[Tuple[str, str]] = None,
        frequency: Optional[str] = "1m",
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
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

    # 验证symbol格式（根据symbol_type类型）
    if validated_params['symbol'] is not None:
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

        # 根据symbol_type类型验证symbol格式
        validated_symbol_type = validate_market_data_type(symbol_type, "symbolType")
        if validated_symbol_type == "stock":
            validate_symbol_format(validated_params['symbol'])
        elif validated_symbol_type == "future":
            validate_future_symbol_format(validated_params['symbol'])
        elif validated_symbol_type == "index":
            # 对于index类型，暂时不进行特殊格式验证
            pass

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 验证symbol_type参数
    validated_symbol_type = validate_market_data_type(symbol_type, "symbolType")

    # 验证time_zone参数
    validated_time_zone = validate_time_zone(time_zone, "timeZone") if time_zone is not None else time_zone

    # 验证frequency参数（根据symbol_type）
    if validated_symbol_type == "index":
        validated_frequency = validate_index_frequency(frequency, "frequency")
    else:
        validated_frequency = validate_frequency(frequency, "frequency")

    # 添加数据量限制验证
    validate_data_volume_limit(
        validated_params['symbol'] if validated_params['symbol'] != [""] else None,
        validated_start_date,
        validated_end_date,
        validated_symbol_type,
        validated_time_zone,
        validated_frequency
    )

    payload = {"symbolType": validated_symbol_type}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_time_zone is not None:
        payload["timeZone"] = list(validated_time_zone)
    if validated_frequency:
        payload["frequency"] = validated_frequency

    if validated_symbol_type == "stock":
        min_endpoint = MULTI_ENDPOINT
        min_path = PATH_GET_MARKET_MIN_DATA
    elif validated_symbol_type == "future":
        min_endpoint = FUTURE_ENDPOINT
        min_path = PATH_GET_FUTURE_MARKET_MIN_DATA
    elif validated_symbol_type == "index":
        min_endpoint = INDEX_ENDPOINT
        min_path = PATH_GET_INDEX_MARKET_MIN_DATA
    else:
        min_endpoint = MULTI_ENDPOINT
        min_path = PATH_GET_MARKET_MIN_DATA

    # 排序已在读取 Parquet 时通过 DuckDB ORDER BY 完成，返回的 DataFrame 索引已是 0..n-1，无需 reset_index
    df = fetch_dataframe(build_endpoint(min_endpoint, min_path), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_hk_transaction(
        date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取港股tick数据
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    # 2. 验证必填参数date
    validate_not_empty(date, "date")

    # 3. 验证参数类型
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

    # 4. 验证港股symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validated_params['symbol'] = validate_hk_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 5. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 6. 验证日期格式
    validated_date = validate_date_format(date, "date")

    payload = {}
    if validated_date is not None:
        payload["date"] = validated_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(TICK_ENDPOINT, PATH_GET_STOCK_HK_TICK), payload=payload)

    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_future_tick(
        date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取期货Tick数据
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    # 2. 验证必填参数date
    validate_not_empty(date, "date")

    # 3. 验证参数类型
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

    # 4. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证日期格式
    validated_date = validate_date_format(date, "date")

    payload = {}
    if validated_date is not None:
        payload["date"] = validated_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 获取数据
    df = fetch_dataframe(build_endpoint(FUTURE_TICK_ENDPOINT, PATH_GET_FUTURE_TICK), payload=payload)

    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

