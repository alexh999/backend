from __future__ import annotations

from typing import List, Optional, Tuple, Union, Dict, Any

import pandas as pd

from panda_data.core.service import fetch_dataframe
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_param_types,
    validate_symbol_format,
    validate_no_duplicates,
    validate_date_format,
    validate_stock_status,
    validate_date_range, validate_not_empty, validate_extra_params,
    validate_index_symbol_format, validate_index_status, validate_industry_code_format,
    validate_industry_level, validate_side_value, validate_margin_type_value, validate_rank_pair, validate_stock_type,
    validate_stock_info_market,
    validate_company_investor_max_rank, validate_year_format, validate_year_range
)

MULTI_ENDPOINT = "/multi"
PATH_GET_STOCK_DETAIL = "/getStockDetail"

INDEX_ENDPOINT = "/index"
PATH_GET_INDEX_SYMBOL = "/getIndexSymbolData"
PATH_GET_INDEX_INDICATOR = "/getIndexIndicatorData"
PATH_GET_INDEX_WEIGHTS = "/getIndexWeightsData"
PATH_GET_INDEX_DETAIL_QH = "/getIndexDetailQH"
PATH_GET_INDEX_LEADING_QH = "/getIndexLeadingQH"

CONCEPT_ENDPOINT = "/concept"
PATH_GET_CONCEPT_LIST = "/getConceptData"
PATH_GET_CONCEPT_STOCK = "/getConceptStockData"

INDUSTRY_ENDPOINT = "/industry"
PATH_GET_INDUSTRY_STOCK = "/getIndustryStockData"
PATH_GET_INDUSTRY_LIST = "/getIndustryList"
PATH_GET_STOCK_INDUSTRY = "/getStockIndustry"

ABNORMAL_ENDPOINT = "/abnormal"
PATH_GET_ABNORMAL = "/getAbnormalData"
PATH_GET_ABNORMAL_DETAIL = "/getAbnormalDetailData"

BUYBACK_ENDPOINT = "/buyback"
PATH_GET_BUY_BACK_DATA = "/getBuyBackData"

STOCK_ENDPOINT = "/stock"
PATH_GET_SECURITIES_MARGIN = "/getSecuritiesMarginData"
PATH_GET_STOCK_CONNECT_DATA = "/getStockConnectData"
PATH_GET_INVESTOR_ACTIVITIES = "/getStockInvestorData"
PATH_GET_RESTRICTED_DETAILS = "/getStockRestrictedData"
PATH_GET_STOCK_CASH_DIVIDEND = "/getStockCashDividendData"
PATH_GET_STOCK_DIVIDEND_INFO = "/getStockDividendInfoData"
PATH_GET_STOCK_SPLIT_INFO = "/getStockSplitInfoData"
PATH_GET_STOCK_DIVIDEND_AMOUNT = "/getStockDividendAmountData"
PATH_GET_STOCK_PRIVATE_PLACEMENT = "/getStockPrivatePlacementData"
PATH_GET_STOCK_ALLOTMENT = "/getStockAllotmentData"
PATH_GET_HOLDER_NUMBER = "/getStockHolderNumberData"
PATH_GET_MAIN_SHAREHOLDER = "/getStockMainHolderData"
PATH_GET_BLOCK_TRADE = "/getStockBlockTradeData"
PATH_GET_STOCK_SHARES = "/getStockShareData"
PATH_GET_STOCK_CUMU_GUARANTEE = "/getStockCumuGuaranteeData"
PATH_GET_STOCK_EQUITY_PLEDGE = "/getStockEquityPledgeData"
PATH_GET_STOCK_EQUITY_PLEDGE_STAT = "/getStockEquityPledgeStatData"
PATH_GET_STOCK_RELA_PARTY_TRANS = "/getStockRelaPartyTransData"
PATH_GET_STOCK_SHAREHOLDER_TRADING_PLAN = "/getStockShareholderTradingPlanData"
PATH_GET_STOCK_EQUITY_ILLEGAL = "/getStockEquityIllegalData"
PATH_GET_STOCK_EQUITY_NATURE = "/getStockEquityNatureData"
PATH_GET_STOCK_EQUITY_PLACARD = "/getStockEquityPlacardData"

PATH_GET_INV_BRIEF_QA = "/getInvBriefQAData"
PATH_GET_INV_BRIEF_DETAIL = "/getInvBriefDetailData"
PATH_GET_STOCK_DISCLOSURE_DATE = "/getStockDisclosureDateData"
PATH_GET_STOCK_STATUS_OVER_ALLOTMENT = "/getStockStatusOverAllotmentData"
PATH_GET_STOCK_LITIGATION_ARBITRATION = "/getStockLitigationArbitrationData"
PATH_GET_STOCK_CSRC_APPROVAL = "/getStockCsrcApprovalData"
PATH_GET_STOCK_COMPETITOR_INFORMATION = "/getStockCompetitorInformationData"
PATH_GET_STOCK_INTERMEDIARY_INFORMATION = "/getStockIntermediaryInformationData"
PATH_GET_MATERIAL_CONTRACT = "/getStockMaterialContractData"
PATH_GET_STOCK_PREFERRED_DETAIL = "/getStockPreferredDetailData"
PATH_GET_STOCK_PREFERRED_PLACEMENT = "/getStockPreferredPlacementData"
PATH_GET_STOCK_PREFERRED_RATING = "/getStockPreferredRatingData"
PATH_GET_STOCK_PREFERRED_SHARES = "/getStockPreferredSharesData"
PATH_GET_STOCK_ISSUER_CREDIT_RATING = "/getStockIssuerCreditRatingData"
PATH_GET_STOCK_PREFERRED_TRADING = "/getStockPreferredTradingData"
PATH_GET_STOCK_PREFERRED_DIVIDEND = "/getStockPreferredDividendData"
PATH_GET_STOCK_SYMBOL_HISTORY = "/getStockSymbolHistoryData"


