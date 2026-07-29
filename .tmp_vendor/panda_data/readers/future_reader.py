from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Union
from urllib.parse import urljoin

import pandas as pd
import requests

from panda_data.config import get_config
from panda_data.core.service import request_service
from panda_data.core.service import fetch_dataframe
from panda_data.exceptions import ServiceError, ServiceErrorCode
from panda_data.utils.common_utils import find_project_root
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_broker_grade,
    validate_date_format,
    validate_date_interval,
    validate_date_range,
    validate_extra_params,
    validate_future_symbol_format,
    validate_future_underlying_symbol_format,
    validate_is_trading_day,
    validate_max_rank,
    validate_no_duplicates,
    validate_not_empty,
    validate_param_types,
    validate_position_type,
    validate_positive_integer, validate_rank_type,
)

config = get_config()
BASE_ENDPOINT = "/future"
PATH_GET_FUTURE_LIST = "/getFutureList"
PATH_GET_FUTURE_FACTOR_POST = "/getFutureMarketPostData"
PATH_GET_FUTURE_DAILY_POST_MARKET = "/getFutureDailyPostMarketData"
PATH_GET_FUTURE_DOMINANT = "/getFutureDominantData"
PATH_GET_FUTURE_NETPOSI_RANK = "/getFutureNetposiRankData"
PATH_GET_FUTURE_SYMBOL_POSI_RANK = "/getFutureSymbolPosiRankData"
PATH_GET_FUTURE_VARIETY_POSI_RANK = "/getFutureVarietyPosiRankData"
PATH_GET_FUTURE_CONTRACT_DAILY_INDICATORS = "/getFutureContractDailyIndicatorsData"
PATH_GET_FUTURE_NET_FLOW = "/getFutureNetFlowData"
PATH_GET_BROKER_VARIETY_PROFIT = "/getBrokerVarietyProfitData"
PATH_GET_BROKER_GRADE = "/getBrokerGradeData"
PATH_GET_BROKER_NET_MARGIN = "/getBrokerNetMarginData"
PATH_GET_BROKER_NET_MARGIN_CHANGE = "/getBrokerNetMarginChangeData"
PATH_GET_BROKER_TOTAL_MARGIN = "/getBrokerTotalMarginData"
PATH_GET_FUTURE_BASIS = "/getFutureBasisData"
PATH_GET_FUTURE_WR = "/getFutureWRData"
PATH_GET_FUTURE_LS_RATIO = "/getFutureLSRatioData"
PATH_GET_FUTURE_CONTRACT_RANK = "/getFutureContractRankData"
PATH_GET_FUTURE_NET_CAP_CHANGE = "/getFutureNetCapChangeData"
PATH_GET_FUTURE_TERM_STRUCTURE = "/getFutureTermStructureData"
PATH_GET_FUTURE_INVENTORY = "/getFutureInventoryData"
PATH_GET_FUTURE_RESEARCH_REPORT = "/getFutureResearchReportData"
PATH_GET_FUTURE_SYMBOL_OI_VALUE = "/getFutureSymbolOiValueData"
PATH_GET_FUTURE_CONTRACT_POOL = "/getFutureContractPoolData"
PATH_GET_FUTURE_BROKER_POSITION = "/getFutureBrokerPositionData"
PATH_GET_FUTURE_BROKER_PROFIT = "/getFutureBrokerProfitData"
PATH_GET_FUTURE_BROKER_MARGIN_FLOW_DAILY = "/getFutureBrokerMarginFlowDailyData"
PATH_GET_FUTURE_BROKER_LS_RATIO = "/getFutureBrokerLsRatioData"
PATH_GET_FUTURE_NONBROKER_NET_OI = "/getFutureNonbrokerNetOiData"
PATH_GET_FUTURE_VARIETY_BROKER_PROFIT = "/getFutureVarietyBrokerProfitData"
PATH_GET_FUTURE_CROSS_TERM_ARBITRAGE = "/getFutureCrossTermArbitrageData"
PATH_GET_FUTURE_FREE_SPREAD = "/getFutureFreeSpreadData"
PATH_GET_FUTURE_FREE_RATIO = "/getFutureFreeRatioData"
PATH_GET_FUTURE_DOMINANT_CORRELATION_MATRIX = "/getFutureDominantCorrelationMatrixData"
PATH_GET_FUTURE_SAT_PROFIT_RANKING = "/getFutureSatProfitData"
PATH_GET_FUTURE_SAT_LOSS_RANKING = "/getFutureSatLossData"
PATH_GET_FUTURE_POSITION_BUILDING_PROCESS = "/getFutureBuildingProcessData"
PATH_GET_FUTURE_CAP_VALUE = "/getFutureCapValueData"
PATH_GET_FUTURE_SEAT_MATCHING = "/getFutureSeatMatchingData"
PATH_GET_FUTURE_RATIO_OF_VIRTUAL_TO_REAL_POSITIONS = "/getFutureRatioVitualRealData"
PATH_GET_FUTURE_SPOT_PROFIT = "/getFutureSpotProfitData"
PATH_GET_FUTURE_SPOT_TRADER_QUOTATION = "/getFutureTraderQuotationData"
PATH_DOWNLOAD_FUTURE_RESEARCH_REPORT = "/downloadFutureResearchReport"


