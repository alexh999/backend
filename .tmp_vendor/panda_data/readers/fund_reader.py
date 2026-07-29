"""
基金数据读取模块

提供基金基本信息、日行情、涨跌停限制、复权行情、ETF申赎等数据的读取接口。
遵循 panda_data SDK 统一模式：参数校验 -> payload构建 -> fetch_dataframe -> 列排序。
"""
from __future__ import annotations

from typing import List, Optional, Union, Dict, Any

import pandas as pd

from panda_data.core.service import fetch_dataframe
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_param_types,
    validate_fund_symbol_format,
    validate_no_duplicates,
    validate_date_format,
    validate_date_range,
    validate_date_interval,
    validate_not_empty,
    validate_extra_params,
)

FUND_ENDPOINT = "/fund"
PATH_GET_FUND_DETAIL = "/getFundDetailData"
PATH_GET_FUND_DAILY = "/getFundDailyData"
PATH_GET_FUND_DAILY_POST = "/getFundDailyPostData"
PATH_GET_FUND_DAILY_PRE = "/getFundDailyPreData"
PATH_GET_FUND_ETF_CR = "/getFundEtfCrData"
PATH_GET_FUND_ETF_CONSTITUENTS = "/getFundEtfConstituentsData"
PATH_GET_FUND_ETF_CONSTITUENT = "/getFundEtfCrNetData"
PATH_GET_FUND_ETF_CR_LIMITS = "/getFundEtfCrLimitsData"


def _normalise_list(value: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """规范化列表参数，过滤空值"""
    if value is None:
        return None
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value] if value != "" else None


