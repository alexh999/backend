from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from datetime import datetime

import pandas as pd

from panda_data.core.service import fetch_dataframe
from panda_data.exceptions import ServiceError, ServiceErrorCode
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_date_format,
    validate_param_types,
    validate_symbol_format,
    validate_no_duplicates,
    validate_quarter_format,
    validate_quarter_range,
    validate_bool_type, validate_quarter_date_combination, validate_extra_params, validate_date_range,
    validate_stock_info_market, validate_not_empty, validate_factor_type, validate_future_symbol_format,
    validate_index_component, validate_date_interval, validate_indicator, validate_quarter_interval
)

FINA_ENDPOINT = "/financial"
PATH_GET_FINANCIAL_FORECAST = "/getFinancialForecastData"
PATH_GET_FINANCIAL_PERFORMANCE = "/getFinancialPerformanceData"
PATH_GET_FINANCIAL_EX = "/getFinancialExData"
PATH_GET_FINANCIAL_STATEMENT_DAILY = "/getFinancialStatementDailyData"

STOCK_ENDPOINT = "/stock"
PATH_GET_AUDIT_OPINION = "/getStockAuditData"
PATH_GET_FACTOR_RESTORED = "/getFactorRestoredData"
FACTOR_ENDPOINT = "/factor"
PATH_GET_ADJ_FACTOR_HK = "/getAdjFactorHk"
PATH_GET_ADJ_FACTOR_US = "/getAdjFactorUs"
PATH_GET_FACTOR_BARRA_EXPOSURE = "/getFactorBarraExposureData"
MULTI_ENDPOINT = "/multi"
PATH_GET_FACTOR = "/getFactor"