def get_future_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        is_trading: Optional[int] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货基本信息

    Args:
        symbol (string): 期货代码，非必填
        fields (string): 返回字段列表，非必填
        exchange (string): 期货交易所后缀，非必填
        is_trading (integer): 是否可交易，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_detail(
        ...     symbol=["A0303.DCE", "ZN_DOMINANT.SHF"],
        ...     fields=[],
        ...     is_trading=None,
        ... )
    """
    validate_extra_params(kwargs)
    # 验证参数类型
    params = {
        'symbol': symbol,
        'fields': fields,
        'exchange': exchange,
    }

    type_config = {
        'symbol': str,
        'fields': str,
        'exchange': str,
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'fields', 'exchange']
    )

    # 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_future_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证 exchange 列表中是否有重复值及取值范围
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')
        validated_params['exchange'] = [item.strip().upper() for item in validated_params['exchange']]
        valid_exchanges = {"CFE", "CZC", "DCE", "SHF", "INE", "GFE"}
        invalid_exchanges = [item for item in validated_params['exchange'] if item not in valid_exchanges]
        if invalid_exchanges:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_INVALID,
                message=(
                    f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] exchange参数值"
                    f"{invalid_exchanges}无效: 有效值为 CFE、CZC、DCE、SHF、INE、GFE"
                ),
            )

    # 验证is_trading参数
    validated_is_trading = validate_is_trading_day(is_trading, "is_trading") if is_trading is not None else is_trading

    payload = {}
    if validated_is_trading is not None and validated_is_trading in [0, 1]:
        payload["isTrading"] = validated_is_trading
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_params['exchange'] is not None:
        payload["exchange"] = validated_params['exchange']

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_LIST), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_daily_post(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货后复权数据

    Args:
        symbol (string): 期货代码，非必填
        start_date (string): 开始日期,eg:"20250702" （查询上市日期），非必填
        end_date (string): 结束日期,eg:"20250702" （查询上市日期），非必填
        fields (string): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_daily_post(
        ...     symbol=["A2511.DCE", "P2607.DCE","A_DOMINANT.DCE"],
        ...     start_date="20251101",
        ...     end_date="20251105",
        ...     fields=[],
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")  # 验证参数类型
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
        validate_future_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_FACTOR_POST), payload=payload)
    if not df.empty:
        df = df.drop(columns=["total_turnover"], errors="ignore")
        if {"symbol", "date"}.issubset(df.columns):
            cols = df.columns.tolist()
            priority_cols = ["symbol", "date"]
            other_cols = [col for col in cols if col not in priority_cols]
            df = df[priority_cols + other_cols]
    return df


def get_future_daily_post_market(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        method: str = "close_pcs",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货主力合约后复权行情数据（future_post_market，4 种复权方法）。

    参数：
        underlying_symbol (str 或 list, 可选): 品种编码，如 "A" 或 ["A", "CF"]，默认为空返回全部品种。
        method (str, 可选): 复权方法，可选 close_pcs/close_os/close_pcr/close_or，默认 close_pcs。
        fields (list, 可选): 返回字段子集；无论如何限制固定返回 symbol、date、dominant_id 三列。

    说明：
        symbol 为主力合约代码（郑商所为交易所标准 3 位年月，如 CF509.CZC）；
        dominant_id 为品种级主力连续标识（如 A_dominant.DCE）。
        郑商所改代码品种（WS→WH/ME→MA/TC→ZC/RO→OI/ER→RI/WT→PM）新旧编码各查各的区间。
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields']
    )

    # 验证underlying_symbol列表中是否有重复值（空值会被正确处理）
    if validated_params['underlying_symbol'] is not None:
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')
        # 将underlying_symbol的每一项变为全大写
        validated_params['underlying_symbol'] = [s.upper() for s in validated_params['underlying_symbol']]

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # method：非必填，默认 close_pcs，校验合法值
    allowed_methods = {"close_pcs", "close_os", "close_pcr", "close_or"}
    validated_method = "close_pcs" if method is None else str(method).strip()
    if validated_method not in allowed_methods:
        raise ValueError(f"method 取值非法：{method}，仅支持 {sorted(allowed_methods)}")

    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["underlyingSymbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_method is not None:
        payload["method"] = validated_method
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_DAILY_POST_MARKET), payload=payload)
    if not df.empty:
        priority_cols = [c for c in ["symbol", "date", "dominant_id"] if c in df.columns]
        if priority_cols:
            other_cols = [col for col in df.columns if col not in priority_cols]
            df = df[priority_cols + other_cols]
    return df


def get_future_dominant(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货主力合约数据

    Args:
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_dominant(
        ...     underlying_symbol=["A","AG"],
        ...     start_date="20250701",
        ...     end_date="20250710",
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol
    }

    type_config = {
        'underlying_symbol': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol']
    )

    # 验证underlying_symbol列表中是否有重复值
    validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    # 将underlying_symbol的每一项变为全大写
    if validated_params['underlying_symbol'] is not None:
        validated_params['underlying_symbol'] = [symbol.upper() for symbol in validated_params['underlying_symbol']]

    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["underlyingSymbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_DOMINANT), payload=payload)
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_netposi_rank(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        max_rank: Optional[int] = None,
        fields: Optional[Union[str, List[str]]] = None,
        type: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货商品净持仓多空榜单数据

    Args:
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        max_rank (integer): 最大排行，查询排名小于等于该值的数据，非必填
        type (string): 多空方向，可填long或short，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_netposi_rank(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     underlying_symbol="A",
        ...     max_rank=10,
        ...     type="long",
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields']
    )

    # 验证 underlying_symbol 格式
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [symbol.upper() for symbol in validated_params['underlying_symbol']]

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 验证 max_rank 参数
    validated_max_rank = validate_max_rank(max_rank, "max_rank") if max_rank is not None else None

    # 验证 type 参数
    validated_type = validate_position_type(type, "type") if type is not None else None

    # 构建请求负载
    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["symbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_max_rank is not None:
        payload["maxRank"] = validated_max_rank
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_type is not None:
        payload["type"] = validated_type

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_NETPOSI_RANK), payload=payload)

    # 整理列顺序
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_future_symbol_posi_rank(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        position_type: Optional[str] = None,
        broker_name: Optional[str] = None,
        rank_max: Optional[int] = 20,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货合约持仓数据

    Args:
        symbol (Optional[Union[string, List[string]]]): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，必填
        end_date (string): 结束日期,eg:"20250802"，必填
        position_type (string): 多:"long"，空:"short"，非必填
        broker_name (string): 席位名称，非必填
        rank_max (int32): 排名，非必填
        fields (Optional[Union[string, List[string]]]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_symbol_posi_rank(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     symbol=["A2503.DCE"],
        ...     position_type="long",
        ...     broker_name="新湖期货",
        ...     rank_max=3,
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
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
        allowed_list_params=["symbol", "fields"]
    )

    if validated_params["symbol"] is not None:
        validate_no_duplicates(validated_params["symbol"], "symbol")
        # 合约/品种代码统一转大写
        validated_params["symbol"] = [s.upper() for s in validated_params["symbol"]]
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_position_type = validate_position_type(position_type,
                                                     "position_type") if position_type is not None else None
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    validated_rank_max = validate_positive_integer(rank_max, "rank_max") if rank_max is not None else 20

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_position_type is not None:
        payload["positionType"] = validated_position_type
    if broker_name is not None and str(broker_name).strip():
        payload["brokerName"] = str(broker_name).strip()
    if validated_rank_max is not None:
        payload["rankMax"] = validated_rank_max
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_SYMBOL_POSI_RANK), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    elif not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_variety_posi_rank(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        position_type: Optional[str] = None,
        broker_name: Optional[str] = None,
        rank_max: Optional[int] = 20,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货商品持仓数据

    Args:
        symbol (string): 期货商品，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        position_type (string): 多:"long"，空:"short"，非必填
        broker_name (string): 席位名称，非必填
        rank_max (integer): 排名，非必填
        fields (string): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_variety_posi_rank(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     symbol=["A"],
        ...     position_type="long",
        ...     broker_name="中信期货",
        ...     rank_max=3,
        ... )
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
        sym_uv = validate_future_underlying_symbol_format(validated_params["symbol"])
        validate_no_duplicates(sym_uv, "symbol")
        validated_params["symbol"] = (
            [sym_uv] if isinstance(sym_uv, str) else sym_uv
        )
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)
    validated_position_type = (
        validate_position_type(position_type, "position_type")
        if position_type is not None
        else None
    )
    validated_rank_max = validate_positive_integer(rank_max, "rank_max") if rank_max is not None else None

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_position_type is not None:
        payload["positionType"] = validated_position_type
    if broker_name is not None and str(broker_name).strip():
        payload["brokerName"] = str(broker_name).strip()
    if validated_rank_max is not None:
        payload["rankMax"] = validated_rank_max
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_VARIETY_POSI_RANK), payload=payload)
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_contract_daily_indicators(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货龙虎比、牛熊线

    Args:
        symbol (string): 期货合约:"AL2501.SHF"，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_contract_daily_indicators(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     symbol=["AL2501.SHF", "AG2505.SHF"],
        ... )
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
        validated_params["symbol"] = [s.upper() for s in validated_params["symbol"]]
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_CONTRACT_DAILY_INDICATORS), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_term_structure(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货期限结构数据

    Args:
        symbol (string): 合约代码：“SC2607.INE”，非必填
        start_date (string): 开始日期：“YYYYMMDD”，非必填
        end_date (string): 结束日期：“YYYYMMDD”，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_term_structure(
        ...     symbol=["SC2607.INE","Y2703.DCE"],
        ...     start_date="20260401",
        ...     end_date="20260403",
        ... )
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
        validate_future_symbol_format(validated_params["symbol"])
        validate_no_duplicates(validated_params["symbol"], "symbol")
        validated_params["symbol"] = [s.upper() for s in validated_params["symbol"]]

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_TERM_STRUCTURE), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_inventory(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货库存数据

    Args:
        symbol (string): 合约代码：“SC2607.INE”，非必填
        start_date (string): 开始日期：“YYYYMMDD”，非必填
        end_date (string): 结束日期：“YYYYMMDD”，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_inventory(
        ...     symbol=["RB","HC"],
        ...     start_date="20260401",
        ...     end_date="20260409",
        ... )
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
        sym_uv = validate_future_underlying_symbol_format(validated_params["symbol"])
        validate_no_duplicates(sym_uv, "symbol")
        validated_params["symbol"] = (
            [sym_uv] if isinstance(sym_uv, str) else sym_uv
        )
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_INVENTORY), payload=payload)
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_research_report(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货商品研报数据（future_research_report，Parquet 数据源）。
    symbol 为品种代码（underlying），如 RB、CU，非合约代码。
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
        sym_uv = validate_future_underlying_symbol_format(validated_params["symbol"])
        validate_no_duplicates(sym_uv, "symbol")
        validated_params["symbol"] = [sym_uv] if isinstance(sym_uv, str) else sym_uv
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_RESEARCH_REPORT), payload=payload)
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def download_future_research_report(
        symbol: str,
        date: str,
        pub: str,
        output_path: Optional[str] = None,
        **kwargs,
) -> str:
    """
    下载期货研报 PDF 到本地。
    """
    validate_extra_params(kwargs)
    validate_not_empty(symbol, "symbol")
    validate_not_empty(date, "date")
    validate_not_empty(pub, "pub")
    validated_symbol = validate_future_underlying_symbol_format(symbol)
    validated_date = validate_date_format(date, "date")
    out_path = output_path
    if not out_path:
        safe_pub = str(pub).strip().replace("/", "_").replace("\\", "_")
        default_dir = Path.cwd() / "future_research_report_downloads" / str(validated_symbol).upper() / validated_date
        default_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(default_dir / f"{safe_pub}.pdf")

    # 先请求一次，复用现有鉴权与异常处理逻辑
    _ = request_service(
        endpoint=build_endpoint(BASE_ENDPOINT, PATH_DOWNLOAD_FUTURE_RESEARCH_REPORT),
        method="GET",
        params={
            "underlying_symbol": str(validated_symbol).upper(),
            "date": validated_date,
            "pub": str(pub).strip(),
        },
        data_path=None,
    )

    # 再走二进制流下载
    from panda_data.client import get_client

    client = get_client()
    base_url = client.config.base_url.rstrip("/")
    url = urljoin(base_url + "/", build_endpoint(BASE_ENDPOINT, PATH_DOWNLOAD_FUTURE_RESEARCH_REPORT).lstrip("/"))
    headers = {}
    token_path = Path(find_project_root(str(Path(__file__).parent))) / "user.json"
    if token_path.exists():
        try:
            token_data = json.loads(token_path.read_text(encoding="utf-8"))
            token = token_data.get("token")
            if token:
                headers["Authorization"] = token
        except Exception:
            pass

    response = requests.get(
        url,
        params={
            "underlying_symbol": str(validated_symbol).upper(),
            "date": validated_date,
            "pub": str(pub).strip(),
        },
        stream=True,
        timeout=float(config.get("HTTP_TIMEOUT", "300")),
        headers=headers or None,
    )
    if response.status_code != 200:
        raise ServiceError(f"下载失败，HTTP {response.status_code}: {response.text[:300]}")

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as file_obj:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)
    return str(target.resolve())


def get_future_symbol_oi_value(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        broker: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货席位合约的总持仓市值

    Args:
        symbol (string): list[str]，非必填
        start_date (string): 开始日期，支持 YYYYMMDD，必填
        end_date (string): 结束日期，支持 YYYYMMDD，必填
        broker (string): None，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_symbol_oi_value(
        ...     symbol=["ZN2607.SHF", "A2605.DCE"],
        ...     start_date="20260413",
        ...     end_date="20260413",
        ...     broker="",
        ... )
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
        validate_future_symbol_format(validated_params["symbol"])
        validate_no_duplicates(validated_params["symbol"], "symbol")
        validated_params["symbol"] = [s.upper() for s in validated_params["symbol"]]
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if broker is not None and str(broker).strip():
        payload["broker"] = str(broker).strip()
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_SYMBOL_OI_VALUE), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_contract_pool(
        symbol: Optional[Union[str, List[str]]] = None,
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        position_direction: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货多头空头合约池

    Args:
        symbol (string/list[string]/None): 合约代码（CTP），非必填
        underlying_symbol (string/list[string]/None): 品种代码，非必填
        start_date (string): 开始日期，必填
        end_date (string): 结束日期，必填
        position_direction (string/list[string]/None): long / short，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_contract_pool(
        ...     symbol=[""],
        ...     underlying_symbol=["RB"],
        ...     start_date="20260401",
        ...     end_date="20260427",
        ...     position_direction="long",
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {
        "symbol": symbol,
        "underlying_symbol": underlying_symbol,
        "position_direction": position_direction,
        "fields": fields,
    }
    type_config = {
        "symbol": str,
        "underlying_symbol": str,
        "position_direction": str,
        "fields": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["symbol", "underlying_symbol", "position_direction", "fields"],
    )

    if validated_params["symbol"] is not None:
        validate_future_symbol_format(validated_params["symbol"])
        validate_no_duplicates(validated_params["symbol"], "symbol")
        validated_params["symbol"] = [s.upper() for s in validated_params["symbol"]]
    if validated_params["underlying_symbol"] is not None:
        us = validate_future_underlying_symbol_format(validated_params["underlying_symbol"])
        validate_no_duplicates(us, "underlying_symbol")
        validated_params["underlying_symbol"] = [us] if isinstance(us, str) else us
    if validated_params["position_direction"] is not None:
        directions = validated_params["position_direction"]
        if isinstance(directions, str):
            directions = [directions]
        processed_directions = []
        for direction in directions:
            validated_direction = validate_position_type(direction, "position_direction")
            if validated_direction is not None:
                processed_directions.append(validated_direction)
        validate_no_duplicates(processed_directions, "position_direction")
        validated_params["position_direction"] = processed_directions
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["underlying_symbol"] is not None:
        payload["underlyingSymbol"] = validated_params["underlying_symbol"]
    if validated_params["position_direction"] is not None:
        payload["positionDirection"] = validated_params["position_direction"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_CONTRACT_POOL), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_nonbroker_net_oi(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货非期货公司净持仓

    Args:
        symbol (string): list[str]，非必填
        start_date (string): 开始日期，支持 YYYYMMDD，必填
        end_date (string): 结束日期，支持 YYYYMMDD，必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_nonbroker_net_oi(
        ...     symbol="AG",
        ...     start_date="20180801",
        ...     end_date="20180831",
        ... )
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
        sym_uv = validate_future_underlying_symbol_format(validated_params["symbol"])
        validate_no_duplicates(sym_uv, "symbol")
        validated_params["symbol"] = [sym_uv] if isinstance(sym_uv, str) else sym_uv
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_NONBROKER_NET_OI), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_broker_profit(
        start_date: str,
        end_date: str,
        broker: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货席位盈亏数据

    Args:
        start_date (string): 开始日期，支持 YYYYMMDD，必填
        end_date (string): 结束日期，支持 YYYYMMDD，必填
        broker (string): None，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_broker_profit(
        ...     start_date="20260301",
        ...     end_date="20260416",
        ...     broker="齐盛期货",
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {
        "fields": fields,
    }
    type_config = {
        "fields": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["fields"],
    )

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if broker is not None and str(broker).strip():
        payload["broker"] = str(broker).strip()
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(
        build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_BROKER_PROFIT),
        payload=payload,
    )
    if not df.empty and {"broker", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["broker", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_broker_margin_flow_daily(
        start_date: str,
        end_date: str,
        broker: Optional[str] = None,
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        underlying_symbol_cn: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货席位每日大资金流动数据

    Args:
        start_date (string): 开始日期，支持 YYYYMMDD，必填
        end_date (string): 结束日期，支持 YYYYMMDD，必填
        broker (string): None，非必填
        underlying_symbol (string 或 List[string]): 品种代码筛选（如 RB），非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_broker_margin_flow_daily(
        ...     start_date="20260301",
        ...     end_date="20260416",
        ...     broker="",
        ...     underlying_symbol=["RB","ZN"],
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {
        "fields": fields,
        "underlying_symbol": underlying_symbol,
        "underlying_symbol_cn": underlying_symbol_cn,
    }
    type_config = {
        "fields": str,
        "underlying_symbol": str,
        "underlying_symbol_cn": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["fields", "underlying_symbol", "underlying_symbol_cn"],
    )

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    us_val = validated_params["underlying_symbol"]
    if us_val is not None and isinstance(us_val, list):
        validate_no_duplicates(us_val, "underlying_symbol")

    us_cn_val = validated_params["underlying_symbol_cn"]
    if us_cn_val is not None and isinstance(us_cn_val, list):
        validate_no_duplicates(us_cn_val, "underlying_symbol_cn")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if broker is not None and str(broker).strip():
        payload["broker"] = str(broker).strip()
    if us_val is not None:
        if isinstance(us_val, str):
            if us_val.strip():
                payload["underlyingSymbol"] = [us_val.strip()]
        else:
            sym_list = [str(x).strip() for x in us_val if x is not None and str(x).strip()]
            if sym_list:
                payload["underlyingSymbol"] = sym_list
    if us_cn_val is not None:
        if isinstance(us_cn_val, str):
            if us_cn_val.strip():
                payload["underlyingSymbolCn"] = [us_cn_val.strip()]
        else:
            cn_list = [str(x).strip() for x in us_cn_val if x is not None and str(x).strip()]
            if cn_list:
                payload["underlyingSymbolCn"] = cn_list
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(
        build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_BROKER_MARGIN_FLOW_DAILY),
        payload=payload,
    )
    if not df.empty and {"broker", "date", "underlying_symbol", "underlying_symbol_cn"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["broker", "date", "underlying_symbol", "underlying_symbol_cn"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_broker_ls_ratio(
        start_date: str,
        end_date: str,
        broker: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货席位多空比数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        broker (string): 席位名称，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_broker_ls_ratio(
        ...     start_date="20260301",
        ...     end_date="20260416",
        ...     broker=["齐盛期货","一德期货"],
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {
        "broker": broker,
        "fields": fields,
    }
    type_config = {
        "broker": str,
        "fields": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["broker", "fields"],
    )

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")
    if validated_params["broker"] is not None and isinstance(validated_params["broker"], list):
        validate_no_duplicates(validated_params["broker"], "broker")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    broker_val = validated_params["broker"]
    if broker_val is not None:
        if isinstance(broker_val, str):
            if broker_val.strip():
                payload["broker"] = [broker_val.strip()]
        else:
            broker_list = [str(x).strip() for x in broker_val if x is not None and str(x).strip()]
            if broker_list:
                payload["broker"] = broker_list
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(
        build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_BROKER_LS_RATIO),
        payload=payload,
    )
    if not df.empty and {"broker", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["broker", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def _build_future_pair_payload(
        contract_symbol_1: str,
        contract_symbol_2: str,
        date: str,
) -> dict:
    validate_not_empty(contract_symbol_1, "contract_symbol_1")
    validate_not_empty(contract_symbol_2, "contract_symbol_2")
    validate_not_empty(date, "date")

    symbol_params = {
        "contract_symbol_1": contract_symbol_1,
        "contract_symbol_2": contract_symbol_2,
    }
    symbol_types = {
        "contract_symbol_1": str,
        "contract_symbol_2": str,
    }
    validated_symbols = validate_param_types(symbol_params, symbol_types, allowed_list_params=[])

    validated_date = validate_date_format(date, "date")

    symbol1 = _validate_standard_symbol(validated_symbols["contract_symbol_1"], "contract_symbol_1")
    symbol2 = _validate_standard_symbol(validated_symbols["contract_symbol_2"], "contract_symbol_2")

    return {
        "contractSymbol1": symbol1,
        "contractSymbol2": symbol2,
        "date": validated_date,
    }


def _validate_standard_symbol(raw_symbol: str, param_name: str) -> str:
    symbol = str(raw_symbol or "").strip().upper()
    if not symbol:
        raise ValueError(f"{param_name} 不能为空")
    # if not re.match(r"^[A-Z_]+\d{4}(?:[A-Z]+)?\.[A-Z]{3}$", symbol):
    #     raise ValueError(f"{param_name} 必须为标准格式 SYMBOL.EXCHANGE，例如 RB1901.SHF")
    return symbol


def _format_future_pair_result(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty:
        if "cross_term_arbitrage" in df.columns:
            df = df.drop(columns=["close_1", "close_2"], errors="ignore")
        if "cross_term_arbitrage" not in df.columns and ("free_spread" in df.columns or "free_ratio" in df.columns):
            df = df.drop(columns=["settlement_1", "settlement_2"], errors="ignore")
        cols = df.columns.tolist()
        priority_cols = [
            "contract_symbol_1",
            "contract_symbol_2",
            "date",
            "settlement_1",
            "settlement_2",
            "close_1",
            "close_2",
            "cross_term_arbitrage",
            "free_spread",
            "free_ratio",
        ]
        ordered = [c for c in priority_cols if c in cols]
        other_cols = [c for c in cols if c not in ordered]
        df = df[ordered + other_cols]
    return df


def get_future_cross_term_arbitrage(
        contract_symbol_1: str,
        contract_symbol_2: str,
        date: str,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货跨期套利数据

    Args:
        contract_symbol_1 (string): 合约代码1，非必填
        contract_symbol_2 (string): 合约代码2，非必填
        date (string): 日期：“YYYYMMDD”，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_cross_term_arbitrage(
        ...     contract_symbol_1="RB1901.SHF",
        ...     contract_symbol_2="RB1905.SHF",
        ...     date="20180808",
        ... )
    """
    validate_extra_params(kwargs)
    payload = _build_future_pair_payload(contract_symbol_1, contract_symbol_2, date)
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_CROSS_TERM_ARBITRAGE), payload=payload)
    return _format_future_pair_result(df)