def _normalise_symbols(symbol: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if symbol is None or symbol == "":
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


def _normalize_to_list(value: Union[str, List[str]]) -> List[str]:
    return value if isinstance(value, list) else [value]


def _build_payload_lhb(
        *,
        symbol: Optional[Union[str, List[str]]] = None,
        type: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if symbol is not None:
        payload["symbol"] = _normalize_to_list(symbol)
    if type is not None:
        payload["type"] = _normalize_to_list(type)
    if start_date is not None:
        payload["startDate"] = start_date
    if end_date is not None:
        payload["endDate"] = end_date
    if fields:
        payload["fields"] = fields
    return payload


def get_stock_detail(
        symbol: Optional[Union[str, List[str]]] = "",
        fields: Optional[Union[str, List[str]]] = None,
        status: Optional[int] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票基本信息

    Args:
        symbol (str or list of str, optional): 股票代码，非必填
        fields (str or list of str, optional): 返回字段，非必填
        status (int, optional): 是否在市，1 -在市，0 -退市，-1 -未知，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_detail(
        ... symbol=["000001.SZ","000002.SZ","000003.SZ"],
        ... fields=[""],
        ... status=None
        ... )
        ... print(result)
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
    if validated_params['symbol'] is not None and validated_params['symbol'] != [""] and validated_params[
        'symbol'] != []:
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')
        validate_symbol_format(validated_params['symbol'])

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

    df = fetch_dataframe(build_endpoint(MULTI_ENDPOINT, PATH_GET_STOCK_DETAIL), payload=payload)
    if not df.empty and "symbol" in df.columns:
        df = df[df["symbol"].str.upper() != "UNKNOWN"]
    return df


def get_index_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        status: Optional[int] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取指数基本信息

    Args:
        symbol (str): 指数代码，非必填
        fields (str): 返回字段列表，非必填
        status (str): 指数状态(1：正常交易，0：已退市，-1：暂无信息)，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_index_detail(
        ... symbol="",
        ... status=None,
        ... fields=[]
        ... )
        ... print(result)
    """
    payload = {}

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

    # 验证symbol格式（指数格式）
    if validated_params['symbol'] is not None:
        validate_index_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证status参数
    if status is not None:
        validated_status = validate_index_status(status, "status")
    else:
        validated_status = status

    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_status is not None:
        payload["status"] = validated_status
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(INDEX_ENDPOINT, PATH_GET_INDEX_SYMBOL), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_index_detail_qh(
        index_name: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]
    """
    payload: Dict[str, Any] = {}

    validate_extra_params(kwargs)
    params = {
        "index_name": index_name,
        "fields": fields,
    }
    type_config = {
        "index_name": str,
        "fields": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["index_name", "fields"],
    )

    if validated_params["index_name"] is not None:
        validate_no_duplicates(validated_params["index_name"], "index_name")
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    index_names = _normalise_list(validated_params["index_name"])
    if index_names is not None:
        payload["indexName"] = index_names
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(INDEX_ENDPOINT, PATH_GET_INDEX_DETAIL_QH), payload=payload)
    if not df.empty:
        priority_cols = [c for c in ["index_name", "created_at"] if c in df.columns]
        other_cols = [col for col in df.columns if col not in priority_cols]
        if priority_cols:
            df = df[priority_cols + other_cols]
    return df


def get_index_ls_leading_qh(
        index_name: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """[WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]
    奇货 DeepView 多空领先指标（index_ls_leading_qh，Parquet / Java）。"""
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    params = {
        "index_name": index_name,
        "fields": fields,
    }
    type_config = {
        "index_name": str,
        "fields": str,
    }
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["index_name", "fields"],
    )

    if validated_params["index_name"] is not None:
        validate_no_duplicates(validated_params["index_name"], "index_name")
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload: Dict[str, Any] = {
        "startDate": validated_start_date,
        "endDate": validated_end_date,
    }
    index_names = _normalise_list(validated_params["index_name"])
    if index_names is not None:
        payload["indexName"] = index_names
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(
        build_endpoint(INDEX_ENDPOINT, PATH_GET_INDEX_LEADING_QH),
        payload=payload,
    )
    if not df.empty and {"index_name", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["index_name", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def _build_payload(
        *,
        concept: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        date: Optional[str] = None
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    concept_list = _normalise_list(concept)
    if concept_list is not None:
        payload["concept"] = concept_list
    if start_date is not None:
        payload["startDate"] = start_date
    if end_date is not None:
        payload["endDate"] = end_date
    if fields:
        payload["fields"] = fields
    if date:
        payload["date"] = date
    return payload


def get_concept_list(
        concept: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取概念列表

    Args:
        concept (str): 概念名称，非必填
        start_date (str): 开始时间，非必填
        end_date (str): 结束时间，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_concept_list(
        ... start_date="20250101",
        ... end_date="20250131",
        ... concept="英伟达概念"
        ... )
        ... print(result)
    """
    validate_extra_params(kwargs)
    # 验证参数类型
    params = {
        'concept': concept
    }

    type_config = {
        'concept': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['concept']
    )

    # 验证concept列表中是否有重复值（空值会被正确处理）
    if validated_params['concept'] is not None:
        validate_no_duplicates(validated_params['concept'], 'concept')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = _build_payload(
        concept=validated_params['concept'],
        start_date=validated_start_date,
        end_date=validated_end_date
    )

    df = fetch_dataframe(build_endpoint(CONCEPT_ENDPOINT, PATH_GET_CONCEPT_LIST), payload=payload)
    if not df.empty and {"name", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["name", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_concept_constituents(
        concept: Optional[Union[str, List[str]]] = None,
        concept_stock: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        date: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取概念成分股

    Args:
        concept (str): 概念名称，非必填
        concept_stock (str): 股票代码，非必填
        date (str): 日期，返回该日期前被纳入对应概念的股票，非必填
        fields (str): 返回字段，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_concept_constituents(
        ... date="20250131",
        ... concept="英伟达概念",
        ... concept_stock="",
        ... fields=["concept", "concept_stock", "date"]
        ... )
        ... print(result)
    """
    validate_extra_params(kwargs)
    # 验证参数类型
    params = {
        'concept': concept,
        'concept_stock': concept_stock,
        'fields': fields
    }

    type_config = {
        'concept': str,
        'concept_stock': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['concept', 'fields', 'concept_stock']
    )

    # 验证concept_stock格式（空值会被正确处理）
    if validated_params['concept_stock'] is not None and validated_params['concept_stock'] != "":
        # concept_stock 类似 symbol 格式验证
        temp_result = [validated_params['concept_stock']] if isinstance(validated_params['concept_stock'], str) else \
            validated_params['concept_stock']
        validate_symbol_format(temp_result)
        # 验证concept_stock是否有重复值
        validate_no_duplicates(temp_result, 'concept_stock')

    # 验证concept列表中是否有重复值（空值会被正确处理）
    if validated_params['concept'] is not None:
        validate_no_duplicates(validated_params['concept'], 'concept')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validated_date = validate_date_format(date, "date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = _build_payload(
        concept=validated_params['concept'],
        start_date=validated_start_date,
        end_date=validated_end_date,
        fields=validated_params['fields'],
        date=validated_date
    )

    if validated_params['concept_stock'] is not None:
        payload["conceptStock"] = validated_params['concept_stock']

    df = fetch_dataframe(build_endpoint(CONCEPT_ENDPOINT, PATH_GET_CONCEPT_STOCK), payload=payload)
    if not df.empty and {"concept_stock", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["concept_stock", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_industry_constituents(
        industry_code: Optional[Union[str, List[str]]] = None,
        stock_symbol: Optional[Union[str, List[str]]] = None,
        level: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None
) -> pd.DataFrame:
    """
    获取行业成分股数据

    Args:
        industry_code (str): 行业代码，如"801010"，非必填
        stock_symbol (str): 股票代码，如"000001.SZ"，非必填
        level (str): 行业级别，可选值："L1"(一级)、"L2"(二级)、"L3"(三级)，非必填
        fields (str): 返回字段列表，非必填

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_industry_constituents(
        ... industry_code="801780",
        ... stock_symbol="000001.SZ",
        ... level="L1",
        ... fields=[]
        ... )
        ... print(result)
    """
    payload = {}

    # 验证参数类型
    params = {
        'industry_code': industry_code,
        'stock_symbol': stock_symbol,
        'level': level,
        'fields': fields
    }

    type_config = {
        'industry_code': str,
        'stock_symbol': str,
        'level': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['industry_code', 'stock_symbol', 'fields']  # industry_code 和 stock_symbol 允许是列表
    )

    # 验证industry_code格式（6位数字格式）
    if validated_params['industry_code'] is not None:
        validate_industry_code_format(validated_params['industry_code'])
        # 验证industry_code列表中是否有重复值
        validate_no_duplicates(validated_params['industry_code'], 'industry_code')

    # 验证stock_symbol格式（6位数字格式）
    if validated_params['stock_symbol'] is not None:
        validate_symbol_format(validated_params['stock_symbol'])
        # 验证stock_symbol列表中是否有重复值
        validate_no_duplicates(validated_params['stock_symbol'], 'stock_symbol')

    # 验证level格式
    if validated_params['level'] is not None and validated_params['level'] != "":
        # 验证level格式
        temp_result = [validated_params['level']] if isinstance(validated_params['level'], str) else validated_params[
            'level']
        validate_industry_level(temp_result, 'level')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    if validated_params['industry_code'] is not None:
        payload["industryCode"] = validated_params['industry_code']
    if validated_params['stock_symbol'] is not None:
        payload["stockSymbol"] = validated_params['stock_symbol']
    if validated_params['level'] is not None:
        payload["level"] = validated_params['level']
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(INDUSTRY_ENDPOINT, PATH_GET_INDUSTRY_STOCK), payload=payload)
    if not df.empty and {"stock_symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["stock_symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_industry_detail(
        level: Optional[str] = "L1",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取行业基本信息数据

    Args:
        fields (str or list of str, optional): 返回字段列表，非必填
        level (str or list of str, optional): 行业级别，可选值："L1"(一级)、"L2"(二级)、"L3"(三级)，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_industry_detail(
        ... level="L1",
        ... fields=[]
        ... )
        ... print(result)
    """
    payload = {}

    validate_extra_params(kwargs)

    # 验证参数类型
    params = {
        'level': level,
        'fields': fields
    }

    type_config = {
        'level': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['fields']  # 只有fields允许是列表，level只能是字符串
    )

    # 验证level格式（只支持字符串）
    if validated_params['level'] is not None:
        validate_industry_level(validated_params['level'], 'level')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    if validated_params['level'] is not None:
        payload["level"] = validated_params['level']
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(INDUSTRY_ENDPOINT, PATH_GET_INDUSTRY_LIST), payload=payload)
    if not df.empty and {"industry_code"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["industry_code"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_industry(
        stock_symbol: str,
        level: Optional[str] = "L1",
) -> pd.DataFrame:
    """
    获取指定股票所属的行业信息

    Args:
        stock_symbol (str): 股票代码，如"000001.SZ"，非必填
        level (str): 行业级别，可选值："L1"(一级)、"L2"(二级)、"L3"(三级)，非必填

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_industry(
        ... stock_symbol="000001.SZ",
        ... level="L1"
        ... )
        ... print(result)
    """
    validate_not_empty(stock_symbol, 'stock_symbol')
    # 验证参数类型
    params = {
        'stock_symbol': stock_symbol,
        'level': level
    }

    type_config = {
        'stock_symbol': str,
        'level': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=[]  # 都不允许是列表
    )

    # 验证stock_symbol格式（标准股票格式）和非空
    if validated_params['stock_symbol'] is not None:
        # 验证股票symbol格式
        temp_result = [validated_params['stock_symbol']] if isinstance(validated_params['stock_symbol'], str) else \
        validated_params['stock_symbol']
        validate_symbol_format(temp_result)

    # 验证level格式
    if validated_params['level'] is not None and validated_params['level'] != "":
        # 验证level格式
        temp_result = [validated_params['level']] if isinstance(validated_params['level'], str) else validated_params[
            'level']
        validate_industry_level(temp_result, 'level')

    payload = {"stockSymbol": validated_params['stock_symbol']}
    if validated_params['level'] is not None:
        payload["level"] = validated_params['level']
    df = fetch_dataframe(build_endpoint(INDUSTRY_ENDPOINT, PATH_GET_STOCK_INDUSTRY), payload=payload)
    if not df.empty and {"stock_symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["stock_symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_index_indicator(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取指数估值指标数据

    Args:
        symbol (str): 指数代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_index_indicator(
        ... symbol="",
        ... start_date="20250101",
        ... end_date="20250131",
        ... fields=[]
        ... )
        ... print(result)
    """
    payload = {}

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

    # 验证symbol格式（指数格式）
    if validated_params['symbol'] is not None:
        validate_index_symbol_format(validated_params['symbol'])
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

    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(INDEX_ENDPOINT, PATH_GET_INDEX_INDICATOR), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_index_weights(
        index_symbol: Optional[Union[str, List[str]]] = None,
        stock_symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取指数权重信息数据

    Args:
        index_symbol (str): 指数代码，非必填
        stock_symbol (str): 成分股代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_index_weights(
        ... index_symbol="000006.SH",
        ... stock_symbol="",
        ... start_date="20250101",
        ... end_date="20250131",
        ... fields=["index_symbol", "stock_symbol", "date"]
        ... )
        ... print(result)
    """
    payload = {}

    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 验证参数类型
    params = {
        'index_symbol': index_symbol,
        'stock_symbol': stock_symbol,
        'fields': fields
    }

    type_config = {
        'index_symbol': str,
        'stock_symbol': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['index_symbol', 'stock_symbol', 'fields']
    )

    # 验证index_symbol格式（指数格式）
    if validated_params['index_symbol'] is not None:
        validate_index_symbol_format(validated_params['index_symbol'])
        # 验证index_symbol列表中是否有重复值
        validate_no_duplicates(validated_params['index_symbol'], 'index_symbol')

    # 验证stock_symbol格式（股票格式）
    if validated_params['stock_symbol'] is not None:
        validate_symbol_format(validated_params['stock_symbol'])
        # 验证stock_symbol列表中是否有重复值
        validate_no_duplicates(validated_params['stock_symbol'], 'stock_symbol')

    # 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    index_symbols = _normalise_list(validated_params['index_symbol'])
    if index_symbols is not None:
        payload["indexSymbol"] = index_symbols
    stock_symbols = _normalise_list(validated_params['stock_symbol'])
    if stock_symbols is not None:
        payload["stockSymbol"] = stock_symbols
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(INDEX_ENDPOINT, PATH_GET_INDEX_WEIGHTS), payload=payload)
    if not df.empty and {"index_symbol", "stock_symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["index_symbol", "stock_symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_lhb_list(
        symbol: Optional[Union[str, List[str]]] = None,
        type: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票龙虎榜数据

    Args:
        symbol (str): 股票代码，如 "000001.SZ"，非必填
        type (str): 龙虎榜类型，非必填
        start_date (str): 开始日期，格式 "YYYYMMDD"，非必填
        end_date (str): 结束日期，格式 "YYYYMMDD"，非必填
        fields (str): 需要返回的字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_lhb_list(
        ... start_date="20250101",
        ... end_date="20250131",
        ... type="G0007",
        ... symbol="",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    # 2. 验证参数类型
    params = {
        'symbol': symbol,
        'type': type,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'type': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'type', 'fields']
    )

    # 3. 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证type列表中是否有重复值（空值会被正确处理）
    if validated_params['type'] is not None:
        validate_no_duplicates(validated_params['type'], 'type')

    # 5. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = _build_payload_lhb(
        symbol=validated_params['symbol'],
        type=validated_params['type'],
        start_date=validated_start_date,
        end_date=validated_end_date,
        fields=validated_params['fields']
    )

    df = fetch_dataframe(build_endpoint(ABNORMAL_ENDPOINT, PATH_GET_ABNORMAL), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_lhb_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        type: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        side: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票龙虎榜明细数据

    Args:
        symbol (str): 股票代码，如 "000001.SZ"，非必填
        type (str): 龙虎榜类型，非必填
        start_date (str): 开始日期，格式 "YYYYMMDD"，非必填
        end_date (str): 结束日期，格式 "YYYYMMDD"，非必填
        side (str): 买卖方向，可选值为 "buy" 或 "sell" 或 "cum"，其中"cum"类型记录发生严重异常时的累计数据，与具体买卖方向无关，非必填
        fields (str): 需要返回的字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_lhb_detail(
        ... symbol="001314.SZ",
        ... start_date="20250101",
        ... end_date="20250131",
        ... type="T0020",
        ... side="sell",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数和非空
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 2. 验证参数类型
    params = {
        'symbol': symbol,
        'type': type,
        'side': side,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'type': str,
        'side': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'type', 'fields']
    )

    # 3. 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证type列表中是否有重复值（空值会被正确处理）
    if validated_params['type'] is not None:
        validate_no_duplicates(validated_params['type'], 'type')

    # 5. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 6. 验证side参数值
    if validated_params['side'] is not None:
        validated_params['side'] = validate_side_value(validated_params['side'])

    # 7. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 8. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = _build_payload_lhb(
        symbol=validated_params['symbol'],
        type=validated_params['type'],
        start_date=validated_start_date,
        end_date=validated_end_date,
        fields=validated_params['fields']
    )

    if validated_params['side'] is not None:
        payload["side"] = validated_params['side']

    df = fetch_dataframe(build_endpoint(ABNORMAL_ENDPOINT, PATH_GET_ABNORMAL_DETAIL), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_repurchase(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取回购数据

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 日期，格式 "YYYYMMDD"，非必填
        end_date (str): 日期，格式 "YYYYMMDD"，非必填
        fields (str): 需要返回的字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_repurchase(
        ... symbol="002011.SZ",
        ... start_date="20250101",
        ... end_date="20251231",
        ... fields=[]
        ... )
        ... print(result)
    """
    validate_extra_params(kwargs)
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

    # 2. 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 3. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 4. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 5. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

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

    df = fetch_dataframe(build_endpoint(BUYBACK_ENDPOINT, PATH_GET_BUY_BACK_DATA), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        # 将 symbol 和 date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_margin(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        margin_type: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取融资融券信息

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        margin_type (str): 买卖方向，'stock' 代表融券卖出，'cash' 代表融资买入，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_margin(
        ... symbol="000001.SZ",
        ... start_date="20250101",
        ... end_date="20250131",
        ... margin_type="stock",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数和必填
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    # 2. 验证参数类型
    params = {
        'symbol': symbol,
        'margin_type': margin_type,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'margin_type': str,
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

    # 5. 验证margin_type参数值
    if validated_params['margin_type'] is not None:
        validated_params['margin_type'] = validate_margin_type_value(validated_params['margin_type'])

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['margin_type'] is not None:
        payload["marginType"] = validated_params['margin_type']
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_SECURITIES_MARGIN), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_hsgt_hold(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取沪深股通持股信息

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_hsgt_hold(
        ... symbol="000001.SZ",
        ... start_date="20250601",
        ... end_date="20250630",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_CONNECT_DATA), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_investor_activity(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股合约投资者关系活动

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_investor_activity(
        ... symbol="000001.SZ",
        ... start_date="20250101",
        ... end_date="20250131",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_INVESTOR_ACTIVITIES), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_restricted_list(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票限售解禁明细数据

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        market (str): 市场,默认'cn'为中国内地市场，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_restricted_list(
        ... symbol="001256.SZ",
        ... start_date="20251201",
        ... end_date="20251231",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_RESTRICTED_DETAILS), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_cash_dividend(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票现金分红数据

    Args:
        symbol (str): 股票代码，可以是单个字符串或字符串列表，非必填
        fields (str): 需要返回的字段列表，非必填
        start_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_cash_dividend(
        ... symbol="688819.SH",
        ... start_date="20140613",
        ... end_date="20240613",
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 3. 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证市场参数
    if validated_params['market'] is not None:
        validated_params['market'] = validate_stock_info_market(validated_params['market'])

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_CASH_DIVIDEND), payload=payload)
    if not df.empty and {"symbol", "announcement_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "announcement_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_dividend_info(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票分红信息

    Args:
        symbol (str): 股票代码，可以是单个字符串或字符串列表，非必填
        fields (str): 需要返回的字段列表，非必填
        start_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_dividend(
        ... symbol="688799.SH",
        ... start_date="20150529",
        ... end_date="20250529",
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 3. 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证市场参数
    if validated_params['market'] is not None:
        validated_params['market'] = validate_stock_info_market(validated_params['market'])

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_DIVIDEND_INFO), payload=payload)
    if not df.empty and {"symbol", "announcement_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "announcement_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_split_info(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票拆分数据

    Args:
        symbol (str): 股票代码，可以是单个字符串或字符串列表，非必填
        fields (str): 需要返回的字段列表，非必填
        start_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_split(
        ... symbol="688798.SH",
        ... start_date="20050419",
        ... end_date="20250419",
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 3. 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证市场参数
    if validated_params['market'] is not None:
        validated_params['market'] = validate_stock_info_market(validated_params['market'])

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_SPLIT_INFO), payload=payload)
    if not df.empty and {"symbol", "ex_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "ex_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_dividend_amount(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票分红总额数据

    Args:
        symbol (str): 股票代码，可以是单个字符串或字符串列表，非必填
        fields (str): 需要返回的字段列表，非必填
        start_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_dividend_amount(
        ... symbol="000001.SZ",
        ... start_date="19910626",
        ... end_date="20260326",
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 3. 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证市场参数
    if validated_params['market'] is not None:
        validated_params['market'] = validate_stock_info_market(validated_params['market'])

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_DIVIDEND_AMOUNT), payload=payload)
    if not df.empty and {"symbol", "announcement_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "announcement_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_private_placement(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票定向增发数据

    Args:
        symbol (str): 股票代码，可以是单个字符串或字符串列表，非必填
        fields (str): 需要返回的字段列表，非必填
        start_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_private_placement(
        ... symbol="000001.SZ",
        ... start_date="19910626",
        ... end_date="20260326",
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 3. 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证市场参数
    if validated_params['market'] is not None:
        validated_params['market'] = validate_stock_info_market(validated_params['market'])

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PRIVATE_PLACEMENT), payload=payload)
    if not df.empty and {"symbol", "announcement_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "announcement_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_allotment(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票配股信息

    Args:
        symbol (str): 股票代码，可以是单个字符串或字符串列表，非必填
        fields (str): 需要返回的字段列表，非必填
        start_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        end_date (str): 信息发布日期，格式为 "YYYYMMDD"，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_allotment(
        ... symbol="000001.SZ",
        ... start_date="19910626",
        ... end_date="20260326",
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 3. 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证市场参数
    if validated_params['market'] is not None:
        validated_params['market'] = validate_stock_info_market(validated_params['market'])

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_ALLOTMENT), payload=payload)
    if not df.empty and {"symbol", "announcement_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "announcement_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_holder_count(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股东数量

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_holder_count(
        ... symbol="000001.SZ",
        ... start_date="20250101",
        ... end_date="20250531",
        ... fields=[]
        ... )
        ... print(result)
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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_HOLDER_NUMBER), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_top_holders(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        start_rank: Optional[int] = None,
        end_rank: Optional[int] = None,
        stock_type: Optional[str] = None,
        market: Optional[str] = "cn",
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股股东信息

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        market (str): 市场,默认'cn'为中国内地市场，非必填
        start_rank (int): 排名开始值，非必填
        end_rank (int): 排名结束值，非必填
        stock_type (str): 股票种类, flow基于持有A股流通股;total基于所有发行出的A股，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_top_holders(
        ... symbol="000001.SZ",
        ... start_date="20250101",
        ... end_date="20250531",
        ... start_rank=1,
        ... end_rank=5,
        ... stock_type="flow",
        ... market="cn",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 2. 验证参数类型
    params = {
        'symbol': symbol,
        'start_rank': start_rank,
        'end_rank': end_rank,
        'stock_type': stock_type,
        'market': market,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'start_rank': int,
        'end_rank': int,
        'stock_type': str,
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

    # 6. 验证股票类型参数
    if validated_params['stock_type'] is not None:
        validated_params['stock_type'] = validate_stock_type(validated_params['stock_type'])

    # 7. 验证排名参数对
    validate_rank_pair(validated_params['start_rank'], validated_params['end_rank'])

    # 8. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 9. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {"market": validated_params['market']}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['start_rank'] is not None:
        payload["startRank"] = validated_params['start_rank']
    if validated_params['end_rank'] is not None:
        payload["endRank"] = validated_params['end_rank']
    if validated_params['stock_type'] is not None:
        payload["stockType"] = validated_params['stock_type']
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_MAIN_SHAREHOLDER), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_block_trade(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股大宗交易信息

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_block_trade(
        ... symbol="000001.SZ",
        ... start_date="20250101",
        ... end_date="20250831",
        ... fields=[]
        ... )
        ... print(result)
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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_BLOCK_TRADE), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_share_float(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票股本数据

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_share_float(
        ... symbol="000001.SZ",
        ... start_date="20250101",
        ... end_date="20250831",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_SHARES), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_cumu_guarantee(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_CUMU_GUARANTEE), payload=payload)
    if not df.empty and {"symbol", "info_date", "end_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date", "end_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    df = df.astype(object).where(pd.notnull(df), None)
    return df


def get_stock_pledge(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取A股公司股权质押

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_pledge(
        ... symbol="",
        ... start_date="20250101",
        ... end_date="20260101",
        ... fields=["hold_shares","hold_ratio"]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_EQUITY_PLEDGE), payload=payload)
    if not df.empty and {"symbol", "publish_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "publish_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_pledge_stat(
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票质押信息统计

    Args:
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_pledge_stat(
        ... start_date="20250101",
        ... end_date="20260101",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 2. 验证参数类型
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

    # 3. 验证fields列表中是否有重复值（空值会被正确处理）
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 4. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 5. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_EQUITY_PLEDGE_STAT), payload=payload)

    if not df.empty:
        # 过滤掉stat_period列
        if "stat_period" in df.columns:
            df = df.drop(columns=["stat_period"])

        # 将 pledge_begin_date 和 pledge_end_date 列放在最前面
        cols = df.columns.tolist()
        priority_cols = ["pledge_begin_date", "pledge_end_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_rela_party_trans(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_RELA_PARTY_TRANS), payload=payload)
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    df = df.astype(object).where(pd.notnull(df), None)
    return df


def get_stock_shareholder_change(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股东增减持计划

    Args:
        symbol (str): 股票代码，非必填
        start_date (str): 开始日期,eg:"20250702"，非必填
        end_date (str): 结束日期,eg:"20250702"，非必填
        fields (str): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        ... result = panda_data.get_stock_shareholder_change(
        ... symbol="",
        ... start_date="20250101",
        ... end_date="20260101",
        ... fields=[]
        ... )
        ... print(result)
    """
    # 1. 检查额外参数
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_SHAREHOLDER_TRADING_PLAN), payload=payload)
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_investor_brief_qa(
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取投资者问答数据

    Args:
        start_date: 开始日期，必填，格式为 YYYY-MM-DD
        end_date: 结束日期，必填，格式为 YYYY-MM-DD
        fields: 返回字段列表，可选
        **kwargs: 其他参数（会被验证）

    Returns:
        pd.DataFrame: 投资者问答数据

    Raises:
        ServiceError: 当参数验证失败时抛出异常
    """
    validate_extra_params(kwargs)

    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建payload
    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_INV_BRIEF_QA), payload=payload)

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"ask_time", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["ask_time", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_investor_brief_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取投资者问答详情数据

    Args:
        symbol: 股票代码列表，可选，需要进行A股股票格式验证
        start_date: 开始日期，必填，格式为 YYYY-MM-DD
        end_date: 结束日期，必填，格式为 YYYY-MM-DD
        fields: 返回字段列表，可选
        **kwargs: 其他参数（会被验证）

    Returns:
        pd.DataFrame: 投资者问答详情数据

    Raises:
        ServiceError: 当参数验证失败时抛出异常
    """
    validate_extra_params(kwargs)

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

    # 验证symbol格式（A股股票格式）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建payload
    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_INV_BRIEF_DETAIL), payload=payload)

    if not df.empty and "symbol" in df.columns:
        df = df[~df["symbol"].str.endswith(".BJ", na=False)]

    # 调整列顺序：如果存在 symbol 和 date 列，将其放在最前面
    if not df.empty and {"symbol", "date", "begin_time"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date", "begin_time"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_equity_nature(
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股权性质数据

    Args:
        symbol: 股票代码列表，可选，需要进行A股股票格式验证
        fields: 返回字段列表，可选
        **kwargs: 其他参数（会被验证）

    Returns:
        pd.DataFrame: 股权性质数据

    Raises:
        ServiceError: 当参数验证失败时抛出异常
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

    # 验证symbol格式（A股股票格式）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 构建payload
    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_EQUITY_NATURE), payload=payload)

    # 过滤掉结尾为.BJ的股票
    if not df.empty and "symbol" in df.columns:
        df = df[~df["symbol"].str.endswith(".BJ", na=False)]

    # 调整列顺序：如果存在 symbol 列，将其放在最前面
    if not df.empty and "symbol" in df.columns:
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_equity_illegal(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股权违规数据

    Args:
        symbol: 股票代码列表，可选，需要进行A股股票格式验证
        start_date: 开始日期，必填，格式为 YYYYMMDD
        end_date: 结束日期，必填，格式为 YYYYMMDD
        fields: 返回字段列表，可选
        **kwargs: 其他参数（会被验证）

    Returns:
        pd.DataFrame: 股权违规数据

    Raises:
        ServiceError: 当参数验证失败时抛出异常
    """
    validate_extra_params(kwargs)

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

    # 验证symbol格式（A股股票格式）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建payload
    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_EQUITY_ILLEGAL), payload=payload)

    # 过滤掉结尾为.BJ的股票
    if not df.empty and "symbol" in df.columns:
        df = df[~df["symbol"].str.endswith(".BJ", na=False)]

    # 调整列顺序：如果存在 symbol 和 info_date 列，将其放在最前面
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_equity_placard(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股权举牌数据

    Args:
        symbol: 股票代码列表，可选，需要进行A股股票格式验证
        start_date: 开始日期，必填，格式为 YYYYMMDD
        end_date: 结束日期，必填，格式为 YYYYMMDD
        fields: 返回字段列表，可选
        **kwargs: 其他参数（会被验证）

    Returns:
        pd.DataFrame: 股权举牌数据

    Raises:
        ServiceError: 当参数验证失败时抛出异常
    """
    validate_extra_params(kwargs)

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

    # 验证symbol格式（A股股票格式）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        # 验证symbol列表中是否有重复值
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    # 构建payload
    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_EQUITY_PLACARD), payload=payload)

    # 过滤掉结尾为.BJ的股票
    if not df.empty and "symbol" in df.columns:
        df = df[~df["symbol"].str.endswith(".BJ", na=False)]

    # 调整列顺序：如果存在 symbol 和 info_date 列，将其放在最前面
    if not df.empty and {"symbol", "info_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "info_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_disclosure_date(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取上市A股定期报告预披露数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 股票代码列表，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 上市A股定期报告预披露数据，包含以下字段：
            - symbol: 股票代码
            - name: 证券简称
            - expected_disclosure_date: 预计披露日
            - end_date: 报告期
            - actual_disclosure_date: 实际披露日
            - first_change_date: 第一次变更日期
            - second_change_date: 第二次变更日期
            - third_change_date: 第三次变更日期
            - first_publish_date: 首次发布日期
            - latest_predisclosure_date: 最新预披露日期
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "expected_disclosure_date" not in fields:
            fields.append("expected_disclosure_date")
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
        validate_symbol_format(validated_params['symbol'])
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
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']
    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_DISCLOSURE_DATE), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_status_over_allotment(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取超额配售权实施情况（仅A股数据）

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 股票代码列表，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 超额配售权实施情况数据，包含以下字段：
            - symbol: 股票代码
            - name: 证券简称
            - info_date: 公告日期
            - end_date: 最后行使日期
            - vwap: 行权中竞价交易购买股票均价
            - volume: 行权中竞价交易购买股票数量
            - over_allotment_shares: 超额发行股份数
            - over_allotment_rate: 超额配售率
            - full_subscription_flag: 是否全额(0：否，1：是，2：未获知，3:不排除)
            - additional_raised_funds: 增加的募集资金
            - additional_raised_fee: 增加的募集资金费用
            - total_proceeds_exercise: 行权后募集资金总额人民币
            - net_proceeds_exercise: 行权后募集资金净额人民币
            - foreign_total_proceeds_exercise: 行权后募集资金总额外币
            - foreign_net_proceeds_exercise: 行权后募集资金净额外币
            - currency_symbol: 外币币种(HKD：港元，USD：美元)
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "info_date" not in fields:
            fields.append("info_date")
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
        validate_symbol_format(validated_params['symbol'])
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
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_STATUS_OVER_ALLOTMENT), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_litigation_arbitration(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        lawsuit_type: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取上市公司诉讼仲裁数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 股票代码列表，不传则查询所有
        lawsuit_type: 诉讼类型列表，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 上市公司诉讼仲裁数据，包含以下字段：
            - symbol: 证券代码
            - name: 证券简称
            - info_date: 公告日期
            - lawsuit_type: 诉讼类型(CI:民事诉讼,AD:行政诉讼,CR:刑事诉讼,AR:仲裁)
            - filing_date: 起诉日期
            - case_summary: 案件摘要
            - case_intro: 案件简介
            - case_progress: 案件进展
            - involved_amount: 涉案金额(元)
            - currency_code: 货币代码
            - plaintiff: 原告方
            - defendant: 被告方
            - first_court: 一审受理法院
            - first_judgment_date: 一审判决日期
            - is_appeal_flg: 是否上诉(1:是，0:否，2:不排除)
            - appellant_type: 上诉方(P:原告，D:被告，TP:其他)
            - second_court: 二审受理法院
            - second_judgment_date: 二审判决日期
            - judgment_content: 判决/仲裁内容
            - remark: 备注
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "info_date" not in fields:
            fields.append("info_date")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'lawsuit_type': lawsuit_type,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'lawsuit_type': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'lawsuit_type', 'fields']
    )

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证 lawsuit_type 列表中是否有重复值
    if validated_params['lawsuit_type'] is not None:
        validate_no_duplicates(validated_params['lawsuit_type'], 'lawsuit_type')

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
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['lawsuit_type'] is not None:
        payload["lawsuitType"] = validated_params['lawsuit_type']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_LITIGATION_ARBITRATION), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_csrc_approval(
        start_date: str = None,
        end_date: str = None,
        announcement_level: Optional[Union[int, List[int]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取证监会批文数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        announcement_level: 公告级别列表，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 证监会批文数据，包含以下字段：
            - publish_date: 发文日期
            - publish_institution: 发布机构
            - announcement_category: 公告类别
            - announcement_level: 公告级别(分为01级、02级、03级)
            - announcement_title: 公告名称
            - announcement_number: 公告文号
            - announcement_content: 公告正文
            - attachment_link: 附件链接
            - announcement_link: 公告链接
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "publish_date" not in fields:
            fields.append("publish_date")
        if "announcement_title" not in fields:
            fields.append("announcement_title")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'announcement_level': announcement_level,
        'fields': fields
    }

    type_config = {
        'announcement_level': int,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['announcement_level', 'fields']
    )

    # 验证 announcement_level 列表中是否有重复值
    if validated_params['announcement_level'] is not None:
        validate_no_duplicates(validated_params['announcement_level'], 'announcement_level')

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
    if validated_params['announcement_level'] is not None:
        payload["announcementLevel"] = validated_params['announcement_level']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_CSRC_APPROVAL), payload=payload)

    # 整理列顺序
    if not df.empty and {"publish_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["publish_date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_competitor_information(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取竞争企业信息数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 股票代码列表，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 竞争企业信息数据，包含以下字段：
            - symbol: 证券代码
            - info_date: 公告日期
            - name: 证券简称
            - competitor_name: 竞争公司名称
            - competitor_intro: 竞争公司机构介绍
            - competitor_stock_code: 竞争公司股票代码
            - competition_fields: 竞争领域（有多个时，以","分割）
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "info_date" not in fields:
            fields.append("info_date")
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
        validate_symbol_format(validated_params['symbol'])
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
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_COMPETITOR_INFORMATION), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_intermediary_information(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        event_type: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取中介情况信息表数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 股票代码列表，不传则查询所有
        event_type: 事件类型列表，不传则查询所有（PIPE:定向增发；FO:公开增发；IPO:首发；RI:配股；PREF:优先股；PRE:定期报告）
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 中介情况信息表数据，包含以下字段：
            - symbol: 股票代码
            - name: 证券简称
            - equity_event_code: 权益融资事件代码
            - event_type: 事件类型（PIPE:定向增发；FO:公开增发；IPO:首发；RI:配股；PREF:优先股；PRE:定期报告）
            - issue_start_date: 发行起始日
            - intermediary_category: 中介机构类别
            - intermediary_name: 中介机构名称
            - intermediary_handler: 中介机构经办人姓名
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "event_type" not in fields:
            fields.append("event_type")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'event_type': event_type,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'event_type': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'event_type', 'fields']
    )

    # 验证 symbol 列表中是否有重复值
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证 event_type 列表中是否有重复值
    if validated_params['event_type'] is not None:
        validate_no_duplicates(validated_params['event_type'], 'event_type')

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
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_params['event_type'] is not None:
        payload["eventType"] = validated_params['event_type']
    if validated_params['fields'] is not None:
        payload["fields"] = validated_params['fields']

    # 发送请求获取数据
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_INTERMEDIARY_INFORMATION), payload=payload)

    # 整理列顺序
    if not df.empty and {"symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_material_contract(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取上市公司重大合同数据

    参数:
        start_date: 开始日期，格式 "YYYYMMDD"，如 "20250702"
        end_date: 结束日期，格式 "YYYYMMDD"，如 "20250702"
        symbol: 股票代码列表，不传则查询所有
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 上市公司重大合同数据，包含以下字段：
            - symbol: 股票代码
            - name: 证券简称
            - info_date: 公告日期
            - info_id: 公告id
            - project_progress: 项目进度
            - contract_party_a: 甲方
            - contract_party_b: 乙方
            - party_b_relation: 上市公司与乙方关系
            - project_name: 项目名称
            - contract_title: 合同名称
            - max_contract_amount: 合同金额上限
            - min_contract_amount: 合同金额下限
            - currency: 币种
            - has_affiliation: 是否存在关联关系(0:否,1:是,2:未获知)
            - is_related_party_transaction: 是否构成关联交易(0:否,1:是,2:未获知)
            - contract_term: 合同期限
            - effective_date: 合同生效日期
            - expiration_date: 合同截止日期
            - operation_mode: 运作模式
            - bid_amount: 中标金额/上年度营业收入
            - consortium_members: 联合体成员
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "info_date" not in fields:
            fields.append("info_date")

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
    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_MATERIAL_CONTRACT), payload=payload)

    # 整理列顺序
    if not df.empty and {'info_date', "symbol"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["info_date", "symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]

    return df


def get_stock_preferred_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        plan_progress: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取优先股基本资料

    参数:
        symbol: 优先股代码列表，不传则查询所有
        exchange: 交易市场
        plan_progress: 方案进度（董事会通过/国资委批准/方案实施/银监会批准/上市委通过/股东大会通过/发审委通过/证监会批准/停止实施）
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 优先股基本资料数据，包含以下字段：
            - symbol: 优先股代码
            - exchange: 交易市场
            - name: 优先股名称
            - publish_date: 最新公告日
            - issue_target: 发行对象
            - face_value: 票面金额(元)
            - currency_code: 货币代码
            - dividend_yield: 票面股息率(百分比)
            - dividend_yield_description: 股息率说明
            - dividend_yield_type: 股息率类型
            - issuance_method: 发行方式
            - is_installment: 是否分次对应(0:否,1:是;2:未获知)
            - subscription_method: 认购方式
            - max_issue_volume: 发行数量上限(万股)
            - min_issue_volume: 发行数量下限(万股)
            - actual_issue_volume: 实际发行数量(万股)
            - offering_price: 发行价格
            - plan_progress: 方案进度
            - board_plan_date: 董事会预案公告日
            - shareholder_meeting_date: 股东大会决议公告日
            - cbrc_approval_date: 银监会批准公告日
            - ipo_review_date: 发审委通过公告日
            - csrc_approval_date: 证监会核准公告日
            - registration_date: 登记日期
            - issuance_ann_date: 发行公告日
            - listing_ann_date: 挂牌转让公告日
            - listed_date: 上市日期
            - is_accumulated: 股息是否累计对应(0:否,1:是;2:未获知)
            - is_convertible: 是否可转换为普通股对应(0:否,1:是;2:未获知)
            - voting_restrictions: 表决限制条款
            - voting_right_recovery: 表决权恢复条件
            - is_forced_conversion: 是否可强制转换为普通股对应(0:否,1:是;2:未获知)
            - forced_conversion_conditions: 强制转换为普通股条件
            - annual_payment_count: 年付息次数
            - first_interest_date: 首次起息日
            - dividend_adjustment_period: 股息调整周期(年)
            - purchasedate: 申购日
            - underwriting_method: 承销方式
            - max_planned_raising: 预计募集资金上限
            - min_planned_raising: 预计募集资金下限
            - actual_raising_amount: 实际募集资金
            - net_raising_amount: 募集资金净额
            - fund_usage: 资金用途
            - is_at_par: 是否可强制转换为普通股对应(0:否,1:是;2:未获知)
            - put_provision: 回售条款
            - forced_conversion_price: 强制转股价格(元/股)
            - fund_receipt_date: 募集资金到账日期
            - fund_verification_date: 募集资金验资日期
            - transfer_arrangement: 转让安排
            - reference_date: 基准日
            - reference_date_type: 基准日类型
            - right_to_residual_profit: 是否可强制转换为普通股对应(0:否,1:是;2:未获知)
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
        'plan_progress': plan_progress,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'plan_progress': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'plan_progress', 'fields']
    )

    # 验证symbol格式（空值会被正确处理）
    if validated_params['symbol'] is not None:
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证exchange（空值会被正确处理）
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated_params['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    plan_progress_list = _normalise_list(validated_params['plan_progress'])
    if plan_progress_list is not None:
        payload["planProgress"] = plan_progress_list
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PREFERRED_DETAIL), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        df = df.sort_values(['symbol']).reset_index(drop=True)
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_preferred_placement(
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        target_type: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取优先股配售结果

    参数:
        symbol: 优先股代码列表，不传则查询所有
        exchange: 交易市场
        target_type: 发行对象类型（财务公司/基金公司资产管理计划/基金公司/其他/投资公司/信托公司/信托计划/证券公司/资产管理公司/城市商业银行/租赁公司/基金管理公司/地方政府国有资产管理机构/非确定性基金公司资产管理计划）
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 优先股配售结果数据，包含以下字段：
            - symbol: 优先股代码
            - exchange: 交易市场
            - issuer_target: 发行对象
            - target_type: 发行对象类型
            - subscription_volume: 认购数量(万股)
            - subscription_amount: 认购金额(万元)
            - is_related_party: 是否为关联方(0:否,1:是;2:未获知)
            - has_recent_related_transaction: 最近一年是否存在关联交易(0:否,1:是;2:未获知)
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
        'target_type': target_type,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'target_type': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'target_type', 'fields']
    )

    # 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证exchange
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated_params['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    target_type_list = _normalise_list(validated_params['target_type'])
    if target_type_list is not None:
        payload["targetType"] = target_type_list
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PREFERRED_PLACEMENT), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        df = df.sort_values(['symbol']).reset_index(drop=True)
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_preferred_rating(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        rating_level: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取优先股评级情况

    参数:
        start_date: 开始日期（公告日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        end_date: 结束日期（公告日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        symbol: 优先股代码列表，不传则查询所有
        exchange: 交易市场
        rating_level: 评级，格式如 "AA"
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 优先股评级情况数据，包含以下字段：
            - symbol: 优先股代码
            - exchange: 交易市场
            - publish_date: 公告日
            - rating_date: 评级日
            - rating_level: 评级
            - rating_agency: 评级机构简称
    """
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
    # 验证参数类型
    params = {
        'symbol': symbol,
        'exchange': exchange,
        'rating_level': rating_level,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'rating_level': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'rating_level', 'fields']
    )

    # 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证exchange
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated_params['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    rating_level_list = _normalise_list(validated_params['rating_level'])
    if rating_level_list is not None:
        payload["ratingLevel"] = rating_level_list
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PREFERRED_RATING), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        df = df.sort_values(['symbol', 'publish_date']).reset_index(drop=True)
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_preferred_shares(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取优先股股本数据

    参数:
        start_date: 开始日期（公告日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        end_date: 结束日期（公告日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        symbol: 股票代码列表，不传则查询所有
        exchange: 交易市场
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 优先股股本数据，包含以下字段：
            - symbol: 股票代码
            - name: 股票名称
            - exchange: 交易市场代码
            - publish_date: 公告日期
            - change_date: 变动日期
            - change_reason: 变动原因
            - issue_shares: 发行股份数量(万股)
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "publish_date" not in fields:
            fields.append("publish_date")
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

    # 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证exchange
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated_params['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PREFERRED_SHARES), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        df = df.sort_values(['symbol', 'publish_date']).reset_index(drop=True)
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_issuer_credit_rating(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        rating_level: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取优先股发行主体信用评级

    参数:
        start_date: 开始日期（公告日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        end_date: 结束日期（公告日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        symbol: 股票代码列表，不传则查询所有
        rating_level: 级别，格式如 "AA"
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 发行主体信用评级数据，包含以下字段：
            - symbol: 股票代码
            - name: 股票名称
            - full_name: 发行主体
            - publish_date: 公告日期
            - rating_date: 评级日期
            - rating_level: 级别
            - outlook: 展望（1:正面;2:稳定;3:负面;4:列入评级观察(可能调低);5:列入评级观察(走势不明);6:观望）
            - rating_company: 评级公司
            - previous_level: 上次级别
            - previous_outlook: 上次展望
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "publish_date" not in fields:
            fields.append("publish_date")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'rating_level': rating_level,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'rating_level': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'rating_level', 'fields']
    )

    # 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    rating_level_list = _normalise_list(validated_params['rating_level'])
    if rating_level_list is not None:
        payload["ratingLevel"] = rating_level_list
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_ISSUER_CREDIT_RATING), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        df = df.sort_values(['symbol', 'publish_date']).reset_index(drop=True)
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_preferred_trading(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取优先股成交统计信息

    参数:
        start_date: 开始日期（交易日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        end_date: 结束日期（交易日期），格式 "YYYYMMDD"，如 "20250702"（必填）
        symbol: 优先股代码列表，不传则查询所有
        exchange: 交易市场
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 优先股成交统计信息数据，包含以下字段：
            - symbol: 优先股代码
            - exchange: 交易市场
            - date: 交易日期
            - price: 成交价(元)
            - volume: 成交量(股)
            - amount: 成交金额(元)
            - buyer_department: 买入营业部
            - seller_department: 卖出营业部
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

    # 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证exchange
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated_params['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PREFERRED_TRADING), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        df = df.sort_values(['symbol', 'date']).reset_index(drop=True)
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_preferred_dividend(
        start_date: str = None,
        end_date: str = None,
        symbol: Optional[Union[str, List[str]]] = None,
        exchange: Optional[Union[str, List[str]]] = None,
        procedure: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    [WARNING: 此接口已废弃或未上线，调用前请确认服务端支持]

    获取优先股分红数据

    参数:
        start_date: 开始日期（最新公告日），格式 "YYYYMMDD"，如 "20250702"（必填）
        end_date: 结束日期（最新公告日），格式 "YYYYMMDD"，如 "20250702"（必填）
        symbol: 优先股代码列表，不传则查询所有
        exchange: 交易市场
        procedure: 事件进程（1:董事会通过;2:股东大会通过;3:实施;4:停止实施）
        fields: 指定返回的字段列表
    返回:
        pd.DataFrame: 优先股分红数据，包含以下字段：
            - symbol: 优先股代码
            - exchange: 交易市场
            - interest_start_date: 计息起始日
            - interest_end_date: 计息截止日
            - publish_date: 最新公告日
            - plan_ann_date: 预案公告日
            - meeting_date: 股东大会公告日
            - dividend_date: 分红实施公告日
            - procedure: 事件进程
            - currency_code: 货币代码
            - coupon_dividend_rate: 票面股息率(百分比)
            - dividend_pre_tax: 每股派现(税前,元)
            - dividend_after_tax: 每股派现(税后,元)
            - total_dividend_amount: 派息总额(万元,元)
            - last_trading_date: 最后交易日
            - record_date: 股权登记日
            - ex_date: 除息日
            - payment_date: 派息日
    """
    validate_extra_params(kwargs)
    if fields is not None:
        if isinstance(fields, str):
            fields = [fields]
        if "symbol" not in fields:
            fields.append("symbol")
        if "publish_date" not in fields:
            fields.append("publish_date")
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

    # 验证参数类型
    params = {
        'symbol': symbol,
        'exchange': exchange,
        'procedure': procedure,
        'fields': fields
    }

    type_config = {
        'symbol': str,
        'exchange': str,
        'procedure': str,
        'fields': str
    }

    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=['symbol', 'exchange', 'procedure', 'fields']
    )

    # 验证symbol格式
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 验证exchange
    if validated_params['exchange'] is not None:
        validate_no_duplicates(validated_params['exchange'], 'exchange')

    # 验证fields列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    symbols = _normalise_symbols(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    exchange_list = _normalise_list(validated_params['exchange'])
    if exchange_list is not None:
        payload["exchange"] = [e.upper() for e in exchange_list]
    procedure_list = _normalise_list(validated_params['procedure'])
    if procedure_list is not None:
        payload["procedure"] = procedure_list
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_PREFERRED_DIVIDEND), payload=payload)
    if not df.empty and {"symbol"}.issubset(df.columns):
        df = df.sort_values(['symbol', 'publish_date']).reset_index(drop=True)
        cols = df.columns.tolist()
        priority_cols = ["symbol"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df


def get_stock_history_detail(
        symbol: Optional[Union[str, List[str]]] = None,
        start_date: str = None,
        end_date: str = None,
        status: Optional[int] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs
) -> pd.DataFrame:
    """
    获取股票历史逐日快照（含历史名称、上市/退市状态）。

    基于 stock_symbol_history Parquet 数据集，返回每只股票在每个交易日的状态快照。

    Args:
        symbol:     股票代码，如 "000001.SZ" 或 ["000001.SZ", "000002.SZ"]，默认为None返回所有
        start_date: 开始日期，格式 "YYYYMMDD"，必填
        end_date:   结束日期，格式 "YYYYMMDD"，必填
        status:     股票状态，1=Active（在市），0=Delisted（已退市），默认为None返回所有状态
        fields:     需要返回的字段列表，默认为None返回全部字段。
                    status: 1=Active（在市）, 0=Delisted（已退市）

    Returns:
        pd.DataFrame: 按 symbol ASC, date ASC 排序的结果
    """
    # 1. 检查额外参数和必填
    validate_extra_params(kwargs)
    validate_not_empty(start_date, "start_date")
    validate_not_empty(end_date, "end_date")

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

    # 3. 验证 symbol 格式（股票格式）
    if validated_params['symbol'] is not None:
        validate_symbol_format(validated_params['symbol'])
        validate_no_duplicates(validated_params['symbol'], 'symbol')

    # 4. 验证 fields 列表中是否有重复值
    if validated_params['fields'] is not None:
        validate_no_duplicates(validated_params['fields'], 'fields')

    # 5. 验证 status 参数
    validated_status = validate_stock_status(status, "status") if status is not None else status

    # 6. 验证日期格式
    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")

    # 7. 验证日期范围
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    symbols = _normalise_list(validated_params['symbol'])
    if symbols is not None:
        payload["symbol"] = symbols
    if validated_start_date:
        payload["startDate"] = validated_start_date
    if validated_end_date:
        payload["endDate"] = validated_end_date
    if validated_status is not None:
        payload["status"] = validated_status
    if validated_params['fields']:
        payload["fields"] = validated_params['fields']

    df = fetch_dataframe(build_endpoint(STOCK_ENDPOINT, PATH_GET_STOCK_SYMBOL_HISTORY), payload=payload)
    if not df.empty and {"symbol", "date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "date"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df

