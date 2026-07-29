from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from panda_data.core.service import fetch_dataframe
from panda_data.exceptions import ServiceError, ServiceErrorCode
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_param_types,
    validate_no_duplicates,
    validate_date_format,
    validate_stock_status,
    validate_date_range,
    validate_not_empty,
    validate_extra_params,
    validate_hk_symbol_format,
    validate_date_interval,
    validate_quarter_format,
    validate_quarter_range,
    validate_quarter_interval,
    validate_bool_type,
    validate_quarter_date_combination,
    validate_data_volume_limit,
    validate_frequency,
    validate_time_zone, validate_year_format, validate_year_range, validate_company_investor_max_rank,
)

MULTI_ENDPOINT = "/multi"
PATH_GET_HK_DETAIL = "/getHkDetail"

INDEX_ENDPOINT = "/index"
PATH_GET_INDEX_COMPONENT = "/getIndexComponent"

STOCK_ENDPOINT = "/stock"
PATH_GET_STOCK_DIVIDEND_EVENT = "/getStockDividendEvent"
PATH_GET_STOCK_MARKET_EVENT = "/getStockMarketEvent"
PATH_GET_STOCK_MEETING_EVENT = "/getStockMeetingEvent"
PATH_GET_STOCK_IR_EVENT = "/getStockIrEvent"
PATH_GET_STOCK_FINANCIAL_EVENT = "/getStockFinancialEvent"
PATH_GET_STOCK_INVESTOR_CONCENTRATION = "/getStockInvestorConcentration"
PATH_GET_STOCK_TOP20_CONCENTRATION = "/getStockTop20Concentration"
PATH_GET_STOCK_INSIDER_TRADE = "/getStockInsiderTrade"
PATH_GET_STOCK_SHAREHOLDER_HOLDING = "/getStockShareholderHolding"
PATH_GET_STOCK_INVESTOR_RANKING = "/getStockInvestorRanking"
PATH_GET_STOCK_MKTFIN_INDICATOR = "/getStockMktfinIndicator"
PATH_GET_STOCK_INDUSTRY_MEDIAN = "/getStockIndustryMedian"
PATH_GET_STOCK_PV_INDICATOR = "/getStockPvIndicator"
PATH_GET_STOCK_NCYCL_CONSENSUS = "/getStockNcyclConsensus"
PATH_GET_STOCK_NCYCL_ESTIMATE = "/getStockNcyclEstimate"
PATH_GET_STOCK_OPERATING_INDICATOR = "/getStockOperatingIndicator"

FINA_ENDPOINT = "/financial"
PATH_GET_FINA_STATEMENT = "/getFinaStatement"

HK_ENDPOINT = "/hkMarket"
PATH_GET_STOCK_HK = "/getStockMarketHKData"
PATH_GET_STOCK_HK_PRE_CAL = "/getStockMarketHKPreCalData"
PATH_GET_STOCK_HK_POST_CAL = "/getStockMarketHKPostCalData"
PATH_GET_STOCK_HK_MIN = "/getStockMarketHKMinData"
FACTOR_ENDPOINT = "/factor"
PATH_GET_FACTOR_HK = "/getFactorHk"

def _normalise_symbols(symbol: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if symbol is None or symbol == "":
        return None
    if isinstance(symbol, list):
        return symbol
    return [symbol]

def _build_payload(
        *,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        # 财务相关参数
        info_date: Optional[str] = None,
        end_quarter: Optional[str] = None,
        start_quarter: Optional[str] = None,
        date: Optional[str] = None,
        is_latest: Optional[bool] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        market: Optional[str] = None,
        interim_type: Optional[str] = None,
        # 其他参数
        type: Optional[str] = None,
        factors: Optional[Union[str, List[str]]] = None,
        index_component: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}

    # 基础参数
    symbols = _normalise_symbols(symbol)
    if symbols is not None:
        payload["symbol"] = symbols
    if fields:
        payload["fields"] = fields

    # 财务参数
    if info_date is not None:
        payload["info_date"] = info_date
    if end_quarter is not None:
        payload["endQuarter"] = end_quarter
    if start_quarter is not None:
        payload["startQuarter"] = start_quarter
    if date is not None:
        payload["date"] = date
    if is_latest is not None:
        payload["isLatest"] = is_latest
    if start_date is not None:
        payload["startDate"] = start_date  # 注意驼峰命名
    if end_date is not None:
        payload["endDate"] = end_date  # 注意驼峰命名
    if market is not None:
        payload["market"] = market
    if interim_type is not None:
        payload["interimType"] = interim_type  # 注意驼峰命名

    # 其他参数
    if type is not None:
        payload["type"] = type
    if factors is not None:
        payload["factors"] = factors
    if index_component is not None:
        payload["indexComponent"] = index_component  # 注意驼峰命名

    return payload

def _reorder_fina_statement_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if {"symbol", "quarter"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "quarter"]
        other_cols = [col for col in cols if col not in priority_cols]
        return df[priority_cols + other_cols]
    if {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        return df[priority_cols + other_cols]
    if "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        return df[["symbol"] + other_cols]
    return df

def _validate_interim_type(interim_type: Optional[str]) -> str:
    if interim_type is None or interim_type == "":
        return "cumulative"
    if not isinstance(interim_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=(
                f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] interim_type 参数类型错误："
                f"应为 str，得到 {type(interim_type).__name__}"
            ),
        )
    interim_type_lower = interim_type.strip().lower()
    if interim_type_lower not in ["single", "cumulative"]:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=(
                f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] interim_type 只能为 single 或 cumulative，"
                f"当前值: {interim_type}"
            ),
        )
    return interim_type_lower