def get_future_free_spread(
        contract_symbol_1: str,
        contract_symbol_2: str,
        date: str,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货自由价差数据

    Args:
        contract_symbol_1 (string): 合约代码1，非必填
        contract_symbol_2 (string): 合约代码2，非必填
        date (string): 日期：“YYYYMMDD”，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_free_spread(
        ...     contract_symbol_1="RB1901.SHF",
        ...     contract_symbol_2="HC1901.SHF",
        ...     date="20180808",
        ... )
    """
    validate_extra_params(kwargs)
    payload = _build_future_pair_payload(contract_symbol_1, contract_symbol_2, date)
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_FREE_SPREAD), payload=payload)
    return _format_future_pair_result(df)


def get_future_free_ratio(
        contract_symbol_1: str,
        contract_symbol_2: str,
        date: str,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货自由价比数据

    Args:
        contract_symbol_1 (string): 合约代码1，非必填
        contract_symbol_2 (string): 合约代码2，非必填
        date (string): 日期：“YYYYMMDD”，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_free_ratio(
        ...     contract_symbol_1="RB1901.SHF",
        ...     contract_symbol_2="HC1901.SHF",
        ...     date="20180808",
        ... )
    """
    validate_extra_params(kwargs)
    payload = _build_future_pair_payload(contract_symbol_1, contract_symbol_2, date)
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_FREE_RATIO), payload=payload)
    return _format_future_pair_result(df)


