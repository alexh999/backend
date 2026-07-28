from __future__ import annotations

from typing import List, Optional, Union

import pandas as pd

from panda_data.core.service import fetch_dataframe
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_extra_params,
    validate_no_duplicates,
    validate_not_empty,
    validate_option_symbol_format,
    validate_param_types, validate_date_format, validate_date_range,
)

BASE_ENDPOINT = "/option"
PATH_GET_OPTION_BASIC_INFORMATION = "/getOptionDetailData"
PATH_GET_OPTION_PRODUCT_INFORMATION = "/getOptionUnderlyingDetailData"
PATH_GET_OPTION_MARKET_DATA = "/getOptionMarketData"
PATH_GET_OPTION_IMPLIED_VOLATILITY = "/getOptionImpliedVolatilityData"
PATH_GET_OPTION_UDERLYING_HISTORICAL_VOLATILITY = "/getOptionUnderlyingVolatilityData"
PATH_GET_OPTION_EXERCISE = "/getOptionExerciseData"
PATH_GET_OPTION_SPOT_MARKET = "/getOptionSpotMarketData"
PATH_GET_OPTION_RISK_INDICATORS = "/getOptionRiskIndicatorsData"
PATH_GET_OPTION_STATIC = "/getOptionStaticData"


def get_option_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        status: Optional[bool] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        option_type: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期权基本信息

    Args:
        symbol (str or list of str, optional): 期权代码，非必填
        status (bool, optional): 是否包含已退市和未上市的期权，非必填
        exchange (str or list of str, optional): 交易市场，非必填
        option_type (str or list of str, optional): 品种类别，非必填
        fields (str or list of str, optional): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_option_detail(
        ...     exchange=['SH'],
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'exchange': exchange,
        'option_type': option_type,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'option_type': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'option_type', 'fields']
    )

    # 验证 symbol 列表中是否有重复值,格式是否合法
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]
        validate_option_symbol_format(validated_params['symbol'])

    # 验证 exchange 列表中是否有重复值
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')
        validated_params['exchange'] = [item.strip().upper() for item in validated_params['exchange']]

    # 验证 option_type 列表中是否有重复值
    if validated_params['option_type'] is not None:
        validate_no_duplicates(validated_params['option_type'], 'option_type')
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 构建请求负载
    payload = {}
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if status is not None:
        payload["status"] = status
    if validated_params['exchange'] is not None:
        payload["exchange"] = validated_params['exchange']
    if validated_params['option_type'] is not None:
        payload["optionType"] = validated_params['option_type']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_BASIC_INFORMATION), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_underlying_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期权品种信息

    Args:
        symbol (str or list of str, optional): 期权代码，非必填
        exchange (str or list of str, optional): 交易市场，非必填
        fields (str or list of str, optional): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_option_underlying_detail(
        ...     symbol=['a', 'SC'],
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
    # 验证参数类型
    params = {
        'symbol': symbol,
        'exchange': exchange,
        'fields': fields,
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'fields': str,
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'fields']
    )

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]
        # validate_option_symbol_format(validated_params['symbol'])

    # 验证 exchange 列表中是否有重复值
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')
        validated_params['exchange'] = [item.strip().upper() for item in validated_params['exchange']]
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 构建请求负载
    payload = {}
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['exchange'] is not None:
        payload["exchange"] = validated_params['exchange']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_PRODUCT_INFORMATION), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_market_data(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取期权行情数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"，与结束日期间不超过5年
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"，与开始日期间不超过5年
        symbol: 期权代码列表，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 期权行情数据，包含以下字段：
            - date: 日期
            - symbol: 期权代码
            - ticker_symbol: 证券简称
            - exchange: 交易市场(SHF/DCE/CZC/INE/CFE/SH/SZ/GFE)
            - pre_settlement: 前结算价
            - pre_close: 前收盘价
            - open: 当日开盘价
            - high: 当日最高价
            - low: 当日最低价
            - close: 当日收盘价
            - settlement: 当日结算价
            - volume: 当日成交量
            - amount: 当日成交金额
            - open_interest: 持仓量
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "date" not in fields:
            fields.append("date")
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

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]
        validate_option_symbol_format(validated_params['symbol'])
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_MARKET_DATA), payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_implied_volatility(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期权隐含波动率

    Args:
        start_date (str): 开始日期，格式 "YYYYMMDD"，如 "20250702"，与结束日期间不超过5年，非必填
        end_date (str): 结束日期，格式 "YYYYMMDD"，如 "20250702"，与开始日期间不超过5年，非必填
        symbol (str or list of str, optional): 期权代码，非必填
        fields (str or list of str, optional): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_option_implied_volatility(
        ...     start_date='20260310',
        ...     end_date='20260310',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "date" not in fields:
            fields.append("date")
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

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]
        validate_option_symbol_format(validated_params['symbol'])

    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_IMPLIED_VOLATILITY), payload=payload)

    # 整理列顺序
    if not df.empty and {'ddate', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["ddate", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_underlying_volatility(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        period: Optional[int] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期权标的历史波动率

    Args:
        start_date (str): 开始日期，格式 "YYYYMMDD"，如 "20250702"，与结束日期间不超过5年，非必填
        end_date (str): 结束日期，格式 "YYYYMMDD"，如 "20250702"，与开始日期间不超过5年，非必填
        symbol (str or list of str, optional): 期权标的代码，非必填
        exchange (str or list of str, optional): 交易市场，非必填
        period (int, optional): 历史波动率期限，可选值：5/10/30/60/90/120/180/250/500，非必填
        fields (str or list of str, optional): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_option_underlying_volatility(
        ...     start_date='20260310',
        ...     end_date='20260310',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "date" not in fields:
            fields.append("date")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'exchange': exchange,
        'period': period,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'period': int,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'period', 'fields']
    )

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]

    # 验证 exchange 列表中是否有重复值
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')
        validated_params['exchange'] = [item.strip().upper() for item in validated_params['exchange']]

    # 验证 period 参数
    valid_periods = [5, 10, 30, 60, 90, 120, 180, 250, 500]
    if period is not None:
        if not isinstance(period, int) or period <= 0:
            raise ValueError(f"period 必须为正整数")
        if period not in valid_periods:
            raise ValueError(f"period 必须为以下值之一: {valid_periods}")
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['exchange'] is not None:
        payload["exchange"] = validated_params['exchange']
    if period is not None:
        payload["period"] = period
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_UDERLYING_HISTORICAL_VOLATILITY),
                         payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_exercise(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        call_put_code: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取期权行权交收信息

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 期权代码列表，不传则查询所有
        call_put_code: 认购认沽编码列表，可选值：CO(认购期权), PO(认沽期权), CP(认购、认沽期权)
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 期权行权交收信息数据，包含以下字段：
            - symbol: 期权代码
            - date: 行权日
            - call_put_code: 认购认沽编码(CO:认购期权,PO:认沽期权;CP:认购、认沽期权)
            - exercise_volume: 行权数量
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "date" not in fields:
            fields.append("date")

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'call_put_code': call_put_code,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'call_put_code': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'call_put_code', 'fields']
    )

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]
        # validate_option_symbol_format(validated_params['symbol'])

    # 验证 call_put_code 列表中是否有重复值
    if validated_params['call_put_code'] is not None:
        validate_no_duplicates(validated_params['call_put_code'], 'call_put_code')
        validated_params['call_put_code'] = [item.strip().upper() for item in validated_params['call_put_code']]

    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['call_put_code'] is not None:
        payload["callPutCode"] = validated_params['call_put_code']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_EXERCISE), payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_spot_market(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取现货日行情

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 交易代码列表，见上海黄金交易所，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 现货日行情数据，包含以下字段：
            - symbol: 交易代码
            - name: 证券简称
            - exchange: 交易所代码
            - date: 交易日期
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - change: 涨跌额
            - change_rate: 涨跌幅
            - vwap: 加权平均价
            - volume: 成交量
            - amount: 成交金额
            - open_interest: 持仓量
            - settlement_direction: 交收方向(0:多支付空,1:空支付多)
            - settlement_volume: 交收数量
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "date" not in fields:
            fields.append("date")

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

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]

    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_SPOT_MARKET), payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_risk_indicators(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取期权风险指标

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 交易代码列表，不传则查询所有
        exchange: 交易市场列表，可选值：SHF(上海期货交易所), SZ(深圳证券交易所), SH(上海证券交易所),
                  DCE(大连商品交易所), GFE(广州期货交易所), CZC(郑州商品交易所),
                  INE(上海国际能源交易中心), CFE(中国金融期货交易所)
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 期权风险指标数据，包含以下字段：
            - symbol: 交易代码
            - name: 合约简称
            - exchange: 交易市场
            - date: 交易日期
            - delta: DELTA，期权价格对标的价格的敏感度
            - theta: THETA，期权价格对到期时间的敏感度
            - gamma: GAMMA，DELTA对标的价格的敏感度
            - vega: VEGA，期权价格对隐含波动率的敏感度
            - rho: RHO，期权价格对无风险利率的敏感度
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "date" not in fields:
            fields.append("date")

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'exchange': exchange,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'fields']
    )

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]

    # 验证 exchange 列表中是否有重复值
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')
        validated_params['exchange'] = [item.strip().upper() for item in validated_params['exchange']]

    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['exchange'] is not None:
        payload["exchange"] = validated_params['exchange']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_RISK_INDICATORS), payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_option_static(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        status: Optional[Union[str, List[str]]] = None,
        call_put_code: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取期权每日盘前静态数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 交易代码列表，不传则查询所有
        exchange: 交易市场列表，可选值：SHF(上海期货交易所), SZ(深圳证券交易所), SH(上海证券交易所),
                  DCE(大连商品交易所), GFE(广州期货交易所), CZC(郑州商品交易所),
                  INE(上海国际能源交易中心), CFE(中国金融期货交易所)
        underlying_symbol: 标的交易代码列表，不传则查询所有
        status: 合约状态列表，不传则查询所有
        call_put_code: 认购认沽编码列表，可选值：CO(认购期权), PO(认沽期权)
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 期权每日盘前静态数据，包含以下字段：
            - date: 交易日期
            - name: 合约简称
            - symbol: 交易代码
            - exchange: 交易市场
            - underlying_name: 标的证券简称
            - underlying_symbol: 标的交易代码
            - underlying_type: 标的证券类型(ETF：期权)
            - exercise_style: 履约方式编码(E：欧式)
            - call_put_code: 认购认沽编码(CO：认购期权,PO：认沽期权)
            - contract_size: 合约单位(经过除权除息调整)
            - strike_price: 行权价格(经过除权除息调整)
            - listed_date: 挂牌日期
            - last_date: 最后交易日
            - exercise_date: 行权日期
            - settlement_date: 交收日期
            - delisted_date: 合约到期日
            - contract_version: 合约版本号
            - open_interest: 昨持仓量
            - pre_close: 前收盘价
            - pre_settlement: 前结算价
            - underlying_pre_close: 标的证券前收盘
            - limit_type: 涨跌幅限类型(N：有涨跌幅限制)
            - limit_up: 涨幅上限价格
            - limit_down: 跌幅下限价格
            - margin: 单位保证金(当日持有一张合约所需要的保证金数量，精确到分)
            - margin_ratio1: 交易所保证金计算比例参数一
            - margin_ratio2: 交易所保证金计算比例参数二
            - lot_size: 整手数(一手对应的合约数)
            - limit_down_volume: 单笔限价申报张数下限
            - limit_up_volume: 单笔限价申报张数上限
            - market_down_volume: 单笔市价申报张数下限
            - market_up_volume: 单笔市价申报张数上限
            - tick_size: 最小报价变动数值
            - status: 合约状态(8位字符串，每位表示特定含义)

    合约状态说明：
        上交所：20191115前是5位字符串，之后该字段为8位字符串，从左起每位表示特定的含义，无定义则填空格。
        第1位：'0'表示可开仓，'1'表示限制卖出开仓（不包括备兑开仓）和买入开仓。
        第2位：'0'表示未连续停牌，'1'表示连续停牌。
        第3位：'0'表示未临近到期日，'1'表示距离到期日不足 5 个交易日。
        第4位：'0'表示近期未做调整，'1'表示最近 5 个交易日内合约发生过调整。
        第5位：'A'表示当日新挂牌的合约，'E'表示存续的合约。
        第6位：'1'表示合约只能进行跨式和宽跨式的组合策略，'0'表示可以进行所有的组合策略。
        深交所：
        6代表上市首日，13代表合约调整
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "date" not in fields:
            fields.append("date")

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'exchange': exchange,
        'underlying_symbol': underlying_symbol,
        'status': status,
        'call_put_code': call_put_code,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'underlying_symbol': str,
        'status': str,
        'call_put_code': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'underlying_symbol', 'status', 'call_put_code', 'fields']
    )

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validated_params['symbol'] = [item.strip().upper() for item in validated_params['symbol']]

    # 验证 exchange 列表中是否有重复值
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')
        validated_params['exchange'] = [item.strip().upper() for item in validated_params['exchange']]

    # 验证 underlying_symbol 列表中是否有重复值
    if validated_params['underlying_symbol'] is not None:
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')
        validated_params['underlying_symbol'] = [item.strip().upper() for item in validated_params['underlying_symbol']]

    # 验证 status 列表中是否有重复值
    if validated_params['status'] is not None:
        validate_no_duplicates(validated_params['status'], 'status')
        validated_params['status'] = [item.strip().upper() for item in validated_params['status']]

    # 验证 call_put_code 列表中是否有重复值
    if validated_params['call_put_code'] is not None:
        validate_no_duplicates(validated_params['call_put_code'], 'call_put_code')
        validated_params['call_put_code'] = [item.strip().upper() for item in validated_params['call_put_code']]

    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['exchange'] is not None:
        payload["exchange"] = validated_params['exchange']
    if validated_params['underlying_symbol'] is not None:
        payload["underlyingSymbol"] = validated_params['underlying_symbol']
    if validated_params['status'] is not None:
        payload["status"] = validated_params['status']
    if validated_params['call_put_code'] is not None:
        payload["callPutCode"] = validated_params['call_put_code']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_OPTION_STATIC), payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df