def get_hk_detail(
        symbol: Optional[Union[str, List[str]]] = "",
        fields: Optional[Union[str, List[str]]] = None,
        status: Optional[int] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取港股的基本信息

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，如 "0001.HK"，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        status (Optional[int]): 是否在市，1 - 在市，0 - 退市，-1 - 未知，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_hk_detail(
        ...     symbol=["0001.HK", "0002.HK", "0003.HK"],
        ...     fields=[""],
        ...     status=None
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

    # 港股沿用原 market=hk 逻辑，只检查重复，不检查格式
    if validated_params['symbol'] is not None and validated_params['symbol'] != [""] and validated_params[
        'symbol'] != []:
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证status参数
    validated_status = validate_stock_status(status, "status") if status is not None else status

    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_status is not None:
        payload["status"] = validated_status

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_HK_DETAIL), payload=payload)
    if not df.empty and "symbol" in df.columns:
        df = df[df["symbol"].str.upper() != "UNKNOWN"]
    return df

def get_stock_dividend_event(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票分红相关的事件

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_dividend_event(
        ...     symbol="",
        ...     start_date="20250101",
        ...     end_date="20260501",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建 payload
    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_DIVIDEND_EVENT), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "publish_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "publish_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_market_event(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取市场活动相关的事件

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_market_event(
        ...     symbol="",
        ...     start_date="20250101",
        ...     end_date="20260401",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建 payload
    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_MARKET_EVENT), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_meeting_event(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司会议相关的事件

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_meeting_event(
        ...     symbol="",
        ...     start_date="20250101",
        ...     end_date="20260401",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建 payload
    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_MEETING_EVENT), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_financial_event(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取财务披露相关的事件

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_financial_event(
        ...     symbol="",
        ...     start_date="20250101",
        ...     end_date="20260401",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建 payload
    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_FINANCIAL_EVENT), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_ir_event(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取投资者关系活动相关的事件

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_ir_event(
        ...     symbol="",
        ...     start_date="20250101",
        ...     end_date="20260401",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建 payload
    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_IR_EVENT), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_investor_concentration(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司投资者集中度

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_investor_concentration(
        ...     symbol="",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_INVESTOR_CONCENTRATION), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_top20_concentration(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司前20投资者集中度

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_top20_concentration(
        ...     symbol="",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_TOP20_CONCENTRATION), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_investor_ranking(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        max_rank: Optional[int] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司投资者排行

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        max_rank (Optional[int]): 最大返回排名（小于等于20的正整数），默认为空返回前20名，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_investor_ranking(
        ...     symbol="",
        ...     fields=[],
        ...     max_rank=10
        ... )
    """
    validate_extra_params(kwargs)

    # 验证 max_rank 参数
    validated_max_rank = validate_company_investor_max_rank(max_rank, "max_rank")

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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {
        "maxRank": validated_max_rank
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_INVESTOR_RANKING), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_insider_trade(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司内部人交易活动

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_insider_trade(
        ...     symbol="0004.HK",
        ...     start_date="20250101",
        ...     end_date="20251231",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建 payload
    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_INSIDER_TRADE), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_shareholder_holding(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司股东持股报告

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_shareholder_holding(
        ...     symbol="8510.HK",
        ...     start_date="20250101",
        ...     end_date="20251231",
        ...     fields=[]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建 payload
    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_SHAREHOLDER_HOLDING), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "holding_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "holding_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def get_stock_mktfin_indicator(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司最新市场财务统计指标

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_mktfin_indicator(
        ...     symbol=[""],
        ...     fields=["curr_price_to_dps_issue_ttm", "curr_ev_to_rev"]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_MKTFIN_INDICATOR), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    elif not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        df = df[["symbol"] + other_cols]

    return df

def get_stock_industry_median(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司最新行业中位统计数据

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_industry_median(
        ...     symbol=[""],
        ...     fields=["imed_net_trade_cycle_days_ttm", "imed_pretax_roa_ratio_ttm"]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_INDUSTRY_MEDIAN), payload=payload)

    # 调整列顺序：如果存在 symbol 列，将其放在最前面
    if not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        df = df[["symbol"] + other_cols]

    return df

def get_stock_pv_indicator(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司最新价量指标数据

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_pv_indicator(
        ...     symbol=[""],
        ...     fields=["pv_beta_5y", "pv_rel_return_26w"]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PV_INDICATOR), payload=payload)

    # 调整列顺序：如果存在 symbol 列，将其放在最前面
    if not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        df = df[["symbol"] + other_cols]

    return df

def get_stock_ncycl_consensus(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取非周期性指标一致预期

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_ncycl_consensus(
        ...     symbol=[""],
        ...     fields=["indicator", "mean", "std_6month", "high_week"]
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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_NCYCL_CONSENSUS), payload=payload)

    # 调整列顺序：如果存在 symbol 列，将其放在最前面
    if not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        df = df[["symbol"] + other_cols]

    return df

def get_stock_ncycl_estimate(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取非周期性指标一致预期

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_ncycl_estimate(
        ...     symbol=[""],
        ...     fields=["indicator", "mean", "std_6month", "high_week"]
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

    # 美股 symbol 当前不要求 .NB 后缀，仅校验重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建 payload
    payload = {}

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_NCYCL_ESTIMATE), payload=payload)

    # 调整列顺序：如果存在 symbol 列，将其放在最前面
    if not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        df = df[["symbol"] + other_cols]

    return df

def get_stock_operating_indicator(
        symbol: Optional[Union[str, List[str]]] = None,
        start_year: str = None,
        end_year: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取公司标准化营运指标

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_year (str): 开始财年，格式为 YYYY（如 "2025"），必填
        end_year (str): 结束财年，格式为 YYYY（如 "2025"），必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_stock_operating_indicator(
        ...     symbol=[""],
        ...     start_year="2023",
        ...     end_year="2025",
        ...     fields=[""]
        ... )
    """
    validate_extra_params(kwargs)

    # 验证必填参数
    validate_not_empty(start_year, "start_year")
    validate_not_empty(end_year, "end_year")

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

    # 验证港股 symbol 格式
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_hk_symbol_format(validated_params['symbol'])

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证年份格式
    validated_start_year = validate_year_format(start_year, "start_year")
    validated_end_year = validate_year_format(end_year, "end_year")

    # 验证年份范围
    validate_year_range(validated_start_year, validated_end_year)

    # 构建 payload
    payload = {
        "startYear": validated_start_year,
        "endYear": validated_end_year
    }

    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols

    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 调用接口
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_OPERATING_INDICATOR), payload=payload)

    # 调整列顺序：如果存在 symbol 和 year 列，将其放在最前面
    if not df.empty and {"symbol", "year"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "year"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    elif not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        df = df[["symbol"] + other_cols]

    return df

def get_index_component(
        stock_symbol: Optional[Union[str, List[str]]] = None,
        index_symbol: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取港股指数成分股数据

    Args:
        stock_symbol: 股票代码列表，可选
            - 港股格式：如 "00001.HK"（4位或5位以8开头的数字）
        index_symbol: 指数代码列表，可选，不进行格式验证
        **kwargs: 其他参数（会被验证）

    Returns:
        pd.DataFrame: 港股指数成分股数据

    Raises:
        ServiceError: 当参数验证失败时抛出异常
    """
    validate_extra_params(kwargs)

    # 验证参数类型
    params = {
        'stock_symbol': stock_symbol,
        'index_symbol': index_symbol
    }

    type_config = {
        'stock_symbol': str,
        'index_symbol': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['stock_symbol', 'index_symbol']
    )

    # 验证港股 stock_symbol 格式
    if validated_params['stock_symbol'] is not None:
        validate_no_duplicates(validated_params['stock_symbol'], 'stock_symbol')
        validate_hk_symbol_format(validated_params['stock_symbol'])

    # 验证 index_symbol 列表中是否有重复值（不进行格式验证）
    if validated_params['index_symbol'] is not None:
        validate_no_duplicates(validated_params['index_symbol'], 'index_symbol')

    # 构建 payload
    payload = {}

    stock_symbols = _normalise_symbols(validated_params['stock_symbol'])
    if stock_symbols is not None:
        payload["stockSymbol"] = stock_symbols

    index_symbols = _normalise_symbols(validated_params['index_symbol'])
    if index_symbols is not None:
        payload["indexSymbol"] = index_symbols

    # 调用接口
    df = fetch_dataframe(build_endpoint(INDEX_ENDPOINT, PATH_GET_INDEX_COMPONENT), payload=payload)

    # 调整列顺序：如果存在 symbol 列，将其放在最前面
    if not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        other_cols = [col for col in cols if col != "symbol"]
        df = df[["symbol"] + other_cols]

    return df

def get_hk_daily(
    symbol: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs
) -> pd.DataFrame:
    """
    获取港股日线数据

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (str): 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD，与结束日期间不超过5年，必填
        end_date (str): 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD，与开始日期间不超过5年，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_hk_daily(
        ...     symbol=[],
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     fields=[]
        ... )
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 1. 验证参数类型
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

    # 2. 验证symbol列表中是否有重复值（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 3. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 4. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 5. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 6. 验证日期间隔
    if start_date is not None and end_date is not None:
        validate_date_interval(start_date, end_date, max_years=5)

    payload = {}
    normalised_symbol = _normalise_symbols(validated_params['symbol'])
    if normalised_symbol is not None:
        payload["symbol"] = normalised_symbol
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(HK_ENDPOINT, PATH_GET_STOCK_HK), payload=payload)

    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df

def _get_hk_cal_daily(
    endpoint_path: str,
    symbol: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs
) -> pd.DataFrame:
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    payload = {}
    normalised_symbol = _normalise_symbols(validated_params['symbol'])
    if normalised_symbol is not None:
        payload["symbol"] = normalised_symbol
    payload["startDate"] = validated_start_date
    payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(HK_ENDPOINT, endpoint_path), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in df.columns if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df

def get_hk_daily_pre(
    symbol: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs
) -> pd.DataFrame:
    """获取港股自研前复权日线数据。start_date、end_date 必填。"""
    return _get_hk_cal_daily(
        PATH_GET_STOCK_HK_PRE_CAL,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        **kwargs,
    )

def get_hk_daily_post(
    symbol: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs
) -> pd.DataFrame:
    """获取港股自研后复权日线数据。start_date、end_date 必填。"""
    return _get_hk_cal_daily(
        PATH_GET_STOCK_HK_POST_CAL,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        **kwargs,
    )

def get_factor_hk(
    symbol: Optional[Union[str, List[str]]] = "",
    start_date: str = "",
    end_date: str = "",
    factors: Optional[Union[str, List[str]]] = None,
    **kwargs
) -> pd.DataFrame:
    """
    获取港股因子数据。
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取港股因子数据（数据源：factor_cal_date_hk）。

    基础行情字段 open/close/high/low/volume/amount 来自自研后复权日线，
    其他 cal 因子来自 factor_cal_date_hk。

    参数：
        symbol: 港股股票代码，如 "00700.HK" 或 ["00700.HK", "09988.HK"]，默认为空返回所有。
        start_date: 开始日期，格式为 "YYYYMMDD"。
        end_date: 结束日期，格式为 "YYYYMMDD"。
        factors: 因子列表，如 "open"、"amount"、"cal_ret_1d"。
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    validate_not_empty(factors, "factors")

    params = {
        'symbol': symbol,
        'factors': factors
    }
    type_config = {
        'symbol': str,
        'factors': str
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'factors']
    )

    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
    if validated_params['factors'] is not None:
        if isinstance(validated_params['factors'], str):
            validated_params['factors'] = [validated_params['factors']]
        validate_no_duplicates(validated_params['factors'], 'factors')

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    normalised_symbol = _normalise_symbols(
        validated_params['symbol'] if validated_params['symbol'] != [""] else None
    )
    if normalised_symbol is not None:
        payload["symbol"] = normalised_symbol
    payload["startDate"] = validated_start_date
    payload["endDate"] = validated_end_date
    if validated_params['factors']:
        payload["factors"] = validated_params['factors']

    df = fetch_dataframe(build_endpoint(HK_ENDPOINT, PATH_GET_FACTOR_HK), payload=payload)

    # getFactorHk 返回 ResultData<ParquetQueryVO>，数据可能嵌套在 data 列中，需要展开
    if not df.empty:
        if 'data' in df.columns and isinstance(df['data'].iloc[0], list):
            expanded_data = []
            for item in df['data']:
                if isinstance(item, list):
                    expanded_data.extend(item)
            if expanded_data:
                df = pd.DataFrame(expanded_data)

    if 'index_component' in df.columns:
        df = df.drop(columns=['index_component'], errors='ignore')

    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in df.columns if col not in priority_cols]
        df = df[priority_cols + other_cols].sort_values(by=["symbol", "date"]).reset_index(drop=True)

    return df

def get_hk_min(
    symbol: Optional[Union[str, List[str]]] = None,
    start_date: str = "",
    end_date: str = "",
    fields: Optional[Union[str, List[str]]] = None,
    time_zone: Optional[Tuple[str, str]] = None,
    frequency: Optional[str] = "1m",
    **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取港股分钟线数据
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {
        "symbol": symbol,
        "fields": fields,
    }
    type_config = {
        "symbol": str,
        "fields": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["symbol", "fields"],
    )

    if validated_params["symbol"] is not None:
        validate_no_duplicates(validated_params["symbol"], "symbol")

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    if start_date and end_date:
        validate_date_interval(start_date, end_date, max_years=5)

    validated_time_zone = validate_time_zone(time_zone, "timeZone") if time_zone is not None else time_zone
    validated_frequency = validate_frequency(frequency, "frequency")

    validate_data_volume_limit(
        validated_params["symbol"] if validated_params["symbol"] != [""] else None,
        validated_start_date,
        validated_end_date,
        "stock",
        validated_time_zone,
        validated_frequency,
    )

    payload = {}
    symbols = _normalise_symbols(validated_params["symbol"] if validated_params["symbol"] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]
    if validated_time_zone is not None:
        payload["timeZone"] = list(validated_time_zone)
    if validated_frequency:
        payload["frequency"] = validated_frequency

    df = fetch_dataframe(build_endpoint(HK_ENDPOINT, PATH_GET_STOCK_HK_MIN), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df

def get_fina_statement(
        start_quarter: str,
        end_quarter: str,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        date: Optional[str] = None,
        is_latest: Optional[bool] = True,
        interim_type: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取财务季度报告

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票名称，非必填
        start_quarter (str): 起始季度，格式为 YYYYqN（如 "2022q1"），与结束季度间隔不超过5年，必填
        end_quarter (str): 结束季度，格式为 YYYYqN（如 "2026q4"），与起始季度间隔不超过5年，必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        date (Optional[str]): 公告日期，返回该日期及之前的数据，格式为 YYYYMMDD，非必填
        is_latest (Optional[bool]): True 返回最新披露数据，False 返回全部，默认为 True，非必填
        interim_type (Optional[str]): 报告类型，可选 "single"（单季）或 "cumulative"（累计），默认为 "cumulative"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_fina_statement(
        ...     symbol="0700.HK",
        ...     start_quarter="2022q1",
        ...     end_quarter="2026q4",
        ...     date="20241014",
        ...     is_latest=True,
        ...     fields=["symbol", "bs_asset_accruals"]
        ... )
    """
    validate_extra_params(kwargs)

    params = {
        "symbol": symbol,
        "fields": fields,
        "interim_type": interim_type,
    }
    type_config = {
        "symbol": str,
        "fields": str,
        "interim_type": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["symbol", "fields"],
    )

    if validated_params["symbol"] is not None:
        validate_no_duplicates(validated_params["symbol"], "symbol")
        validate_hk_symbol_format(validated_params["symbol"])

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validate_not_empty(start_quarter, "start_quarter")
    validate_not_empty(end_quarter, "end_quarter")

    validated_start_quarter = validate_quarter_format(start_quarter, "start_quarter")
    validated_end_quarter = validate_quarter_format(end_quarter, "end_quarter")
    validate_quarter_range(validated_start_quarter, validated_end_quarter)
    validate_quarter_interval(validated_start_quarter, validated_end_quarter, max_years=5)

    validated_date = validate_date_format(date, "date")
    validated_is_latest = validate_bool_type(is_latest, "is_latest")
    validate_quarter_date_combination(start_quarter, end_quarter, date)
    validated_interim_type = _validate_interim_type(interim_type)

    payload = _build_payload(
        symbol=validated_params["symbol"],
        fields=validated_params["fields"],
        start_quarter=validated_start_quarter,
        end_quarter=validated_end_quarter,
        date=validated_date,
        is_latest=validated_is_latest,
        interim_type=validated_interim_type,
    )

    df = fetch_dataframe(build_endpoint(FINA_ENDPOINT, PATH_GET_FINA_STATEMENT), payload=payload)
    return _reorder_fina_statement_columns(df)