def get_future_dominant_correlation(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
) -> dict:
    """
    获取期货主力合约涨跌幅相关性

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        symbol (string): 期货品种名称，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_dominant_correlation(
        ...     symbol=["RB", "JM", "A"],
        ...     start_date="20250108",
        ...     end_date="20260427",
        ... )
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {"symbol": symbol}
    type_config = {"symbol": str}
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["symbol"],
    )

    if validated_params["symbol"] is None:
        raise ValueError("symbol 不能为空")

    normalized_input = validate_future_underlying_symbol_format(validated_params["symbol"])
    symbol_list = [normalized_input] if isinstance(normalized_input, str) else normalized_input
    symbol_list = [str(s).strip().upper() for s in symbol_list if str(s).strip()]
    validate_no_duplicates(symbol_list, "symbol")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)
    # validate_date_interval(validated_start_date, validated_end_date, max_years=1)

    payload = {
        "symbol": symbol_list,
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    response = request_service(
        endpoint=build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_DOMINANT_CORRELATION_MATRIX),
        payload=payload,
        method="POST",
        data_path=None,
    )
    if isinstance(response, dict) and isinstance(response.get("data"), dict):
        return response["data"]
    if isinstance(response, dict):
        return response
    raise ServiceError("主连相关性矩阵接口返回格式异常")


def get_broker_variety_profit(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        broker: Optional[str] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货席位的商品盈亏数据

    Args:
        symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        broker (string): 席位，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_broker_variety_profit(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     symbol=["M", "LH"],
        ...     broker="创元期货",
        ... )
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
        sym_uv = validate_future_underlying_symbol_format(validated_params["symbol"])
        validate_no_duplicates(sym_uv, "symbol")
        validated_params["symbol"] = (
            [sym_uv] if isinstance(sym_uv, str) else sym_uv
        )
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]
    if broker is not None and str(broker).strip():
        payload["broker"] = str(broker).strip()

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_BROKER_VARIETY_PROFIT), payload=payload)
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_broker_grade(
        grade: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取席位评级数据

    Args:
        grade (string): 席位评级，有A,B,C,D,E共5种，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_broker_grade(
        ...     grade='A',
        ... )
    """
    validate_extra_params(kwargs)

    # 验证 grade 参数
    validated_grade = validate_broker_grade(grade, "grade")

    # 构建请求负载
    payload = {}
    if validated_grade is not None:
        payload["grade"] = validated_grade

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_BROKER_GRADE), payload=payload)

    return df


