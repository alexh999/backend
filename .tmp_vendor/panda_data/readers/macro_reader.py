from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Tuple, Union

import pandas as pd

from panda_data.core.service import fetch_dataframe
from panda_data.utils.common_utils import build_endpoint
from panda_data.utils.param_check_utils import (
    validate_date_format,
    validate_date_range,
    validate_extra_params,
    validate_no_duplicates,
    validate_param_types, validate_macro_category, validate_macro_symbol_format,
)

BASE_ENDPOINT = "/macro"
PATH_GET_MACRO_ECO_CALENDAR_DATA = "/getMacroCalData"
PATH_GET_MACRO_CAL_CONFIG = "/getMacroCalConfig"
PATH_GET_MACRO_CAL_INFO = "/getMacroCalInfo"
PATH_GET_MACRO_DETAIL = "/getMacroDetail"
PATH_GET_MACRO_GB_DATA = "/getMacroGbData"

# macro_cal_config：与服务端一致，对外固定四列（region_code 由 event_code 推导或后端返回）
_MACRO_CAL_CONFIG_OUTPUT_COLS: Tuple[str, ...] = ("event_code", "indic_name", "region_code", "eco_name_cn")

def _normalize_fields_macro(fields: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    if fields is None:
        return None
    if isinstance(fields, str):
        return [fields.strip()] if str(fields).strip() else None
    out = [str(x).strip() for x in fields if x is not None and str(x).strip()]
    return out or None

def _region_code_from_event_code_series(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    head = s.str.split(".").str[0]
    return head.where(head.str.len() > 0, s.str[:3])

def _finalize_macro_cal_config_df(
    df: pd.DataFrame, fields: Optional[Union[str, List[str]]]
) -> pd.DataFrame:
    """统一为四列；region_code 始终由 event_code 推导（与本地 SDK 一致）。"""
    if df.empty:
        return pd.DataFrame(columns=list(_MACRO_CAL_CONFIG_OUTPUT_COLS))
    out = df.copy()
    for c in ("event_code", "indic_name", "eco_name_cn"):
        if c not in out.columns:
            out[c] = pd.NA
    out["region_code"] = _region_code_from_event_code_series(out["event_code"])
    out = out[list(_MACRO_CAL_CONFIG_OUTPUT_COLS)]
    qf = _normalize_fields_macro(fields)
    if qf:
        allowed = set(_MACRO_CAL_CONFIG_OUTPUT_COLS)
        qf = [c for c in qf if c in allowed]
        if qf:
            out = out[qf]
    return out.reset_index(drop=True)

def get_macro_cal(
    event_code: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    宏观经济日历

    Args:
        event_code (str or list[str]): 日历指标代码，完整指标码表见文件下载，非必填
        start_date (str): 开始日期 YYYYMMDD，必填
        end_date (str): 结束日期 YYYYMMDD，必填
        fields (str or list[str]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_macro_cal(
        ...     event_code="CHN.001",
        ...     start_date="20260101",
        ...     end_date="20260401",
        ... )
    """
    validate_extra_params(kwargs)

    params = {"event_code": event_code, "fields": fields}
    type_config = {"event_code": str, "fields": str}
    validated_params = validate_param_types(
        params,
        type_config,
        allowed_list_params=["event_code", "fields"],
    )

    if validated_params["event_code"] is not None:
        validate_no_duplicates(validated_params["event_code"], "event_code")
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_params["event_code"] is not None:
        payload["eventCode"] = validated_params["event_code"]
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_MACRO_ECO_CALENDAR_DATA), payload=payload)
    if not df.empty and {"event_code", "pub_date_bj"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["event_code", "pub_date_bj"]
        other_cols = [col for col in cols if col not in priority_cols]
        df = df[priority_cols + other_cols]
    return df

def get_macro_cal_config(
    event_code: Optional[Union[str, List[str]]] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    宏观经济日历配置

    Args:
        event_code (str or list[str]): 日历指标代码，完整指标码表见文件下载，必填
        fields (str or list[str]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_macro_cal_config(
        ...     event_code="CHN.001",
        ... )
    """
    validate_extra_params(kwargs)
    params = {"event_code": event_code, "fields": fields}
    validated_params = validate_param_types(
        params,
        {"event_code": str, "fields": str},
        allowed_list_params=["event_code", "fields"],
    )
    if validated_params["event_code"] is not None:
        validate_no_duplicates(validated_params["event_code"], "event_code")
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    payload = {}
    if validated_params["event_code"] is not None:
        payload["eventCode"] = validated_params["event_code"]
    # fields 不在此传参；由客户端对四列子集过滤
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_MACRO_CAL_CONFIG), payload=payload)
    return _finalize_macro_cal_config_df(df, fields)

def get_macro_cal_info(
    event_code: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    宏观经济日历信息

    Args:
        event_code (str or list[str]): 日历指标代码，完整指标码表见文件下载，非必填
        start_date (str): 开始日期 YYYYMMDD，必填
        end_date (str): 结束日期 YYYYMMDD，必填
        fields (str or list[str]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_macro_cal_info(
        ...     event_code="CHN.001",
        ...     start_date="20150101",
        ...     end_date="20260401",
        ... )
    """
    validate_extra_params(kwargs)
    params = {"event_code": event_code, "fields": fields}
    validated_params = validate_param_types(
        params,
        {"event_code": str, "fields": str},
        allowed_list_params=["event_code", "fields"],
    )
    if validated_params["event_code"] is not None:
        validate_no_duplicates(validated_params["event_code"], "event_code")
    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    validated_start_date = validate_date_format(start_date, "start_date")
    validated_end_date = validate_date_format(end_date, "end_date")
    validate_date_range(validated_start_date, validated_end_date)

    payload = {}
    if validated_params["event_code"] is not None:
        payload["eventCode"] = validated_params["event_code"]
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_MACRO_CAL_INFO), payload=payload)
    if not df.empty and {"event_code", "pub_date_bj"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["event_code", "pub_date_bj"]
        df = df[priority_cols + [c for c in cols if c not in priority_cols]]
    return df

def get_macro_detail(
        category: Union[str, List[str]],
        symbol: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
) -> pd.DataFrame:
    """
    宏观指标列表

    Args:
        category (str or list[str]): 指标分类代码（见下表），必填
        symbol (str or list[str]): 指标代码（非空时将覆盖category的筛选进行查询），非必填
        fields (str or list[str]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_macro_detail(
        ...     symbol=[""],
        ...     category=["TR"],
        ...     fields=[""],
        ... )
    """
    validate_extra_params(kwargs)

    # 验证category参数（必填）
    validated_categories = validate_macro_category(category, "category")

    # 验证symbol参数（可选）
    params = {"symbol": symbol, "fields": fields}
    validated_params = validate_param_types(
        params,
        {"symbol": str, "fields": str},
        allowed_list_params=["symbol", "fields"],
    )

    if validated_params["symbol"] is not None:
        validated_params["symbol"] = validate_macro_symbol_format(validated_params["symbol"])
        validate_no_duplicates(validated_params["symbol"], "symbol")

    if validated_params["fields"] is not None:
        validate_no_duplicates(validated_params["fields"], "fields")

    # 构建payload
    payload = {}

    # category必填
    payload["category"] = validated_categories

    # symbol可选
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]

    # fields可选
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]

    # 调用远程服务
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, PATH_GET_MACRO_DETAIL), payload=payload)

    # 后处理：调整列顺序和过滤列
    if not df.empty:
        # 过滤不需要的列
        columns_to_drop = ['demo_id', 'parentID', 'dataApiID', 'dataApiName']
        existing_cols_to_drop = [col for col in columns_to_drop if col in df.columns]
        if existing_cols_to_drop:
            df = df.drop(columns=existing_cols_to_drop)

        # 将symbol列放到首列
        if "symbol" in df.columns:
            cols = df.columns.tolist()
            df = df[["symbol"] + [c for c in cols if c != "symbol"]]

    return df

# ---------- macro_all（远程 Java Admin）----------

# (两字母前缀大写, economy_tier, macro_subdir) — 与 Hub macro_all_clean_service.ECONOMY_PREFIX_TO_MACRO_SUBDIR 一致
_MACRO_ALL_ROWS: List[Tuple[str, str, str]] = [
    ("NA", "cn_macro", "macro_na"),
    ("IN", "cn_macro", "macro_in"),
    ("CI", "cn_macro", "macro_ci"),
    ("PI", "cn_macro", "macro_pi"),
    ("FA", "cn_macro", "macro_fa"),
    ("FI", "cn_macro", "macro_fi"),
    ("MB", "cn_macro", "macro_mb"),
    ("IR", "cn_macro", "macro_ir"),
    ("FE", "cn_macro", "macro_fe"),
    ("DT", "cn_macro", "macro_dt"),
    ("EW", "cn_macro", "macro_ew"),
    ("LI", "cn_macro", "macro_li"),
    ("PR", "cn_macro", "macro_pr"),
    ("SE", "cn_macro", "macro_se"),
    ("SM", "cn_macro", "macro_sm"),
    ("PM", "cn_macro", "macro_pm"),
    ("AG", "feature_data", "macro_ag"),
    ("EN", "feature_data", "macro_en"),
    ("CH", "feature_data", "macro_ch"),
    ("ST", "feature_data", "macro_st"),
    ("NF", "feature_data", "macro_nf"),
    ("BM", "feature_data", "macro_bm"),
    ("AU", "feature_data", "macro_au"),
    ("ME", "feature_data", "macro_me"),
    ("EE", "feature_data", "macro_ee"),
    ("TM", "feature_data", "macro_tm"),
    ("FB", "feature_data", "macro_fb"),
    ("TE", "feature_data", "macro_te"),
    ("PP", "feature_data", "macro_pp"),
    ("PH", "feature_data", "macro_ph"),
    ("UT", "feature_data", "macro_ut"),
    ("TR", "feature_data", "macro_tr"),
    ("RC", "feature_data", "macro_rc"),
    ("TH", "feature_data", "macro_th"),
    ("CE", "feature_data", "macro_ce"),
    ("WR", "feature_data", "macro_wr"),
    ("FS", "feature_data", "macro_fs"),
    ("IS", "feature_data", "macro_is"),
    ("US", "global_macro", "macro_us"),
    ("EU", "global_macro", "macro_eu"),
    ("JP", "global_macro", "macro_jp"),
    ("KR", "global_macro", "macro_kr"),
    ("AS", "global_macro", "macro_as"),
    ("UK", "global_macro", "macro_uk"),
    ("FR", "global_macro", "macro_fr"),
    ("DE", "global_macro", "macro_de"),
    ("ID", "global_macro", "macro_id"),
    ("IT", "global_macro", "macro_it"),
    ("ES", "global_macro", "macro_es"),
    ("CA", "global_macro", "macro_ca"),
    ("SZ", "global_macro", "macro_sz"),
    ("RU", "global_macro", "macro_ru"),
    ("BR", "global_macro", "macro_br"),
    ("ZA", "global_macro", "macro_za"),
    ("MY", "global_macro", "macro_my"),
    ("IA", "global_macro", "macro_ia"),
    ("TU", "global_macro", "macro_tu"),
    ("TL", "global_macro", "macro_tl"),
    ("GL", "global_macro", "macro_gl"),
    ("SG", "global_macro", "macro_sg"),
    ("VN", "global_macro", "macro_vn"),
    ("KH", "global_macro", "macro_kh"),
    ("RP", "global_macro", "macro_rp"),
    ("BN", "global_macro", "macro_bn"),
    ("LA", "global_macro", "macro_la"),
    ("MM", "global_macro", "macro_mm"),
    ("EC", "industry_economy", "macro_ec"),
    ("MD", "industry_economy", "macro_md"),
    ("EH", "industry_economy", "macro_eh"),
    ("AD", "industry_economy", "macro_ad"),
    ("HA", "industry_economy", "macro_ha"),
    ("OF", "industry_economy", "macro_of"),
    ("RB", "industry_economy", "macro_rb"),
    ("RE", "industry_economy", "macro_re"),
    ("ED", "industry_economy", "macro_ed"),
    ("EP", "industry_economy", "macro_ep"),
    ("AR", "industry_economy", "macro_ar"),
    ("CM", "industry_economy", "macro_cm"),
    ("OR", "industry_economy", "macro_or"),
]

def _java_subpath_for_prefix(prefix_upper: str) -> str:
    """NA → /getMacroNaData。"""
    p = prefix_upper.strip().upper()
    if len(p) < 2:
        raise ValueError("前缀长度不足 2")
    pq = p[0] + p[1].lower()
    return f"/getMacro{pq}Data"

JAVA_SUBPATH_BY_PREFIX: Dict[str, str] = {
    row[0]: _java_subpath_for_prefix(row[0]) for row in _MACRO_ALL_ROWS if row[1] != "global_macro"
}

_NON_GLOBAL_ROWS = [row for row in _MACRO_ALL_ROWS if row[1] != "global_macro"]

def _assert_macro_all_five_year_range(start_ymd: Optional[str], end_ymd: Optional[str]) -> None:
    """与 Java MacroAllSeriesServiceImpl 一致：macro_all 查询区间不得超过 5 个自然年。"""
    if not start_ymd or not end_ymd:
        return
    s = str(start_ymd).replace("-", "").strip()
    e = str(end_ymd).replace("-", "").strip()
    if len(s) != 8 or len(e) != 8 or not s.isdigit() or not e.isdigit():
        return
    d0 = datetime.strptime(s, "%Y%m%d").date()
    d1 = datetime.strptime(e, "%Y%m%d").date()
    y, m, day = d0.year + 5, d0.month, d0.day
    last = calendar.monthrange(y, m)[1]
    max_end = date(y, m, min(day, last))
    if d1 > max_end:
        raise ValueError("查询时间范围不能超过5年（结束日不得晚于起始日加5年）")

def _validate_series_params(
    symbol: Optional[Union[str, List[str]]],
    start_date: Optional[str],
    end_date: Optional[str],
    fields: Optional[Union[str, List[str]]],
    kwargs: dict,
) -> tuple:
    validate_extra_params(kwargs)
    params = {"symbol": symbol, "fields": fields}
    type_config = {"symbol": str, "fields": str}
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
    _assert_macro_all_five_year_range(validated_start_date, validated_end_date)
    return validated_params, validated_start_date, validated_end_date

def _build_macro_all_payload(
    validated_params: dict,
    validated_start_date: Optional[str],
    validated_end_date: Optional[str],
) -> dict:
    payload: dict = {}
    if validated_params["symbol"] is not None:
        payload["symbol"] = validated_params["symbol"]
    if validated_start_date is not None:
        payload["startDate"] = validated_start_date
    if validated_end_date is not None:
        payload["endDate"] = validated_end_date
    if validated_params["fields"]:
        payload["fields"] = validated_params["fields"]
    return payload

def _get_macro_all_series_remote(
    path: str,
    symbol: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs,
) -> pd.DataFrame:
    """调用 Java Admin 指定子路径，请求体为 MacroAllSeriesDTO 四字段 camelCase。"""
    validated_params, validated_start_date, validated_end_date = _validate_series_params(
        symbol, start_date, end_date, fields, kwargs
    )
    payload = _build_macro_all_payload(validated_params, validated_start_date, validated_end_date)
    df = fetch_dataframe(build_endpoint(BASE_ENDPOINT, path), payload=payload)
    if not df.empty and {"symbol", "period_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "period_date"]
        other_cols = [c for c in cols if c not in priority_cols]
        df = df[priority_cols + other_cols]
    return df

def _symbol_is_blank(symbol: Optional[Union[str, List[str]]]) -> bool:
    if symbol is None:
        return True
    if isinstance(symbol, list):
        return all(x is None or str(x).strip() == "" for x in symbol)
    return str(symbol).strip() == ""

def _first_non_blank_for_gb(symbol: Union[str, List[str]]) -> str:
    """取首条非空 symbol 并校验长度（前缀路由由 Java 或非空分支完成）。"""
    if isinstance(symbol, list):
        for sym in symbol:
            if sym is not None and str(sym).strip():
                s = str(sym).strip()
                if len(s) < 2:
                    raise ValueError("get_macro_gb：首条非空 symbol 长度至少为 2 以解析两字母前缀")
                return s
        raise ValueError("get_macro_gb：无有效 symbol")
    s = str(symbol).strip()
    if len(s) < 2:
        raise ValueError("get_macro_gb：symbol 长度至少为 2 以解析两字母前缀")
    return s

def get_macro_gb(
    symbol: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[Union[str, List[str]]] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    宏观行业-国际宏观

    Args:
        symbol (str or list[str]): 指标代码，完整指标码表见文件下载，非必填
        start_date (str): 开始日期 YYYYMMDD，必填
        end_date (str): 结束日期 YYYYMMDD，必填
        fields (str or list[str]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.get_macro_gb(
        ...     start_date="20260101",
        ...     end_date="20260430",
        ... )
    """
    if not _symbol_is_blank(symbol):
        _first_non_blank_for_gb(symbol)
    sym_for_validate = None if _symbol_is_blank(symbol) else symbol
    validated_params, validated_start_date, validated_end_date = _validate_series_params(
        sym_for_validate, start_date, end_date, fields, kwargs
    )
    payload = _build_macro_all_payload(validated_params, validated_start_date, validated_end_date)
    endpoint = build_endpoint(BASE_ENDPOINT, PATH_GET_MACRO_GB_DATA)
    df = fetch_dataframe(endpoint, payload=payload)
    if not df.empty and {"symbol", "period_date"}.issubset(df.columns):
        cols = df.columns.tolist()
        priority_cols = ["symbol", "period_date"]
        other_cols = [c for c in cols if c not in priority_cols]
        df = df[priority_cols + other_cols]
    return df

# 各前缀对应的宏观数据描述，用于生成各 get_macro_xx 函数的 docstring
_MACRO_PREFIX_DESC: Dict[str, str] = {
    "NA": "中国宏观-国民经济核算",
    "IN": "中国宏观-工业",
    "CI": "中国宏观-景气指数",
    "PI": "中国宏观-价格指数",
    "FA": "中国宏观-固定资产投资",
    "FI": "中国宏观-财政",
    "MB": "中国宏观-货币与银行",
    "IR": "中国宏观-利率汇率",
    "FE": "中国宏观-对外经济",
    "DT": "中国宏观-国内贸易",
    "EW": "中国宏观-就业与工资",
    "LI": "中国宏观-人民生活",
    "PR": "中国宏观-人口与资源",
    "SE": "中国宏观-科教体卫",
    "SM": "中国宏观-证券市场",
    "PM": "中国宏观-区域宏观",
    "AG": "宏观行业-农林牧渔",
    "EN": "宏观行业-能源",
    "CH": "宏观行业-化工",
    "ST": "宏观行业-钢铁",
    "NF": "宏观行业-有色金属",
    "BM": "宏观行业-建材",
    "AU": "宏观行业-汽车",
    "ME": "宏观行业-机械设备",
    "EE": "宏观行业-电子电器",
    "TM": "宏观行业-TMT",
    "FB": "宏观行业-食品饮料",
    "TE": "宏观行业-纺织服装",
    "PP": "宏观行业-造纸印刷",
    "PH": "宏观行业-医药生物",
    "UT": "宏观行业-公用事业",
    "TR": "宏观行业-交通运输",
    "RC": "宏观行业-房地产及建筑业",
    "TH": "宏观行业-旅游酒店",
    "CE": "宏观行业-文教体娱及工艺品",
    "WR": "宏观行业-批发零售业",
    "FS": "宏观行业-金融保险业",
    "IS": "宏观行业-行业综合",
    "EC": "宏观特色数据-线上电商数据",
    "MD": "宏观特色数据-医药数据",
    "EH": "宏观特色数据-能化数据",
    "AD": "宏观特色数据-汽车数据",
    "HA": "宏观特色数据-家电数据",
    "OF": "宏观特色数据-线下商超数据",
    "RB": "宏观特色数据-招聘数据",
    "RE": "宏观特色数据-房地产数据",
    "ED": "宏观特色数据-电子数据",
    "EP": "宏观特色数据-电新数据",
    "AR": "宏观特色数据-农业数据",
    "CM": "宏观特色数据-大宗数据",
    "OR": "宏观特色数据-其他",
}


def _build_fixed_path_getters_map() -> Tuple[List[str], Dict[str, Callable[..., pd.DataFrame]]]:
    """非全球桶：一前缀一函数；返回 (名称列表, 名称→函数)。"""
    names: List[str] = []
    out: Dict[str, Callable[..., pd.DataFrame]] = {}
    for prefix, tier, _subdir in _NON_GLOBAL_ROWS:
        path = JAVA_SUBPATH_BY_PREFIX[prefix]
        fn_name = f"get_macro_{prefix.lower()}"

        def _factory(sub_path: str, exported: str, doc: str = ""):
            def _fn(
                symbol: Optional[Union[str, List[str]]] = None,
                start_date: Optional[str] = None,
                end_date: Optional[str] = None,
                fields: Optional[Union[str, List[str]]] = None,
                **kw,
            ) -> pd.DataFrame:
                return _get_macro_all_series_remote(sub_path, symbol, start_date, end_date, fields, **kw)

            _fn.__name__ = exported
            _fn.__qualname__ = exported
            _fn.__doc__ = doc
            return _fn

        desc = _MACRO_PREFIX_DESC.get(prefix, "")
        if desc:
            doc = f"""
    {desc}

    Args:
        symbol (str or list[str]): 指标代码，完整指标码表见文件下载，非必填
        start_date (str): 开始日期 YYYYMMDD，必填
        end_date (str): 结束日期 YYYYMMDD，必填
        fields (str or list[str]): 返回字段列表，非必填
        **kwargs: 多余参数，传入额外参数将被拒绝

    Returns:
        pd.DataFrame

    请求示例:
        >>> import panda_data
        >>> result = panda_data.{fn_name}(
        ...     start_date="20220101",
        ...     end_date="20260430",
        ... )
    """
        else:
            doc = ""

        out[fn_name] = _factory(path, fn_name, doc)
        names.append(fn_name)
    return names, out

_MACRO_GETTER_NAMES, _REMOTE_MACRO_GETTERS = _build_fixed_path_getters_map()
for _k, _v in _REMOTE_MACRO_GETTERS.items():
    globals()[_k] = _v

# 显式绑定全部非全球 getter，便于 IDE/「转到定义」（与 _REMOTE_MACRO_GETTERS 内为同一对象）
get_macro_na: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_na"]
get_macro_in: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_in"]
get_macro_ci: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ci"]
get_macro_pi: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_pi"]
get_macro_fa: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_fa"]
get_macro_fi: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_fi"]
get_macro_mb: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_mb"]
get_macro_ir: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ir"]
get_macro_fe: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_fe"]
get_macro_dt: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_dt"]
get_macro_ew: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ew"]
get_macro_li: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_li"]
get_macro_pr: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_pr"]
get_macro_se: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_se"]
get_macro_sm: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_sm"]
get_macro_pm: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_pm"]
get_macro_ag: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ag"]
get_macro_en: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_en"]
get_macro_ch: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ch"]
get_macro_st: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_st"]
get_macro_nf: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_nf"]
get_macro_bm: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_bm"]
get_macro_au: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_au"]
get_macro_me: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_me"]
get_macro_ee: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ee"]
get_macro_tm: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_tm"]
get_macro_fb: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_fb"]
get_macro_te: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_te"]
get_macro_pp: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_pp"]
get_macro_ph: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ph"]
get_macro_ut: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ut"]
get_macro_tr: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_tr"]
get_macro_rc: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_rc"]
get_macro_th: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_th"]
get_macro_ce: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ce"]
get_macro_wr: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_wr"]
get_macro_fs: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_fs"]
get_macro_is: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_is"]
get_macro_ec: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ec"]
get_macro_md: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_md"]
get_macro_eh: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_eh"]
get_macro_ad: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ad"]
get_macro_ha: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ha"]
get_macro_of: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_of"]
get_macro_rb: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_rb"]
get_macro_re: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_re"]
get_macro_ed: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ed"]
get_macro_ep: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ep"]
get_macro_ar: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_ar"]
get_macro_cm: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_cm"]
get_macro_or: Callable[..., pd.DataFrame] = _REMOTE_MACRO_GETTERS["get_macro_or"]

# macro_all 动态注册的 get_macro_xx 与 get_macro_gb，供包 __init__ 同步导出
MACRO_ALL_PUBLIC_NAMES: List[str] = _MACRO_GETTER_NAMES + ["get_macro_gb"]

__all__ = [
    "get_macro_cal",
    "get_macro_cal_config",
    "get_macro_cal_info",
    *MACRO_ALL_PUBLIC_NAMES,
]