def _normalise_symbols(symbol: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """规范化symbol参数"""
    if symbol is None or symbol == "":
        return None
    if isinstance(symbol, list):
        return symbol
    return [symbol]


def _reorder_columns(df: pd.DataFrame, priority_cols: List[str]) -> pd.DataFrame:
    """将关键列移到最前面"""
    if not df.empty and set(priority_cols).issubset(df.columns):
        cols = df.columns.tolist()
        other_cols = [c for c in cols if c not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_fund_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        type: Optional[Union[str, List[str]]] = None,
        operation_mode: Optional[Union[str, List[str]]] = None,
        etf_lof_type: Optional[Union[str, List[str]]] = None,
        is_class_fund: Optional[Union[int, List[int]]] = None,
        index_fund_type: Optional[Union[str, List[str]]] = None,
        status: Optional[Union[str, List[str]]] = None,
        fund_status: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取基金基本信息

    参数:
        symbol: 基金代码，如 "000001.OF"、"159919.SZ"、"510050.SH"
        exchange: 交易市场（SZ:深交所；SH:上交所；OF:场外基金）
        type: 按投资对象分基金类型（E：股票型，H：混合型，B：债券型，SB：短期理财债券，M：货币型，O：其他）
        operation_mode: 基金运作模式（O：开放式，C：封闭式）
        etf_lof_type: ETF或LOF型基金（ETF、LOF、UN）
        is_class_fund: 是否分级基金（1：母基金，2：子基金A，3：子基金B，0：否）
        index_fund_type: 基金指数型属性（I：指数型，EI：指数增强型，UN：非指数基金）
        status: 上市状态（L：上市；S：暂停；DE：终止上市；UN：未上市）
        fund_status: 基金状态（A:存续中，E:已到期，UN:未成立）
        fields: 返回字段列表
    返回:
        pd.DataFrame: 基金基本信息
    注意：
        对于未上市的基金目前统一设计为场外基金（交易市场代码：OF），等交易所上市后其会被修改为场内基金（交易市场代码：SH或SZ）。
    """
    validate_extra_params(kwargs)

    params = {
        'symbol': symbol,
        'exchange': exchange,
        'type': type,
        'operation_mode': operation_mode,
        'etf_lof_type': etf_lof_type,
        'is_class_fund': is_class_fund,
        'index_fund_type': index_fund_type,
        'status': status,
        'fund_status': fund_status,
        'fields': fields,
    }
    type_config = {
        'symbol': str,
        'exchange': str,
        'type': str,
        'operation_mode': str,
        'etf_lof_type': str,
        'is_class_fund': int,
        'index_fund_type': str,
        'status': str,
        'fund_status': str,
        'fields': str,
    }
    validated = validate_param_types(
        params, type_config,
        allowed_list_params=[
            'symbol', 'exchange', 'type', 'operation_mode',
            'etf_lof_type', 'is_class_fund', 'index_fund_type',
            'status', 'fund_status', 'fields',
        ],
    )

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['type'] is not None:
        validate_no_duplicates(validated['type'], 'type')
    if validated['operation_mode'] is not None:
        validate_no_duplicates(validated['operation_mode'], 'operation_mode')
    if validated['etf_lof_type'] is not None:
        validate_no_duplicates(validated['etf_lof_type'], 'etf_lof_type')
    if validated['is_class_fund'] is not None:
        validate_no_duplicates(validated['is_class_fund'], 'is_class_fund')
    if validated['index_fund_type'] is not None:
        validate_no_duplicates(validated['index_fund_type'], 'index_fund_type')
    if validated['status'] is not None:
        validate_no_duplicates(validated['status'], 'status')
    if validated['fund_status'] is not None:
        validate_no_duplicates(validated['fund_status'], 'fund_status')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    payload: Dict[str, Any] = {}
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    type_list = _normalise_list(validated['type'])
    if type_list is not None:
        payload["type"] = type_list
    op_list = _normalise_list(validated['operation_mode'])
    if op_list is not None:
        payload["operationMode"] = op_list
    etf_list = _normalise_list(validated['etf_lof_type'])
    if etf_list is not None:
        payload["etfLofType"] = etf_list
    class_list = _normalise_list(validated['is_class_fund'])
    if class_list is not None:
        payload["isClassFund"] = class_list
    index_list = _normalise_list(validated['index_fund_type'])
    if index_list is not None:
        payload["indexFundType"] = index_list
    status_list = _normalise_list(validated['status'])
    if status_list is not None:
        payload["status"] = status_list
    fund_status_list = _normalise_list(validated['fund_status'])
    if fund_status_list is not None:
        payload["fundStatus"] = fund_status_list
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_DETAIL), payload=payload)
    if not df.empty and "symbol" in df.columns:
        df = _reorder_columns(df, ["symbol"])
    if "is_class_fund" in df.columns:
        df['is_class_fund'] = df['is_class_fund'].astype(int)
    if "clearing_speed" in df.columns:
        df['clearing_speed'] = df['clearing_speed'].fillna(0)
        df['clearing_speed'] = df['clearing_speed'].astype(int)
    return df


def get_fund_daily(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取基金日行情数据

    参数:
        start_date: 开始日期（交易日期），格式 YYYYMMDD（必填）
        end_date: 结束日期（交易日期），格式 YYYYMMDD（必填）
        symbol: 基金代码
        exchange: 交易市场
        fields: 返回字段列表
    返回:
        pd.DataFrame: 基金日行情数据
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {'symbol': symbol, 'exchange': exchange, 'fields': fields}
    type_config = {'symbol': str, 'exchange': str, 'fields': str}
    validated = validate_param_types(params, type_config, allowed_list_params=['symbol', 'exchange', 'fields'])

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    validated_start = validate_date_format(start_date, "start_date")
    validated_end = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start, validated_end)
    validate_date_interval(validated_start, validated_end, max_years=1)

    payload: Dict[str, Any] = {}
    payload["startDate"] = validated_start
    payload["endDate"] = validated_end
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_DAILY), payload=payload)
    return _reorder_columns(df, ["symbol", "date"])


def get_fund_daily_post(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取基金后复权日行情数据

    参数:
        start_date: 开始日期（交易日期），格式 YYYYMMDD（必填）
        end_date: 结束日期（交易日期），格式 YYYYMMDD（必填）
        symbol: 基金代码
        exchange: 交易市场
        fields: 返回字段列表
    返回:
        pd.DataFrame: 基金后复权日行情数据
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {'symbol': symbol, 'exchange': exchange, 'fields': fields}
    type_config = {'symbol': str, 'exchange': str, 'fields': str}
    validated = validate_param_types(params, type_config, allowed_list_params=['symbol', 'exchange', 'fields'])

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    validated_start = validate_date_format(start_date, "start_date")
    validated_end = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start, validated_end)
    validate_date_interval(validated_start, validated_end, max_years=1)

    payload: Dict[str, Any] = {}
    payload["startDate"] = validated_start
    payload["endDate"] = validated_end
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_DAILY_POST), payload=payload)
    return _reorder_columns(df, ["symbol", "date"])


def get_fund_daily_pre(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取基金前复权日行情数据

    参数:
        start_date: 开始日期（交易日期），格式 YYYYMMDD（必填）
        end_date: 结束日期（交易日期），格式 YYYYMMDD（必填）
        symbol: 基金代码
        exchange: 交易市场
        fields: 返回字段列表
    返回:
        pd.DataFrame: 基金前复权日行情数据
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {'symbol': symbol, 'exchange': exchange, 'fields': fields}
    type_config = {'symbol': str, 'exchange': str, 'fields': str}
    validated = validate_param_types(params, type_config, allowed_list_params=['symbol', 'exchange', 'fields'])

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    validated_start = validate_date_format(start_date, "start_date")
    validated_end = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start, validated_end)
    validate_date_interval(validated_start, validated_end, max_years=1)

    payload: Dict[str, Any] = {}
    payload["startDate"] = validated_start
    payload["endDate"] = validated_end
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_DAILY_PRE), payload=payload)
    return _reorder_columns(df, ["symbol", "date"])


def get_fund_etf_cr(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取ETF基金申赎清单

    参数:
        start_date: 开始日期（交易日期），格式 YYYYMMDD（必填）
        end_date: 结束日期（交易日期），格式 YYYYMMDD（必填）
        symbol: 基金代码
        exchange: 交易市场
        fields: 返回字段列表
    返回:
        pd.DataFrame: ETF基金申赎清单数据
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {'symbol': symbol, 'exchange': exchange, 'fields': fields}
    type_config = {'symbol': str, 'exchange': str, 'fields': str}
    validated = validate_param_types(params, type_config, allowed_list_params=['symbol', 'exchange', 'fields'])

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    validated_start = validate_date_format(start_date, "start_date")
    validated_end = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start, validated_end)
    validate_date_interval(validated_start, validated_end, max_years=1)

    payload: Dict[str, Any] = {}
    payload["startDate"] = validated_start
    payload["endDate"] = validated_end
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_ETF_CR), payload=payload)
    return _reorder_columns(df, ["symbol", "date"])


def get_fund_etf_constituents(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取ETF基金申赎清单成分券信息

    参数:
        start_date: 开始日期（交易日期），格式 YYYYMMDD（必填）
        end_date: 结束日期（交易日期），格式 YYYYMMDD（必填）
        symbol: 基金代码
        exchange: 交易市场
        fields: 返回字段列表
    返回:
        pd.DataFrame: ETF申赎清单成分券信息
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {'symbol': symbol, 'exchange': exchange, 'fields': fields}
    type_config = {'symbol': str, 'exchange': str, 'fields': str}
    validated = validate_param_types(params, type_config, allowed_list_params=['symbol', 'exchange', 'fields'])

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    validated_start = validate_date_format(start_date, "start_date")
    validated_end = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start, validated_end)
    validate_date_interval(validated_start, validated_end, max_years=1)

    payload: Dict[str, Any] = {}
    payload["startDate"] = validated_start
    payload["endDate"] = validated_end
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_ETF_CONSTITUENTS), payload=payload)
    return _reorder_columns(df, ["symbol", "date"])


def get_fund_etf_net(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取ETF净申赎数据

    参数:
        start_date: 开始日期（交易日期），格式 YYYYMMDD（必填）
        end_date: 结束日期（交易日期），格式 YYYYMMDD（必填）
        symbol: 基金代码
        exchange: 交易市场
        fields: 返回字段列表
    返回:
        pd.DataFrame: ETF净申赎数据
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {'symbol': symbol, 'exchange': exchange, 'fields': fields}
    type_config = {'symbol': str, 'exchange': str, 'fields': str}
    validated = validate_param_types(params, type_config, allowed_list_params=['symbol', 'exchange', 'fields'])

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    validated_start = validate_date_format(start_date, "start_date")
    validated_end = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start, validated_end)
    validate_date_interval(validated_start, validated_end, max_years=1)

    payload: Dict[str, Any] = {}
    payload["startDate"] = validated_start
    payload["endDate"] = validated_end
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_ETF_CONSTITUENT), payload=payload)
    data = _reorder_columns(df, ["symbol", "date"])
    if "name" in data.columns:
        data = data.drop(columns=["name"])
    return data


def get_fund_etf_cr_limits(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取ETF申赎限制数据

    参数:
        start_date: 开始日期（交易日期），格式 YYYYMMDD（必填）
        end_date: 结束日期（交易日期），格式 YYYYMMDD（必填）
        symbol: 基金代码
        exchange: 交易市场
        fields: 返回字段列表
    返回:
        pd.DataFrame: ETF申赎限制数据
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {'symbol': symbol, 'exchange': exchange, 'fields': fields}
    type_config = {'symbol': str, 'exchange': str, 'fields': str}
    validated = validate_param_types(params, type_config, allowed_list_params=['symbol', 'exchange', 'fields'])

    if validated['symbol'] is not None:
        validate_fund_symbol_format(validated['symbol'])
        validate_no_duplicates(validated['symbol'], 'symbol')
    if validated['exchange'] is not None:
        validate_no_duplicates(validated['exchange'], 'exchange')
    if validated['fields'] is not None:
        validate_no_duplicates(validated['fields'], 'fields')

    validated_start = validate_date_format(start_date, "start_date")
    validated_end = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start, validated_end)
    validate_date_interval(validated_start, validated_end, max_years=1)

    payload: Dict[str, Any] = {}
    payload["startDate"] = validated_start
    payload["endDate"] = validated_end
    symbols = _normalise_symbols(validated['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated['fields']:
        payload["fields"] = validated['fields']

    df = fetch_dataframe(build_endpoint(FUND_ENDPOINT, PATH_GET_FUND_ETF_CR_LIMITS), payload=payload)
    data = _reorder_columns(df, ["symbol", "date"])
    if "name" in data.columns:
        data = data.drop(columns=["name"])
    return data