def _normalise_symbols(symbol: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if symbol is None:
        return None
    if isinstance(symbol, list):
        return symbol
    return [symbol]


def _normalise_list(value: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value] if value != "" else None


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


def get_fina_forecast(
        symbol: Optional[Union[str, List[str]]] = None,
        info_date: Optional[str] = None,
        end_quarter: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取业绩预告数据

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，可以是单个字符串或字符串列表，非必填
        info_date (Optional[str]): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_quarter (Optional[str]): 报告季度，格式为 "YYYYqN"，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_fina_forecast(
        ...     symbol="688795.SH",
        ...     info_date="20251128",
        ...     end_quarter="2025q4",
        ...     fields=[]
        ... )
        >>> print(result)
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

    # 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证info_date格式
    validated_info_date = validate_date_format(info_date, "info_date")

    # 验证end_quarter格式
    validated_end_quarter = validate_quarter_format(end_quarter, "end_quarter")

    payload = _build_payload(
        symbol=validated_params['symbol'],
        fields=validated_params['fields'],
        info_date=validated_info_date,
        end_quarter=validated_end_quarter,
    )

    df = fetch_dataframe(build_endpoint(FINA_ENDPOINT, PATH_GET_FINANCIAL_FORECAST), payload=payload)
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_fina_performance(
        symbol: Optional[Union[str, List[str]]] = None,
        info_date: Optional[str] = None,
        end_quarter: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取财务快报数据

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，可以是单个字符串或字符串列表，非必填
        info_date (Optional[str]): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_quarter (Optional[str]): 报告季度，格式为 "YYYYqN"，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_fina_performance(
        ...     symbol="688235.SH",
        ...     info_date="20251107",
        ...     end_quarter="2025q4",
        ...     fields=["symbol", "info_date", "end_date", "basic_eps", "eps_excluding_nonrecurring",
        ...             "net_profit_excluding_nonrecurring_yoy", "net_profit_parent"]
        ... )
        >>> print(result)
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

    # 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 添加日期处理逻辑
    if info_date:
        # 如果info_date非空，则将end_quarter设置为None
        end_quarter = None
    elif not info_date and not end_quarter:
        # 如果info_date和end_quarter均为空，则将info_date设置为当日日期
        info_date = datetime.now().strftime('%Y%m%d')

    # 验证info_date格式
    validated_info_date = validate_date_format(info_date, "info_date")

    # 验证end_quarter格式
    validated_end_quarter = validate_quarter_format(end_quarter, "end_quarter")
    payload = _build_payload(
        symbol=validated_params['symbol'],
        fields=validated_params['fields'],
        info_date=validated_info_date,
        end_quarter=validated_end_quarter,
    )

    df = fetch_dataframe(build_endpoint(FINA_ENDPOINT, PATH_GET_FINANCIAL_PERFORMANCE), payload=payload)
    # 如果有rice_create_tm列，则删除这列
    df = df.drop(columns=['rice_create_tm'], errors='ignore')
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_fina_reports(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        start_quarter: str = None,
        end_quarter: str = None,
        date: Optional[str] = None,
        is_latest: Optional[bool] = True,
        **kwargs
) -> pd.DataFrame:
    """
    获取财务季度报告

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票名称，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        start_quarter (str): 起始季度，格式为 "YYYYqN"，非必填
        end_quarter (str): 结束季度，格式为 "YYYYqN"，非必填
        date (Optional[str]): 公告日期，返回该日期及之前的数据，非必填
        is_latest (Optional[bool]): True 返回最新披露数据，False 返回全部，默认为 True，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_fina_reports(
        ...     symbol="688795.SH",
        ...     date="20251114",
        ...     start_quarter="2024q1",
        ...     end_quarter="2026q1",
        ...     is_latest=False,
        ...     fields=["symbol", "date", "quarter", "bs_acct_payable", "is_adj_credit_impair",
        ...             "cfs_cash_inflow_operating", "cfs_cash_oth_operating"]
        ... )
        >>> print(result)
    """
    validate_extra_params(kwargs)

    # 验证必填参数
    validate_not_empty(start_quarter, "start_quarter")
    validate_not_empty(end_quarter, "end_quarter")

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

    # 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 对fields进行金融因子映射转换（新字段名转为旧字段名）
    if validated_params['fields'] is not None:
        # 确保fields是列表格式
        if isinstance(validated_params['fields'], str):
            fields_list = [validated_params['fields']]
        else:
            fields_list = validated_params['fields']

        # 更新validated_params中的fields为转换后的结果
        validated_params['fields'] = fields_list

        # 验证转换后的fields列表中是否有重复值（空值会被正确处理）
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证季度格式
    validated_start_quarter = validate_quarter_format(start_quarter, "start_quarter")
    validated_end_quarter = validate_quarter_format(end_quarter, "end_quarter")

    # 验证季度范围
    validate_quarter_range(validated_start_quarter, validated_end_quarter)

    # 验证季度间隔不超过5年
    validate_quarter_interval(validated_start_quarter, validated_end_quarter, max_years=5)

    # 验证date格式
    validated_date = validate_date_format(date, "date")

    # 验证is_latest类型
    validated_is_latest = validate_bool_type(is_latest, "is_latest")

    # 新增：验证start_quarter、end_quarter和date参数的组合有效性
    validate_quarter_date_combination(start_quarter, end_quarter, date)

    payload = _build_payload(
        symbol=validated_params['symbol'],
        fields=validated_params['fields'],
        start_quarter=validated_start_quarter,
        end_quarter=validated_end_quarter,
        date=validated_date,
        is_latest=validated_is_latest,
    )

    df = fetch_dataframe(build_endpoint(FINA_ENDPOINT, PATH_GET_FINANCIAL_EX), payload=payload)
    if not df.empty and {"symbol", "quarter"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "quarter"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_financial_statement_daily(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        market: Optional[str] = None,
        interim_type: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取财务报表日频数据
    返回的是 Parquet 格式文件，会自动转换为 DataFrame

    Args:
        symbol: 标的代码列表
        fields: 返回字段列表
        start_date: 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD
        end_date: 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD
        market: 市场类型，只能填 us 或 hk
        interim_type: 报表类型，只能填 single 或 cumulative
        **kwargs: 其他参数（会被验证）

    Returns:
        pd.DataFrame: 财务报表日频数据
    """
    validate_extra_params(kwargs)

    # 验证参数类型
    params = {
        'symbol': symbol,
        'fields': fields,
        'start_date': start_date,
        'end_date': end_date,
        'market': market,
        'interim_type': interim_type
    }

    type_config = {
        'symbol': str,
        'fields': str,
        'start_date': str,
        'end_date': str,
        'market': str,
        'interim_type': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'fields']
    )

    # 仅验证 symbol 列表无重复（本接口为港美股，不校验 A 股 symbol 格式）
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    if validated_start_date and validated_end_date:
        validate_date_range(validated_start_date, validated_end_date)

    # 验证market参数（必须非空，且只能是 us 或 hk）
    if market is None or market == "":
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] market参数不能为空，只能填us或hk"
        )

    if not isinstance(market, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] market参数类型错误：应为str类型，得到{type(market).__name__}类型"
        )

    market_lower = market.strip().lower()
    if market_lower not in ["us", "hk"]:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] market参数错误，只能填us或hk，当前值为: {market}"
        )

    # 验证interim_type参数（必须非空，且只能是 single 或 cumulative）
    if interim_type is None or interim_type == "":
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] interimType参数不能为空，只能填single或cumulative"
        )

    if not isinstance(interim_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] interimType参数类型错误：应为str类型，得到{type(interim_type).__name__}类型"
        )

    interim_type_lower = interim_type.strip().lower()
    if interim_type_lower not in ["single", "cumulative"]:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] interimType参数错误，只能填single或cumulative，当前值为: {interim_type}"
        )

    # 构建payload，注意Java端期望的字段名是startDate和endDate（驼峰命名）
    payload = _build_payload(
        symbol=validated_params['symbol'],
        fields=validated_params['fields'],
        extra={
            **({"startDate": validated_start_date} if validated_start_date is not None else {}),
            **({"endDate": validated_end_date} if validated_end_date is not None else {}),
            "market": market_lower,
            "interimType": interim_type_lower,
        },
    )

    # 调用接口，返回的是 Parquet 文件，fetch_dataframe 会自动处理
    df = fetch_dataframe(build_endpoint(FINA_ENDPOINT, PATH_GET_FINANCIAL_STATEMENT_DAILY), payload=payload)

    # 如果返回的DataFrame不为空，尝试调整列顺序（如果存在symbol和date列）
    if not df.empty:
        if "symbol" in df.columns and "date" in df.columns:
            cols = df.columns.tolist()
            priority_cols = ["symbol", "date"]
            other_cols = [col for col in cols if col not in priority_cols]
            df = df[priority_cols + other_cols]
        elif "symbol" in df.columns:
            cols = df.columns.tolist()
            priority_cols = ["symbol"]
            other_cols = [col for col in cols if col not in priority_cols]
            df = df[priority_cols + other_cols]

    return df


def get_audit_opinion(
        symbol: Optional[Union[str, List[str]]] = None,
        start_quarter: Optional[str] = None,
        end_quarter: Optional[str] = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取财务报告审计意见

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_quarter (Optional[str]): 开始季度，如 "2025q1"，非必填
        end_quarter (Optional[str]): 结束季度，如 "2025q3"，非必填
        market (Optional[str]): 市场，默认 "cn" 为中国内地市场，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_audit_opinion(
        ...     symbol="000001.SZ",
        ...     start_quarter="2024q1",
        ...     end_quarter="2025q3",
        ...     market="cn",
        ...     fields=[]
        ... )
        >>> print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    # 2. 验证参数类型
    params = {
        'symbol': symbol,
        'market': market,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'market': str,
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

    # 5. 验证市场参数
    if validated_params['market'] is not None:
        validated_params['market'] = validate_stock_info_market(validated_params['market'])

    # 6. 验证季度格式
    validated_start_quarter = validate_quarter_format(start_quarter, "start_quarter")
    validated_end_quarter = validate_quarter_format(end_quarter, "end_quarter")

    # 7. 验证季度范围
    validate_quarter_range(validated_start_quarter, validated_end_quarter)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_quarter:
        payload["startQuarter"] = validated_start_quarter
    if validated_end_quarter:
        payload["endQuarter"] = validated_end_quarter
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_AUDIT_OPINION), payload=payload)
    if not df.empty and {"symbol", "quarter"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "quarter"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_adj_factor(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取复权因子

    Args:
        symbol (Optional[Union[str, List[str]]]): 股票代码，非必填
        start_date (Optional[str]): 开始日期，如 "20250702"，非必填
        end_date (Optional[str]): 结束日期，如 "20250702"，非必填
        fields (Optional[Union[str, List[str]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_adj_factor(
        ...     symbol="000001.SZ",
        ...     start_date="20250101",
        ...     end_date="20250831",
        ...     fields=[]
        ... )
        >>> print(result)
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
    df = fetch_dataframe(build_endpoint("/factor", PATH_GET_FACTOR_RESTORED), payload=payload)
    if not df.empty and {"symbol", "ex_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "ex_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def _get_oversea_adj_factor(
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
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    payload["startDate"] = validated_start_date
    payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(FACTOR_ENDPOINT, endpoint_path), payload=payload)
    if not df.empty and {"symbol", "ex_date"}.issubset(df.columns):
        priority_cols = [col for col in ["symbol", "ex_date", "ex_end_date"] if col in df.columns]
        other_cols = [col for col in df.columns if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_adj_factor_hk(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取港股自研复权因子数据。
    start_date、end_date 必填。
    """
    return _get_oversea_adj_factor(
        PATH_GET_ADJ_FACTOR_HK,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        **kwargs,
    )


def get_adj_factor_us(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取美股自研复权因子数据。
    start_date、end_date 必填。
    """
    return _get_oversea_adj_factor(
        PATH_GET_ADJ_FACTOR_US,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        **kwargs,
    )


def get_factor(
        symbol: Union[str, List[str]] = "",
        start_date: str = "",
        end_date: str = "",
        type: Optional[str] = "stock",
        factors: Union[str, List[str]] = None,
        index_component: Optional[str] = "",
        **kwargs
) -> pd.DataFrame:
    """
    获取回测因子

    Args:
        symbol (Union[str, List[str]]): 股票代码，非必填
        start_date (str): 开始日期，如 "20250702"，非必填
        end_date (str): 结束日期，如 "20250702"，非必填
        type (Optional[str]): 产品类型，支持 "stock"、"future"，默认为 "stock"，非必填
        factors (Union[str, List[str]]): 因子列表，非必填
        index_component (Optional[str]): 股票池，默认为空表示查询所有，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_factor(
        ...     symbol="000001.SZ",
        ...     start_date="20250101",
        ...     end_date="20250131",
        ...     factors=['open', 'close'],
        ...     index_component="000300",
        ...     type="stock"
        ... )
        >>> print(result)
    """

    validate_extra_params(kwargs)
    # 验证必填参数
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    validate_not_empty(factors, "factors")

    # 验证参数类型
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

    # 验证symbol格式（根据type类型）
    if validated_params['symbol'] is not None:
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

        # 根据type类型验证symbol格式
        validated_type = validate_factor_type(type, "type")
        if validated_type == "stock":
            validate_symbol_format(validated_params['symbol'])
        elif validated_type == "future":
            validate_future_symbol_format(validated_params['symbol'])

    # 验证factors列表中是否有重复值
    if validated_params['factors'] is not None:
        # 确保factors是列表格式
        if isinstance(validated_params['factors'], str):
            factors_list = [validated_params['factors']]
        else:
            factors_list = validated_params['factors']

        validated_params['factors'] = factors_list

        validate_no_duplicates(validated_params['factors'], 'factors')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 验证日期间隔不能超过5年
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    # 验证type参数
    validated_type = validate_factor_type(type, "type")

    # 如果index_component是旧版的，则提供转换以兼容
    if index_component == "100":
        index_component = "000300"
    elif index_component == "010":
        index_component = "000905"
    elif index_component == "001":
        index_component = "000852"
    elif index_component == "000":
        index_component = "000985"

    # 验证index_component参数
    validated_index_component = validate_indicator(index_component, "indexComponent")

    if validated_index_component == "000985":
        validated_index_component = ""

    payload = {"type": validated_type}
    symbols = _normalise_symbols(validated_params['symbol'] if validated_params['symbol'] != [""] else None)
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['factors']:
        payload["factors"] = validated_params['factors']
    if validated_index_component:
        payload["indexComponent"] = validated_index_component

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_FACTOR), payload=payload)

    # 如果返回的数据包含嵌套的 JSON 结构，需要展开
    if not df.empty:
        # 检查是否数据在某个列中（如 'data' 列）
        if 'data' in df.columns and isinstance(df['data'].iloc[0], list):
            # 将嵌套的列表展开为新的 DataFrame
            expanded_data = []
            for item in df['data']:
                if isinstance(item, list):
                    expanded_data.extend(item)

            if expanded_data:
                df = pd.DataFrame(expanded_data)

    # 如果有index_component列则丢弃
    if 'index_component' in df.columns:
        df = df.drop(columns=['index_component'], errors='ignore')

    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        df = df.sort_values(by=["symbol", "date"], ascending=[True, False]).reset_index(drop=True)

    return df


def get_factor_barra_exposure(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
        [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]


    Args:
        symbol: 股票代码，如 "000001.SZ" 或 ["000001.SZ", "000002.SZ"]
        start_date: 开始日期，YYYYMMDD 或 YYYY-MM-DD
        end_date: 结束日期，YYYYMMDD 或 YYYY-MM-DD
        fields: 返回字段列表，不传返回全部字段
        **kwargs: 其他参数

    Returns:
        pd.DataFrame: 因子暴露度数据
    """
    validate_extra_params(kwargs)

    params = {
        'symbol': symbol,
        'fields': fields,
        'start_date': start_date,
        'end_date': end_date,
    }
    type_config = {
        'symbol': str,
        'fields': str,
        'start_date': str,
        'end_date': str,
    }
    validated_params = validate_param_types(
        params, type_config,
        allowed_list_params=['symbol', 'fields']
    )

    validated_start_date = validate_date_format(validated_params['start_date'], "start_date")
    validated_end_date = validate_date_format(validated_params['end_date'], "end_date")

    if validated_start_date and validated_end_date:
        validate_date_range(validated_start_date, validated_end_date)

    if validated_params['symbol'] is not None:
        symbols = _normalise_symbols(validated_params['symbol'])
        validate_symbol_format(symbols)

    if validated_params['fields'] is not None:
        if isinstance(validated_params['fields'], str):
            validated_params['fields'] = [validated_params['fields']]
        validate_no_duplicates(validated_params['fields'], 'fields')

    payload = _build_payload(
        symbol=validated_params['symbol'],
        fields=validated_params['fields'],
        start_date=validated_start_date,
        end_date=validated_end_date,
    )

    df = fetch_dataframe(
        build_endpoint(FACTOR_ENDPOINT, PATH_GET_FACTOR_BARRA_EXPOSURE),
        payload=payload
    )

    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        df = df.sort_values(by=["symbol", "date"], ascending=[True, False]).reset_index(drop=True)

    return df