def get_broker_net_margin(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        broker: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取席位净持仓保证金数据

    Args:
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        broker (string): 席位名，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_broker_net_margin(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     broker='',
        ...     underlying_symbol='A',
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields,
        'broker': broker
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str,
        'broker': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields', 'broker']
    )

    # 验证 underlying_symbol 格式
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [symbol.upper() for symbol in validated_params['underlying_symbol']]

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    if validated_params['broker'] is not None:
        validate_no_duplicates(validated_params['broker'], 'broker')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["symbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_params['broker'] is not None:
        payload["broker"] = validated_params['broker']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_BROKER_NET_MARGIN), payload=payload)

    # 整理列顺序
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_broker_net_margin_change(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        broker: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取席位净持仓保证金变化数据

    Args:
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        broker (string): 席位名，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_broker_net_margin_change_change(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     broker='',
        ...     underlying_symbol='A',
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields,
        'broker': broker
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str,
        'broker': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields', 'broker']
    )

    # 验证 underlying_symbol 格式
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [symbol.upper() for symbol in validated_params['underlying_symbol']]

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    if validated_params['broker'] is not None:
        validate_no_duplicates(validated_params['broker'], 'broker')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["symbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_params['broker'] is not None:
        payload["broker"] = validated_params['broker']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_BROKER_NET_MARGIN_CHANGE), payload=payload)

    # 整理列顺序
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_broker_total_margin(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        broker: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取席位总持仓保证金数据

    Args:
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        broker (string): 席位名，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_broker_total_margin(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     broker='',
        ...     underlying_symbol='A',
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields,
        'broker': broker
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str,
        'broker': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields', 'broker']
    )

    # 验证 underlying_symbol 格式
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [symbol.upper() for symbol in validated_params['underlying_symbol']]

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    if validated_params['broker'] is not None:
        validate_no_duplicates(validated_params['broker'], 'broker')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["symbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    if validated_params['broker'] is not None:
        payload["broker"] = validated_params['broker']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_BROKER_TOTAL_MARGIN), payload=payload)

    # 整理列顺序
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_future_net_flow(
        start_date: str,
        end_date: str,
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        broker_name: Optional[str] = None,
        position_type: Optional[str] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    获取期货净资金流列表

    Args:
        underlying_symbol (Optional[Union[string, List[string]]]): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，必填
        end_date (string): 结束日期,eg:"20250802"，必填
        fields (Optional[Union[string, List[string]]]): 返回字段列表，非必填
        broker_name (string): 席位名称，非必填
        position_type (string): 多:"long"，空:"short"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_net_flow(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     underlying_symbol=["AG", "AU"],
        ...     broker_name="海通期货",
        ...     position_type="long",
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {
        "underlying_symbol": underlying_symbol,
        "fields": fields,
    }
    type_config = {
        "underlying_symbol": str,
        "fields": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["underlying_symbol", "fields"],
    )

    if validated_params["underlying_symbol"] is not None:
        sym_uv = validate_future_underlying_symbol_format(validated_params["underlying_symbol"])
        validate_no_duplicates(sym_uv, "underlying_symbol")
        validated_params["underlying_symbol"] = (
            [sym_uv] if isinstance(sym_uv, str) else sym_uv
        )

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    validated_position_type = None
    if position_type is not None and str(position_type).strip():
        validated_position_type = validate_position_type(
            str(position_type).strip(), "position_type"
        )

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["underlying_symbol"] is not None:
        payload["underlying_symbol"] = validated_params["underlying_symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]
    if broker_name is not None and str(broker_name).strip():
        payload["brokerName"] = str(broker_name).strip()
    if validated_position_type is not None:
        payload["positionType"] = validated_position_type

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_NET_FLOW), payload=payload)
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_basis(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货基差数据

    Args:
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_basis(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     fields=[''],
        ...     underlying_symbol='A',
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields']
    )

    # 验证 underlying_symbol 格式
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [symbol.upper() for symbol in validated_params['underlying_symbol']]

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["symbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_BASIS), payload=payload)

    # 整理列顺序
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_future_wr(
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货仓单数据

    Args:
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        fields (string): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_wr(
        ...     start_date="20250101",
        ...     end_date="20250201",
        ...     underlying_symbol='A',
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields']
    )

    # 验证 underlying_symbol 格式
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [symbol.upper() for symbol in validated_params['underlying_symbol']]

    # 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_params['underlying_symbol'] is not None:
        payload["symbol"] = validated_params['underlying_symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_WR), payload=payload)

    # 整理列顺序
    if not df.empty and {"underlying_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["underlying_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_future_ls_ratio(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货合约多空比数据

    Args:
        symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_ls_ratio(
        ...     symbol="",
        ...     start_date="20260101",
        ...     end_date="20260201",
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol
    }

    type_config = {
        'symbol': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol']
    )

    # 验证 symbol 格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_future_symbol_format(validated_params['symbol'])
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_LS_RATIO), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_future_net_cap_change(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        broker: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货合约净持仓市值变化数据

    Args:
        symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        broker (string): 席位，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_net_cap_change(
        ...     symbol="",
        ...     start_date="20260101",
        ...     end_date="20260201",
        ...     broker=[],
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'broker': broker
    }

    type_config = {
        'symbol': str,
        'broker': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'broker']
    )

    # 验证 symbol 格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_future_symbol_format(validated_params['symbol'])
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证 broker 列表中是否有重复值
    if validated_params['broker'] is not None:
        validate_no_duplicates(validated_params['broker'], 'broker')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['broker'] is not None:
        payload["broker"] = validated_params['broker']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_NET_CAP_CHANGE), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_future_contract_rank(
        symbol: Optional[Union[str, List[str]]] = None,
        underlying_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        type: Optional[str] = None,
        max_rank: Optional[int] = None,
        rank_type: str = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货合约龙虎比、牛熊线排行

    Args:
        symbol (string): 期货品种，非必填
        underlying_symbol (string): 期货品种，非必填
        start_date (string): 开始日期,eg:"20250702"，非必填
        end_date (string): 结束日期,eg:"20250802"，非必填
        type (string): 多空方向，可选long或short，为空时均返回，非必填
        max_rank (integer): 最大排名，非必填
        rank_type (string): 排名依据，仅接受ratio或line，ratio将返回龙虎比及对应排名信息，line则返回牛熊线及对应排名信息，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_contract_rank(
        ...     start_date="20260101",
        ...     end_date="20260201",
        ...     underlying_symbol="",
        ...     symbol="",
        ...     max_rank=None,
        ...     type="",
        ...     rank_type="line",
        ... )
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    validated_rank_type = validate_rank_type(rank_type, "rank_type")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'underlying_symbol': underlying_symbol
    }

    type_config = {
        'symbol': str,
        'underlying_symbol': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'underlying_symbol']
    )

    # 验证 symbol 格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_future_symbol_format(validated_params['symbol'])
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证 underlying_symbol 格式（空值会被正确处理）
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')

        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [s.upper() for s in validated_params['underlying_symbol']]

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 验证 max_rank 参数
    validated_max_rank = validate_max_rank(max_rank, "max_rank") if max_rank is not None else None

    # 验证 type 参数
    validated_type = validate_position_type(type, "type") if type is not None else None

    # 构建请求负载（驼峰风格）
    payload = {
        "rankType": validated_rank_type
    }

    if validated_params['symbol'] is not None:
        payload["symbol"] = validated_params['symbol']

    if validated_params['underlying_symbol'] is not None:
        payload["underlyingSymbol"] = validated_params['underlying_symbol']

    if validated_start_date is not None:
        payload["startDate"] = validated_start_date

    if validated_end_date is not None:
        payload["endDate"] = validated_end_date

    if validated_type is not None:
        payload["type"] = validated_type

    if validated_max_rank is not None:
        payload["maxRank"] = validated_max_rank

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_CONTRACT_RANK), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol", "date", "rank", "position_type"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date", "rank", "position_type"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_sat_profit(
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货席位盈利排行数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        fields (string): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_sat_profit_rank(
        ...     start_date='20260310',
        ...     end_date='20260320',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "date" not in fields:
            fields.append("date")
    # 验证参数类型
    params = {
        'fields': fields
    }

    type_config = {
        'fields': str
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['fields']
    )

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_SAT_PROFIT_RANKING), payload=payload)

    # 整理列顺序
    if not df.empty and {"rank", 'date'}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["rank", 'date']
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
        df = df.sort_values(by=['rank']).reset_index(drop=True)
    return df


def get_future_sat_loss(
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取期货席位亏损排行数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        fields (string): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_sat_loss(
        ...     start_date='20260310',
        ...     end_date='20260320',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "date" not in fields:
            fields.append("date")
    # 验证参数类型
    params = {
        'fields': fields
    }

    type_config = {
        'fields': str
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['fields']
    )
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_SAT_LOSS_RANKING), payload=payload)

    # 整理列顺序
    if not df.empty and {"rank", 'date'}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["rank", 'date']
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
        df = df.sort_values(by=['rank']).reset_index(drop=True)
    return df


def get_future_building_process(
        start_date: str,
        end_date: str,
        broker: str,
        symbol: Optional[list[str]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs) -> pd.DataFrame:
    """
    获取期货席位建仓过程数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        broker (string): 券商名称，必填
        symbol (string): 期货名称，非必填
        fields (string): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_building_process(
        ...     start_date='20260310',
        ...     end_date='20260320',
        ...     broker="浙商期货",
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "date" not in fields:
            fields.append("date")
        if "broker" not in fields:
            fields.append("broker")
        if "symbol" not in fields:
            fields.append("symbol")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    validate_not_empty(end_date, "broker")
    # 验证参数类型
    params = {
        'symbol': symbol,
        'broker': broker,
        'fields': fields,
    }

    type_config = {
        'symbol': str,
        'broker': str,
        'fields': str,
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'fields']
    )

    # 验证 symbol 格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_future_symbol_format(validated_params['symbol'])
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证 broker 格式（空值会被正确处理）
    if validated_params['broker'] is not None:
        # 将 broker 的每一项去处空格
        validated_params['broker'] = validated_params['broker'].strip()
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
    if validated_params['broker'] is not None:
        payload["broker"] = validated_params['broker']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_POSITION_BUILDING_PROCESS), payload=payload)

    # 整理列顺序
    if not df.empty and {"broker", 'date', 'symbol'}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", 'broker', 'symbol']
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
        df = df.sort_values(by=['date', 'broker', 'symbol'])
        df = df.reset_index(drop=True)
    return df


def get_future_cap_value(
        start_date: str = None,
        end_date: str = None,
        underlying_symbol: Optional[Union[None, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs) -> pd.DataFrame:
    """
    获取期货品种持仓市值数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        underlying_symbol (string): 期货品种名称，非必填
        fields (string): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_cap_value(
        ...     start_date='20240810',
        ...     end_date='20240920',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "date" not in fields:
            fields.append("date")
        if "underlying_symbol" not in fields:
            fields.append("underlying_symbol")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields,
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str,
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields']
    )

    # 验证 underlying_symbol 格式（空值会被正确处理）
    if validated_params['underlying_symbol'] is not None:
        # 验证 underlying_symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')
        # 将 underlying_symbol 的每一项变为全大写
        validated_params['underlying_symbol'] = [s.strip().upper() for s in validated_params['underlying_symbol']]

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['underlying_symbol'] is not None:
        payload["underlyingSymbol"] = validated_params['underlying_symbol']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_CAP_VALUE), payload=payload)

    # 整理列顺序
    if not df.empty and {"broker", 'date', 'underlying_symbol'}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", 'underlying_symbol']
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
        df = df.sort_values(by=['date', 'underlying_symbol']).reset_index(drop=True)
    return df


def get_future_ratio_virtual_real(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[None, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs) -> pd.DataFrame:
    """
    获取期货虚实盘比数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        symbol (string): 期货合约名称，非必填
        fields (string): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_ratio_virtual_real(
        ...     start_date='20240810',
        ...     end_date='20240920',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "date" not in fields:
            fields.append("date")
        if "symbol" not in fields:
            fields.append("symbol")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
    params = {
        'symbol': symbol,
        'fields': fields,
    }

    type_config = {
        'symbol': str,
        'fields': str,
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'fields']
    )

    # 验证 symbol 格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_future_symbol_format(validated_params['symbol'])
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

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
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_RATIO_OF_VIRTUAL_TO_REAL_POSITIONS),
                         payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
        df = df.sort_values(by=['date', 'symbol']).reset_index(drop=True)
    return df


def get_future_spot_profit(
        start_date: str = None,
        end_date: str = None,
        underlying_symbol: Optional[Union[None, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs) -> pd.DataFrame:
    """
    获取期货利润数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        underlying_symbol (string): 期货品种名称，非必填
        fields (string): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_spot_profit(
        ...     start_date='20240810',
        ...     end_date='20240920',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "date" not in fields:
            fields.append("date")
        if "underlying_symbol" not in fields:
            fields.append("underlying_symbol")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields,
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str,
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields']
    )

    # 验证 underlying_symbol 格式（空值会被正确处理）
    if validated_params['underlying_symbol'] is not None:
        # 验证 underlying_symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')
        validated_params['underlying_symbol'] = [item.strip().upper() for item in validated_params['underlying_symbol']]
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['underlying_symbol'] is not None:
        payload["underlyingSymbol"] = validated_params['underlying_symbol']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_SPOT_PROFIT),
                         payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "underlying_symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "underlying_symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
        df = df.sort_values(by=["date", "underlying_symbol"]).reset_index(drop=True)
    return df


def get_future_trader_quotation(
        start_date: str = None,
        end_date: str = None,
        underlying_symbol: Optional[Union[None, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs) -> pd.DataFrame:
    """
    获取期货现货贸易商报价数据

    Args:
        start_date (string): 开始日期，格式 YYYYMMDD，必填
        end_date (string): 结束日期，格式 YYYYMMDD，必填
        underlying_symbol (string): 期货品种名称，非必填
        fields (string): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_future_trader_quotation(
        ...     start_date='20240810',
        ...     end_date='20240920',
        ... )
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "date" not in fields:
            fields.append("date")
        if "underlying_symbol" not in fields:
            fields.append("underlying_symbol")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
    params = {
        'underlying_symbol': underlying_symbol,
        'fields': fields,
    }

    type_config = {
        'underlying_symbol': str,
        'fields': str,
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['underlying_symbol', 'fields']
    )

    # 验证 underlying_symbol 格式（空值会被正确处理）
    if validated_params['underlying_symbol'] is not None:
        # 验证 symbol 列表中是否有重复值
        validate_no_duplicates(validated_params['underlying_symbol'], 'underlying_symbol')
        validated_params['underlying_symbol'] = [item.strip().upper() for item in validated_params['underlying_symbol']]
    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')
    # 构建请求负载
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['underlying_symbol'] is not None:
        payload["underlyingSymbol"] = validated_params['underlying_symbol']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_SPOT_TRADER_QUOTATION),
                         payload=payload)

    # 整理列顺序
    if not df.empty and {'date', "underlying_symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["date", "underlying_symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
        df = df.sort_values(by=['date', 'underlying_symbol']).reset_index(drop=True)
    return df


def get_future_broker_position(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        broker: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取期货席位持仓数据（future_broker_position，Parquet 数据源）。
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
        validate_future_symbol_format(validated_params["symbol"])
        validate_no_duplicates(validated_params["symbol"], "symbol")
        validated_params["symbol"] = [s.upper() for s in validated_params["symbol"]]
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if broker is not None and str(broker).strip():
        payload["broker"] = str(broker).strip()
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_BROKER_POSITION), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_future_variety_broker_profit(
        start_date: str,
        end_date: str,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        broker: Optional[str] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取期货品种席位盈亏数据（future_variety_broker_profit）。
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
        sym_uv = validate_future_underlying_symbol_format(validated_params["symbol"])
        validate_no_duplicates(sym_uv, "symbol")
        validated_params["symbol"] = [sym_uv] if isinstance(sym_uv, str) else sym_uv
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)
    validate_date_interval(validated_start_date, validated_end_date, max_years=5)

    payload = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]
    if broker is not None and str(broker).strip():
        payload["broker"] = str(broker).strip()

    df = fetch_dataframe(
        build_endpoint(BASE_ENDPOINT, PATH_GET_FUTURE_VARIETY_BROKER_PROFIT),
        payload=payload,
    )
    if not df.empty and {"broker", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["broker", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df