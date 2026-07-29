# param_check_utils.py
from datetime import time
from typing import Any, Dict, List, Optional, Union, Tuple
import re
from panda_data.exceptions import ServiceError, ServiceErrorCode


def validate_date_format(date_str: Optional[str], param_name: str = "date") -> Optional[str]:
    """验证日期格式，支持YYYYMMDD或YYYY-MM-DD格式"""
    if date_str is None or date_str == "":
        return None

    if not isinstance(date_str, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(date_str).__name__}类型"
        )

    # 检查基本格式
    ymd_format = None

    # YYYY-MM-DD格式
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        clean_date = date_str.replace('-', '')
        ymd_format = (date_str[:4], date_str[5:7], date_str[8:10])
    # YYYYMMDD格式
    elif re.match(r'^\d{8}$', date_str):
        clean_date = date_str
        ymd_format = (date_str[:4], date_str[4:6], date_str[6:8])
    else:
        raise ServiceError(
            code=ServiceErrorCode.DATE_FORMAT_ERROR,
            message=f"[错误码 {ServiceErrorCode.DATE_FORMAT_ERROR}] {param_name}格式错误: {date_str}，应为YYYYMMDD或YYYY-MM-DD格式"
        )

    # 验证日期合法性
    try:
        year = int(ymd_format[0])
        month = int(ymd_format[1])
        day = int(ymd_format[2])

        # 基本范围检查
        if month < 1 or month > 12:
            raise ServiceError(
                code=ServiceErrorCode.DATE_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.DATE_FORMAT_ERROR}] {param_name}格式错误: {date_str}，月份必须在01-12之间"
            )

        # 每月天数
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        # 闰年检查
        is_leap_year = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        if is_leap_year:
            days_in_month[1] = 29

        max_days = days_in_month[month - 1]

        if day < 1 or day > max_days:
            raise ServiceError(
                code=ServiceErrorCode.DATE_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.DATE_FORMAT_ERROR}] {param_name}格式错误: {date_str}，{month}月的日期必须在01-{max_days}之间"
            )

    except ValueError:
        raise ServiceError(
            code=ServiceErrorCode.DATE_FORMAT_ERROR,
            message=f"[错误码 {ServiceErrorCode.DATE_FORMAT_ERROR}] {param_name}格式错误: {date_str}，包含非数字字符"
        )

    return clean_date


def validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> None:
    """验证日期范围"""
    if start_date and end_date and start_date > end_date:
        raise ServiceError(
            code=ServiceErrorCode.DATE_RANGE_INVALID,
            message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 日期范围无效: 开始日期({start_date})不能大于结束日期({end_date})"
        )


def validate_date_interval(start_date: Optional[str], end_date: Optional[str], max_years: Optional[int] = None,
                           max_months: Optional[int] = None) -> None:
    """
    验证日期间隔是否超过限制

    Args:
        start_date: 开始日期（YYYYMMDD格式）
        end_date: 结束日期（YYYYMMDD格式）
        max_years: 最大年数限制
        max_months: 最大月数限制
    """
    if not start_date or not end_date:
        return

    # 解析日期
    start_year = int(start_date[:4])
    start_month = int(start_date[4:6])
    start_day = int(start_date[6:8])

    end_year = int(end_date[:4])
    end_month = int(end_date[4:6])
    end_day = int(end_date[6:8])

    # 计算年数和月数差异
    year_diff = end_year - start_year
    month_diff = end_month - start_month
    day_diff = end_day - start_day

    # 验证年数限制
    if max_years is not None:
        # 计算实际间隔的年数（考虑月份和日期）
        if year_diff > max_years:
            # 超过最大年数
            raise ServiceError(
                code=ServiceErrorCode.DATE_RANGE_INVALID,
                message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 日期范围无效: 开始日期({start_date})和结束日期({end_date})的间隔不能超过{max_years}年"
            )
        elif year_diff == max_years:
            # 正好等于最大年数，需要检查月份和日期
            # 如果月份差大于0，或者月份差等于0但日期差大于0，则超过限制
            if month_diff > 0 or (month_diff == 0 and day_diff > 0):
                raise ServiceError(
                    code=ServiceErrorCode.DATE_RANGE_INVALID,
                    message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 日期范围无效: 开始日期({start_date})和结束日期({end_date})的间隔不能超过{max_years}年"
                )

    # 验证月数限制
    if max_months is not None:
        # 计算总月数
        total_months = year_diff * 12 + month_diff
        # 如果日期差为负，说明还没到那个月，需要减去1个月
        if day_diff < 0:
            total_months -= 1

        if total_months > max_months:
            raise ServiceError(
                code=ServiceErrorCode.DATE_RANGE_INVALID,
                message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 日期范围无效: 开始日期({start_date})和结束日期({end_date})的间隔不能超过{max_months}个月"
            )
        elif total_months == max_months:
            # 正好等于最大月数，如果日期差大于0，则超过限制
            if day_diff > 0:
                raise ServiceError(
                    code=ServiceErrorCode.DATE_RANGE_INVALID,
                    message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 日期范围无效: 开始日期({start_date})和结束日期({end_date})的间隔不能超过{max_months}个月"
                )


def validate_param_types(
        params: Dict[str, Any],
        type_config: Dict[str, Union[type, List[type]]],
        allowed_list_params: List[str] = None
) -> Dict[str, Any]:
    """验证参数类型"""
    if allowed_list_params is None:
        allowed_list_params = []

    validated_params = {}

    for param_name, param_value in params.items():
        if param_value is None:
            validated_params[param_name] = None
            continue

        expected_types = type_config.get(param_name)
        if expected_types:
            # 确保expected_types是列表格式
            if not isinstance(expected_types, list):
                expected_types = [expected_types]

            # 检查是否为允许的列表参数
            if param_name in allowed_list_params and isinstance(param_value, str):
                # 单个字符串转换为列表
                validated_params[param_name] = [param_value]
            elif param_name in allowed_list_params and isinstance(param_value, list):
                # 验证列表中每个元素的类型
                for item in param_value:
                    if not any(isinstance(item, t) for t in expected_types):
                        raise ServiceError(
                            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
                            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}列表中元素类型错误: 期望{[t.__name__ for t in expected_types]}，实际为{type(item).__name__}"
                        )
                validated_params[param_name] = param_value
            elif isinstance(param_value, tuple(expected_types)):
                validated_params[param_name] = param_value
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误: 期望{[t.__name__ for t in expected_types]}，实际为{type(param_value).__name__}"
                )
        else:
            # 如果没有配置类型，直接使用原值
            validated_params[param_name] = param_value

    return validated_params


def validate_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """验证symbol格式"""
    if symbols is None:
        return None

    if isinstance(symbols, str):
        # 如果是空字符串，直接返回
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    symbol_pattern = r'^\d{6}\.(SH|SZ)$'

    for sym in symbols_list:
        if sym == "":  # 跳过空字符串
            continue
        if not re.match(symbol_pattern, sym):
            if re.match(r'^\d{6}\.(sh|sz)$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数值格式错误: 错误的参数值{sym}，后缀必须为大写SH或SZ"
                )
            elif re.match(r'^\d{6}\.\w+$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数值格式错误: 错误的参数值{sym}，后缀必须为SH或SZ"
                )
            elif re.match(r'^\d+\.(SH|SZ)$', sym) and len(sym.split('.')[0]) != 6:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数值格式错误: 错误的参数值{sym}，股票代码必须为6位数字"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数值格式错误: 错误的参数值{sym}，格式应为6位数字+.+SH或SZ（如000001.SZ）"
                )

    return symbols


def validate_extra_params(kwargs: Dict[str, Any], valid_params: List[str] = None) -> None:
    """验证是否有额外参数"""
    if valid_params is None:
        valid_params = []

    extra_params = [k for k in kwargs.keys() if k not in valid_params]
    if extra_params:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_ERROR}] 请求参数错误: 发现未支持的参数 {extra_params}"
        )


def validate_side_value(side: str, param_name: str = "side") -> str:
    """
    验证side参数值，仅支持buy或sell或cum
    """
    if side is None or side == "":
        return None

    if not isinstance(side, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(side).__name__}类型"
        )

    valid_sides = ["buy", "sell", "cum"]
    if side.lower() not in valid_sides:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{side}无效: 有效值为 buy,sell,cum"
        )

    return side.lower()


def validate_no_duplicates(param_value: Union[str, List[str]], param_name: str = "param") -> Union[str, List[str]]:
    """
    验证列表参数中是否包含重复值
    """
    if param_value is None:
        return None

    # 如果是字符串，直接返回
    if isinstance(param_value, str):
        return param_value

    # 如果是列表，检查是否有重复（忽略空字符串）
    if isinstance(param_value, list):
        # 过滤掉空字符串
        non_empty_items = [item for item in param_value if item != ""]

        # 如果过滤后为空列表，直接返回原值
        if len(non_empty_items) == 0:
            return param_value

        seen = set()
        duplicated = set()
        for item in non_empty_items:
            if item in seen:
                duplicated.add(item)
            else:
                seen.add(item)

        if duplicated:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_DUPLICATED,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_DUPLICATED}] {param_name}参数存在重复值: {list(duplicated)}"
            )
        return param_value

    # 如果不是字符串或列表，抛出类型错误
    raise ServiceError(
        code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
        message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str或List[str]类型，得到{type(param_value).__name__}类型"
    )


def validate_not_empty(param_value: Any, param_name: str = "param") -> None:
    """
    验证参数不为空，支持 None、空字符串、空列表、全部元素为空的列表
    """
    if param_value is None:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
        )

    if isinstance(param_value, str) and param_value == "":
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
        )

    if isinstance(param_value, list):
        if len(param_value) == 0:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
            )
        # 检查列表是否全部元素为空字符串
        if all(item == "" for item in param_value):
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
            )


def validate_exchange(exchange: str, param_name: str = "exchange") -> str:
    """
    验证交易所参数，仅支持 SH, HK, US
    """
    if exchange is None or exchange == "":
        return "SH"

    if not isinstance(exchange, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(exchange).__name__}类型"
        )

    valid_exchanges = ["SH", "HK", "US"]
    if exchange.upper() not in valid_exchanges:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{exchange}无效: 有效值为SH、HK、US"
        )

    return exchange.upper()


def validate_is_trading_day(is_trading_day: int, param_name: str = "is_trading_day") -> int:
    """
    验证是否为交易日参数，仅支持 0 或 1
    """
    if is_trading_day is None or is_trading_day == "":
        return None

    if not isinstance(is_trading_day, int):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为int类型，得到{type(is_trading_day).__name__}类型"
        )

    if is_trading_day not in [0, 1]:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{is_trading_day}无效: 有效值为 0 或 1"
        )

    return is_trading_day


def validate_quarter_format(quarter: Optional[str], param_name: str = "quarter") -> Optional[str]:
    """验证季度格式，规范为 YYYYqN（q 小写，N 为 1-4），如 2024q1。"""
    if quarter is None or quarter == "":
        return None

    if not isinstance(quarter, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(quarter).__name__}类型"
        )

    normalized = quarter.strip().lower()
    # 匹配 YYYYqN；允许传入 2024Q1，统一为小写 2024q1
    pattern = r"^\d{4}q[1-4]$"
    if not re.match(pattern, normalized):
        raise ServiceError(
            code=ServiceErrorCode.DATE_FORMAT_ERROR,
            message=f"[错误码 {ServiceErrorCode.DATE_FORMAT_ERROR}] {param_name}格式错误: {quarter}，应为 YYYYqN（如 2025q1），字母 q 须为小写或 Q（将自动转为小写），N 为 1-4",
        )

    return normalized


def parse_quarter_to_int(quarter: str) -> int:
    """将季度格式转换为整数，用于比较大小，如2025q1 -> 202501, 2025q4 -> 202504"""
    year = int(quarter[:4])
    q = int(quarter[5])
    return year * 10 + q


def validate_quarter_range(start_quarter: Optional[str], end_quarter: Optional[str]) -> None:
    """验证季度范围，确保end_quarter >= start_quarter"""
    if start_quarter and end_quarter:
        start_int = parse_quarter_to_int(start_quarter)
        end_int = parse_quarter_to_int(end_quarter)
        if end_int < start_int:
            raise ServiceError(
                code=ServiceErrorCode.DATE_RANGE_INVALID,
                message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 季度范围无效: 开始季度({start_quarter})不能大于结束季度({end_quarter})"
            )


def validate_bool_type(value: Any, param_name: str = "param") -> bool:
    """验证参数是否为布尔类型"""
    if value is None:
        return value

    if not isinstance(value, bool):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为bool类型，得到{type(value).__name__}类型"
        )

    return value


def validate_fund_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """验证基金symbol格式，支持OF、SZ、SH后缀，代码长度不限"""
    if symbols is None:
        return None

    if isinstance(symbols, str):
        # 如果是空字符串，直接返回
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    # 基金代码格式：数字+.+OF/SZ/SH（如000001.OF, 159919.SZ, 510050.SH）
    fund_pattern = r'^[F\d]+\.(OF|SZ|SH)$'

    for sym in symbols_list:
        if sym == "":  # 跳过空字符串
            continue
        if not re.match(fund_pattern, sym):
            if re.match(r'^\d+\.(of|sz|sh)$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，后缀必须为大写OF、SZ或SH"
                )
            elif re.match(r'^\d+\.\w+$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，后缀必须为OF、SZ或SH"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，格式应为(F)+数字+.+OF/SZ/SH（如000001.OF,F450005.OF）"
                )

    return symbols


def validate_future_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """验证期货symbol格式，支持两种格式：合约(AG2201)或主力合约(A_DOMINANT)，自动去除.及之后的后缀"""
    if symbols is None:
        return None

    if isinstance(symbols, str):
        # 如果是空字符串，直接返回
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    # 期货合约格式：字母/下划线开头 + 4位数字结尾（如AG2201、A2201、VV_F2201）
    # 新增支持：若干位字母 + 4位数字 + 若干位字母（如L2602F）
    future_contract_pattern = r'^[A-Z_]+\d{4}$|^[A-Z]+\d{4}[A-Z]+$'
    # 主力合约格式：字母/下划线开头 + _DOMINANT结尾（如A_DOMINANT、VV_F_DOMINANT）
    dominant_contract_pattern = r'^[A-Z_]+_DOMINANT$'

    processed_symbols = []
    for sym in symbols_list:
        if sym == "":  # 跳过空字符串
            processed_symbols.append(sym)
            continue

        # 去除.及之后的内容
        original_sym = sym
        if '.' in sym:
            sym = sym.split('.')[0]

        # 验证处理后的格式
        if not (re.match(future_contract_pattern, sym) or re.match(dominant_contract_pattern, sym)):
            # 检查是否是小写格式
            if re.match(r'^[a-z_]+\d{4}$', sym) or re.match(r'^[a-z]+_dominant$', sym) or re.match(
                    r'^[a-z]+\d{4}[a-z]+$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，字母部分必须为大写"
                )
            # 检查是否是格式错误
            elif re.match(r'^[A-Z_]+\d+$', sym) and not re.match(future_contract_pattern, sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，数字部分必须为4位"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，格式应为大写字母+[4位数字]或大写字母+_DOMINANT（如AG2201或A_DOMINANT）或大写字母+4位数字+大写字母（如L2602F）"
                )

        # 添加处理后的symbol到结果列表
        processed_symbols.append(sym)

    # 返回处理后的结果
    if isinstance(symbols, str):
        return processed_symbols[0]
    else:
        return processed_symbols


def validate_option_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """验证期权symbol格式，支持多种期权合约格式，自动去除.及之后的后缀"""
    if symbols is None:
        return None

    if isinstance(symbols, str):
        # 如果是空字符串，直接返回
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    # 期权合约格式（上交所）：标的代码(6位)+期权类型(C/P)+行权价(8位，含小数点)+到期日(8位)
    # 例如：10007325C2412M02500、10007325P2412M02500
    shse_option_pattern = r'^\d{8}\.SH$'

    # 期权合约格式（深交所）：标的代码(4位)+期权类型(C/P)+行权价+到期日等
    # 例如：15001001C2412A02500
    szse_option_pattern = r'^\d{8}\.SZ$'

    # 商品期权格式：品种代码+到期年月+期权类型+行权价
    # 例如：SR401C4800、SR401P4800、i2401-C-3500
    commodity_option_pattern_1 = r'^[A-Z]+\d{3,4}[CP]\d+\.(SHF|DCE|CZC|INE|CFE)$'
    commodity_option_pattern_2 = r'^[A-Z]+\d{3,4}-[CP]-\d+\.(SHF|DCE|CZC|INE|CFE)$'

    # 金融期权格式：标的代码+到期年月+期权类型+行权价
    # 例如：510050C2412M02500、300ETF购12月2500（中文格式暂不支持）
    financial_option_pattern = r'^\d{6}[CP]\d{2}(0[1-9]|1[0-2])[A-Z]?\d+\.GFE$'

    processed_symbols = []
    for sym in symbols_list:
        if sym == "":  # 跳过空字符串
            processed_symbols.append(sym)
            continue

        # 去除.及之后的内容
        original_sym = sym
        # if '.' in sym:
        #     sym = sym.split('.')[0]

        # 转换为大写进行验证
        sym_upper = sym.upper()
        # 验证处理后的格式
        if not (re.match(shse_option_pattern, sym_upper) or
                re.match(szse_option_pattern, sym_upper) or
                re.match(commodity_option_pattern_1, sym_upper) or
                re.match(commodity_option_pattern_2, sym_upper) or
                re.match(financial_option_pattern, sym_upper)):

            # 检查是否是小写格式
            if re.match(r'^[a-z]+\d+[cp]\d+$', sym.lower()) or re.match(r'^[a-z]+\d+-[cp]-\d+$', sym.lower()):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，字母部分必须为大写"
                )
            # 检查是否是期权类型错误
            elif re.match(r'^[A-Z0-9]+[0-9]+$', sym_upper) and not any([
                re.match(shse_option_pattern, sym_upper),
                re.match(szse_option_pattern, sym_upper),
                re.match(commodity_option_pattern_1, sym_upper),
                re.match(commodity_option_pattern_2, sym_upper),
                re.match(financial_option_pattern, sym_upper)
            ]):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，期权类型必须为C(认购)或P(认沽)"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，"
                            f"格式应为：上交所期权(90007478.SZ)、深交所期权(90007478.SZ)、"
                            f"商品期权(如SR401C4800或i2401-C-3500)或金融期权(如510050C2412M02500)"
                )

        # 添加处理后的symbol到结果列表（保持原始大小写，但建议统一大写）
        processed_symbols.append(sym_upper)

    # 返回处理后的结果
    if isinstance(symbols, str):
        return processed_symbols[0]
    else:
        return processed_symbols


def validate_future_underlying_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """
    期货品种维度 symbol（对应 Java 侧 underlying_symbol IN）：
    允许纯大写字母/下划线品种码（如 AG、AU、VV_F），也允许合约/主力格式（规则同 validate_future_symbol_format）。
    """
    if symbols is None:
        return None

    if isinstance(symbols, str):
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    future_contract_pattern = r"^[A-Z_]+\d{4}$|^[A-Z]+\d{4}[A-Z]+$"
    dominant_contract_pattern = r"^[A-Z_]+_DOMINANT$"
    variety_pattern = r"^[A-Z_]{1,32}$"

    processed_symbols: List[str] = []
    for sym in symbols_list:
        if sym == "":
            processed_symbols.append(sym)
            continue

        original_sym = sym
        stem = sym.split(".")[0].strip().upper()
        if not stem:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，symbol 不能为空",
            )

        if re.match(future_contract_pattern, stem) or re.match(dominant_contract_pattern, stem):
            processed_symbols.append(stem)
        elif re.match(variety_pattern, stem):
            processed_symbols.append(stem)
        else:
            if re.match(r"^[a-z_]+\d{4}$", stem) or re.match(r"^[a-z]+_dominant$", stem) or re.match(
                    r"^[a-z_]{1,32}$", stem
            ):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，字母部分必须为大写",
                )
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{original_sym}，"
                        "品种码须为大写字母/下划线（如 AG），或合约/主力格式（如 AG2501、A_DOMINANT）",
            )

    if isinstance(symbols, str):
        return processed_symbols[0]
    return processed_symbols


def validate_index_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """验证指数symbol格式，支持H+五位数字.SH、六位数字.SH以及399开头的六位数字.SZ格式"""
    if symbols is None:
        return None

    if isinstance(symbols, str):
        # 如果是空字符串，直接返回
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    # 指数代码格式：H+五位数字.SH 或 六位数字.SH 或 399开头的六位数字.SZ（如H11111.SH或111111.SH或399999.SZ）
    index_pattern = r'^(H\d{5}|\d{6}|399\d{3})\.(SH|SZ)$'

    for sym in symbols_list:
        if sym == "":  # 跳过空字符串
            continue
        if not re.match(index_pattern, sym):
            if re.match(r'^(h\d{5}|\d{6}|399\d{3})\.(sh|sz|Sh|sH|Sz|sZ)$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，后缀必须为大写SH或SZ，H必须为大写"
                )
            elif re.match(r'^[A-Z]\d{5}\.SH$', sym) and not sym.startswith('H'):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，首字母必须为H"
                )
            elif re.match(r'^H\d+\.[A-Z]+$', sym) or re.match(r'^\d+\.[A-Z]+$', sym) or re.match(r'^399\d{3}\.[A-Z]+$',
                                                                                                 sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，交易所必须为SH或SZ"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，格式应为H+五位数字+.SH、六位数字+.SH或399开头的六位数字+.SZ"
                )

    return symbols


def validate_index_status(status: int, param_name: str = "status") -> int:
    """
    验证指数状态参数，仅支持 -1, 0 或 1
    """
    if status is None or status == "":
        return None

    if not isinstance(status, int):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为int类型，得到{type(status).__name__}类型"
        )

    if status not in [-1, 0, 1]:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{status}无效: 有效值为 -1, 0 或 1"
        )

    return status


def validate_industry_code_format(industry_codes: Union[str, List[str]]) -> Union[str, List[str]]:
    """验证行业代码格式，使用6位数字格式"""
    if industry_codes is None or industry_codes == "":
        return None

    if isinstance(industry_codes, str):
        # 如果是空字符串，直接返回
        if industry_codes == "":
            return industry_codes
        codes_list = [industry_codes]
    else:
        codes_list = industry_codes
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(codes_list) == 0 or all(c == "" for c in codes_list):
            return codes_list

    # 行业代码格式：6位数字
    industry_pattern = r'^\d{6}$'

    for code in codes_list:
        if code == "":  # 跳过空字符串
            continue
        if not re.match(industry_pattern, code):
            if re.match(r'^\d+$', code) and len(code) != 6:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{code}，行业代码必须为6位数字"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{code}，格式应为6位数字（如123456）"
                )

    return industry_codes


def validate_industry_level(level: Union[str, List[str]], param_name: str = "level") -> Union[str, List[str]]:
    """验证行业级别，仅支持L1, L2, L3"""
    if level is None or level == "":
        return None

    if isinstance(level, str):
        # 如果是空字符串，直接返回
        if level == "":
            return level
        levels_list = [level]
    else:
        levels_list = level
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(levels_list) == 0 or all(l == "" for l in levels_list):
            return levels_list

    # 行业级别格式：L1, L2, L3
    valid_levels = ["L1", "L2", "L3"]

    for l in levels_list:
        if l == "":  # 跳过空字符串
            continue
        if l.upper() not in valid_levels:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_INVALID,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{l}无效: 有效值为 L1, L2, L3"
            )

    return level


def validate_market(market: str, param_name: str = "market") -> str:
    """
    验证市场参数，仅支持 cn, hk, us
    """
    if market is None or market == "":
        return "cn"

    if not isinstance(market, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(market).__name__}类型"
        )

    valid_markets = ["cn", "hk", "us"]
    if market.lower() not in valid_markets:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{market}无效: 有效值为cn,hk,us"
        )

    return market.lower()


def validate_stock_status(status: int, param_name: str = "status") -> int:
    """
    验证股票状态参数，支持 -1, 0, 1
    """
    if status is None or status == "":
        return None

    if not isinstance(status, int):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为int类型，得到{type(status).__name__}类型"
        )

    if status not in [-1, 0, 1]:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{status}无效: 有效值为 -1, 0, 1"
        )

    return status


def validate_index_component(index_component: str, param_name: str = "indexComponent") -> str:
    """
    验证指数成分参数，仅支持 100, 010, 001, 000
    """
    if index_component is None or index_component == "":
        return None

    if not isinstance(index_component, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(index_component).__name__}类型"
        )

    valid_components = ["100", "010", "001", "000"]
    if index_component not in valid_components:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{index_component}无效: 有效值为 001,100,010,000"
        )

    return index_component


def validate_factor_type(factor_type: str, param_name: str = "type") -> str:
    """
    验证因子类型参数，仅支持 stock, future
    """
    if factor_type is None or factor_type == "":
        return "stock"

    if not isinstance(factor_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(factor_type).__name__}类型"
        )

    valid_types = ["stock", "future"]
    if factor_type.lower() not in valid_types:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{factor_type}无效: 有效值为 stock,future"
        )

    return factor_type.lower()


def validate_market_data_type(data_type: str, param_name: str = "type") -> str:
    """
    验证市场数据类型参数，仅支持 stock, future, index
    """
    if data_type is None or data_type == "":
        return "stock"

    if not isinstance(data_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(data_type).__name__}类型"
        )

    valid_types = ["stock", "future", "index"]
    if data_type.lower() not in valid_types:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{data_type}无效: 有效值为 stock,future,index"
        )

    return data_type.lower()


def validate_indicator(indicator: str, param_name: str = "indicator") -> str:
    """
    验证指标参数，仅支持下列指数或000985表示非列表内任何指数的成分股
    """
    if indicator is None or indicator == "":
        return None

    if not isinstance(indicator, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(indicator).__name__}类型"
        )

    valid_indicators = ['000985', '000300', '000905', '000906', '000852', '000016',
                        '000010', '000009', '399001', '399006', '000688',
                        '000916', '000909', '000910', '000911', '000912',
                        '000913', '000914', '000915', '000917', '000908',
                        '000922', 'H30269', '000015', '000821', '000824',
                        'H30526', 'H30524', '000803', '000804',
                        '000018', '000050', '000051', 'H30263', 'H30318',
                        'H30535', 'H30590', 'H30592', '000941', '000977',
                        'H30365', 'H30399', '000807', '000808', '000819',
                        '000820', 'H30523', 'H30539', 'H30596', 'H30597',
                        '000932', '000933', '000992', 'H30250', 'H30251',
                        'H30252', 'H30253', 'H30254', 'H30255', 'H30256',
                        'H30257', 'H30259', '000858', '000857', 'H30402',
                        'H30443', 'H30446', 'H30455', 'H30457', 'H30458',
                        'H30463', 'H30465', '000510', '000903', '399440',
                        'H30031', '000134', '000951', 'H30364', 'H30260',
                        '000919', '000918', 'H30356', 'H30355', 'H30271',
                        'H30272', 'H30029', '000925', 'H30362', 'H30363',
                        '000963', 'H30344', 'H30343', 'H30367', 'H30371',
                        'H30536', 'H30588', 'H30591', 'H30593', 'H30098',
                        'H30007', 'H30184', '000685', 'H30199', '399438',
                        '000950', '399967', 'H30213', 'H30214', 'H30198',
                        'H30187', 'H30015', '399417', 'H30366', 'H30166',
                        '000097'
                        # 如需拓展请在后添加
                        ]
    if indicator not in valid_indicators:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{indicator}无效: 有效值见参考文档"
        )

    return indicator


def validate_time_format(time_str: str, param_name: str = "time") -> str:
    """
    验证时间格式，格式为hh:mm，范围00:00~23:59
    """
    if time_str is None or time_str == "":
        return None

    if not isinstance(time_str, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(time_str).__name__}类型"
        )

    # 匹配hh:mm格式
    time_pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
    if not re.match(time_pattern, time_str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] {param_name}参数格式错误: {time_str}，格式应为hh:mm，范围00:00~23:59"
        )

    return time_str


def validate_time_zone(time_zone: Optional[Tuple[str, str]], param_name: str = "timeZone") -> Optional[Tuple[str, str]]:
    """
    验证时间区间参数，必须是包含两个时间字符串的元组，格式为hh:mm，范围00:00~23:59
    """
    if time_zone is None or time_zone == ():
        return None

    if not isinstance(time_zone, tuple):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为tuple类型，得到{type(time_zone).__name__}类型"
        )

    if len(time_zone) != 2:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值无效: 必须包含两个时间字符串"
        )

    # 验证每个时间字符串的格式和范围
    for i, time_str in enumerate(time_zone):
        if not isinstance(time_str, str):
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(time_str).__name__}类型"
            )

        # 使用正则表达式验证hh:mm格式，范围00:00~23:59
        time_pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
        if not re.match(time_pattern, time_str):
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] {param_name}参数格式错误: {time_str}，格式应为hh:mm，范围00:00~23:59"
            )

        # 验证时间字符串格式
        validate_time_format(time_str, f"{param_name}[{i}]")

    return time_zone


def validate_frequency(frequency: str, param_name: str = "frequency") -> str:
    """
    验证频率参数，仅支持 1m, 5m, 15m, 60m
    """
    if frequency is None or frequency == "":
        return "1m"

    if not isinstance(frequency, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(frequency).__name__}类型"
        )

    valid_frequencies = ["1m", "5m", "15m", "60m"]
    if frequency.lower() not in valid_frequencies:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{frequency}无效: 有效值为 1m,5m,15m,60m"
        )

    return frequency.lower()


def validate_index_frequency(frequency: str, param_name: str = "frequency") -> str:
    """
    验证指数频率参数，仅支持 1m
    """
    if frequency is None or frequency == "":
        return "1m"

    if not isinstance(frequency, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(frequency).__name__}类型"
        )

    valid_frequencies = ["1m"]
    if frequency.lower() not in valid_frequencies:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{frequency}无效: index数据当前仅支持1m频率"
        )

    return frequency.lower()


def validate_margin_type_value(margin_type: str, param_name: str = "margin_type") -> str:
    """
    验证margin_type参数值，仅支持stock或cash
    """
    if margin_type is None or margin_type == "":
        return None

    if not isinstance(margin_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(margin_type).__name__}类型"
        )

    valid_margin_types = ["stock", "cash"]
    if margin_type.lower() not in valid_margin_types:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{margin_type}无效: 有效值为 stock,cash"
        )

    return margin_type.lower()


def validate_stock_info_market(market: str, param_name: str = "market") -> str:
    """
    验证股票相关信息涉及的市场参数，非空时仅支持cn
    """
    if market is None or market == "":
        return "cn"

    if not isinstance(market, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(market).__name__}类型"
        )

    valid_markets = ["cn"]
    if market.lower() not in valid_markets:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{market}无效: 当前仅支持cn"
        )

    return market.lower()


def validate_stock_type(stock_type: str, param_name: str = "stockType") -> str:
    """
    验证股票类型参数，非空时仅支持flow或total
    """
    if stock_type is None or stock_type == "":
        return None

    if not isinstance(stock_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(stock_type).__name__}类型"
        )

    valid_types = ["flow", "total"]
    if stock_type.lower() not in valid_types:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{stock_type}无效: 有效值为 flow,total"
        )

    return stock_type.lower()


def validate_rank_pair(start_rank: Optional[int], end_rank: Optional[int]) -> None:
    """
    验证排名参数对，两者必须同时为正整数或同时为空，且end_rank >= start_rank
    """
    # 如果两者都为空，则合法
    if start_rank is None and end_rank is None:
        return

    # 如果其中一个为空而另一个不为空，则非法
    if start_rank is None or end_rank is None:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] 请求参数值无效：startRank和endRank必须同时提供或同时为空"
        )

    # 验证类型
    if not isinstance(start_rank, int) or not isinstance(end_rank, int):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] startRank和endRank参数类型错误：应为int类型"
        )

    # 验证是否为正整数
    if start_rank <= 0 or end_rank <= 0:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] 请求参数值无效：startRank和endRank参数值必须为正整数"
        )

    # 验证范围关系
    if end_rank < start_rank:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] 请求参数值无效：endRank({end_rank})必须大于等于startRank({start_rank})"
        )


def validate_positive_integer(value: int, param_name: str = "param") -> int:
    """
    验证参数是否为正整数
    """
    if value is None or value == "":
        return 1

    if not isinstance(value, int):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为int类型，得到{type(value).__name__}类型"
        )

    if value <= 0:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{value}无效: 必须为正整数"
        )

    return value


def validate_quarter_date_combination(
        start_quarter: Optional[str],
        end_quarter: Optional[str],
        date: Optional[str]
) -> None:
    """
    验证start_quarter、end_quarter和date参数的组合有效性
    支持以下三种情况：
    1. 三个参数均非空
    2. start_quarter，end_quarter非空，date为空
    3. date非空，start_quarter，end_quarter为空
    """
    # 检查参数是否为空（None或空字符串）
    start_quarter_empty = start_quarter is None or start_quarter == ""
    end_quarter_empty = end_quarter is None or end_quarter == ""
    date_empty = date is None or date == ""

    # 情况1：三个参数均非空
    if not start_quarter_empty and not end_quarter_empty and not date_empty:
        return

    # 情况2：start_quarter，end_quarter非空，date为空
    if not start_quarter_empty and not end_quarter_empty and date_empty:
        return

    # 情况3：date非空，start_quarter，end_quarter为空
    if date_empty and start_quarter_empty and end_quarter_empty:
        return

    # 不符合上述三种情况，抛出异常
    raise ServiceError(
        code=ServiceErrorCode.REQUEST_PARAM_INVALID,
        message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] start_quarter、end_quarter和date参数组合无效："
                f"支持的组合为 1) 三者均非空 2) start_quarter和end_quarter非空但date为空 3) date非空但start_quarter和end_quarter为空"
    )


def validate_hk_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """
    验证港股symbol格式
    合法形式包括：
    1. 4位数字.HK 如 0100.HK
    2. 5位数字以8开头.HK 如 82333.HK
    后缀必须为HK（如果是小写会转换为大写）
    """
    if symbols is None:
        return None

    if isinstance(symbols, str):
        # 如果是空字符串，直接返回
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        # 如果是空列表或只包含空字符串的列表，直接返回
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    processed_symbols = []
    for sym in symbols_list:
        if sym == "":  # 跳过空字符串
            processed_symbols.append(sym)
            continue

        # 将后缀转换为大写
        if '.' in sym:
            prefix, suffix = sym.rsplit('.', 1)
            sym_upper = f"{prefix}.{suffix.upper()}"
        else:
            sym_upper = sym

        # 验证格式
        # 4位数字.HK格式
        four_digit_pattern = r'^\d{4}\.HK$'
        # 5位数字以8开头.HK格式
        five_digit_pattern = r'^8\d{4}\.HK$'

        if not (re.match(four_digit_pattern, sym_upper) or re.match(five_digit_pattern, sym_upper)):
            # 检查是否是小写hk格式
            if re.match(r'^\d{4}\.hk$', sym) or re.match(r'^8\d{4}\.hk$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，后缀必须为大写HK"
                )
            # 检查是否是其他后缀
            elif re.match(r'^\d{4}\.\w+$', sym) or re.match(r'^8\d{4}\.\w+$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，后缀必须为HK"
                )
            # 检查是否是4位数字但以8开头的情况
            elif re.match(r'^8\d{3}\.HK$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，以8开头的港股代码必须为5位数字"
                )
            # 检查是否是5位数字但不是以8开头的情况
            elif re.match(r'^[0-79]\d{4}\.HK$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，5位数字的港股代码必须以8开头"
                )
            # 检查是否是数字位数不对
            elif re.match(r'^\d+\.\w+$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，港股代码必须为4位数字或5位数字(以8开头)"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，格式应为4位数字.HK(如0100.HK)或5位数字以8开头.HK(如82333.HK)"
                )

        # 添加处理后的symbol到结果列表
        processed_symbols.append(sym_upper)

    # 返回处理后的结果
    if isinstance(symbols, str):
        return processed_symbols[0]
    else:
        return processed_symbols


def validate_nb_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """
    验证 NB 市场 symbol 格式，如 AAPL.NB、US000001.NB，后缀为 .NB（大写）。
    """
    if symbols is None:
        return None

    if isinstance(symbols, str):
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    processed_symbols = []
    for sym in symbols_list:
        if sym == "":
            processed_symbols.append(sym)
            continue
        if "." not in sym:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，NB 市场代码须包含后缀，如 AAPL.NB",
            )
        prefix, suffix = sym.rsplit(".", 1)
        sym_norm = f"{prefix}.{suffix.upper()}"
        if suffix.upper() != "NB":
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，NB 市场后缀必须为 .NB",
            )
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9\-]{0,29}\.NB$", sym_norm):
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，NB 市场格式应为 代码.NB（如 AAPL.NB）",
            )
        processed_symbols.append(sym_norm)

    if isinstance(symbols, str):
        return processed_symbols[0]
    return processed_symbols


def validate_data_volume_limit(
        symbol: Optional[Union[str, List[str]]],
        start_date: str,
        end_date: str,
        symbol_type: str,
        time_zone: Optional[Tuple[str, str]],
        frequency: str
) -> None:
    """
    验证数据查询量限制，防止单次查询数据量过大
    """
    from datetime import datetime

    # 基础限制：5500个symbol，一个月数据，全交易时段，1m频率
    MAX_SYMBOLS_COUNT = 5500
    BASE_DAYS = 32
    BASE_FREQUENCY = "1m"

    # 计算symbol系数
    if symbol is None:
        symbol_count = MAX_SYMBOLS_COUNT  # 当symbol为空时，表示查询全部symbol
    else:
        if isinstance(symbol, str):
            symbol_list = [symbol] if symbol != "" else []
        else:
            symbol_list = [s for s in symbol if s != ""]
        symbol_count = len(symbol_list)

    # 计算symbol类型系数
    symbol_coefficient = symbol_count / MAX_SYMBOLS_COUNT
    if symbol_type.lower() == "index":
        symbol_coefficient *= 5
    elif symbol_type.lower() == "future":
        symbol_coefficient *= 6.5

    # 限制symbol系数最大为1
    symbol_coefficient = min(symbol_coefficient, 1.0)

    # 计算日期范围系数
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")
    actual_days = abs((end_dt - start_dt).days) + 1  # 包含起止日期
    date_coefficient = round(actual_days / BASE_DAYS, 1)

    # 计算time_zone系数
    time_coefficient = 1.0  # 默认为1，表示全时段
    if time_zone is not None:
        time_coefficient = calculate_time_coefficient(time_zone, symbol_type)

    # 计算频率系数
    freq_multiplier = 1.0
    if frequency.lower() == "5m":
        freq_multiplier = 6
    elif frequency.lower() == "15m":
        freq_multiplier = 12
    elif frequency.lower() == "60m":
        freq_multiplier = 60

    # 计算总系数
    total_coefficient = (symbol_coefficient * date_coefficient * time_coefficient) / freq_multiplier

    # 如果总系数大于1，抛出异常
    if round(total_coefficient, 2) > 1.0:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] 请求参数值超出范围，单次查询数据量可能过大"
        )


def calculate_time_coefficient(time_zone: Tuple[str, str], symbol_type: str) -> float:
    """
    计算time_zone时间段内有效交易时间的比例系数
    """
    from datetime import time

    start_time_str, end_time_str = time_zone
    start_hour, start_minute = map(int, start_time_str.split(':'))
    end_hour, end_minute = map(int, end_time_str.split(':'))

    start_time = time(start_hour, start_minute)
    end_time = time(end_hour, end_minute)

    # 定义有效交易时段
    if symbol_type.lower() == "future":
        # 期货交易时段：09:30-11:30, 13:00-15:00, 21:00-02:30(次日)
        trading_periods = [
            (time(9, 30), time(11, 30)),  # 上午
            (time(13, 0), time(15, 0)),  # 下午
            (time(21, 0), time(2, 30))  # 夜盘(跨天)
        ]
        total_valid_hours = 9.5  # 总共9.5小时
    else:
        # 股票/指数交易时段：09:30-11:30, 13:00-15:00
        trading_periods = [
            (time(9, 30), time(11, 30)),  # 上午
            (time(13, 0), time(15, 0))  # 下午
        ]
        total_valid_hours = 4.0  # 总共4小时

    # 计算time_zone时间段内的有效交易时间
    effective_hours = 0.0

    # 检查是否跨日
    if end_time < start_time:  # 跨日情况，如 23:00 - 02:30
        # 分两段计算：从start_time到23:59:59，从00:00到end_time
        # 第一段：start_time 到 23:59
        effective_hours += calculate_period_overlap(start_time, time(23, 59), trading_periods, cross_midnight=False)
        # 第二段：00:00 到 end_time
        effective_hours += calculate_period_overlap(time(0, 0), end_time, trading_periods, cross_midnight=True)
    else:  # 不跨日
        effective_hours = calculate_period_overlap(start_time, end_time, trading_periods, cross_midnight=False)

    # 计算比例系数，最大为1.0
    coefficient = min(effective_hours / total_valid_hours, 1.0)
    return round(coefficient, 1)


def calculate_period_overlap(period_start: time, period_end: time, trading_periods: list,
                             cross_midnight: bool = False) -> float:
    """
    计算指定时间段与交易时段的重叠时间
    """
    from datetime import time, timedelta

    total_overlap_minutes = 0

    for trade_start, trade_end in trading_periods:
        # 如果是跨日且当前交易时段也是跨日(夜盘)
        if cross_midnight and trade_end < trade_start:  # 处理跨日交易时段
            # 这种情况下需要特殊处理跨日子夜时段
            # 计算period_start到period_end(第二天)与trade_start到trade_end的交集
            overlap_minutes = calculate_cross_midnight_overlap(period_start, period_end, trade_start, trade_end)
        else:
            # 正常情况下的时间段重叠计算
            overlap_minutes = calculate_normal_overlap(period_start, period_end, trade_start, trade_end)

        total_overlap_minutes += overlap_minutes

    return total_overlap_minutes / 60.0  # 转换为小时


def calculate_normal_overlap(period_start: time, period_end: time, trade_start: time, trade_end: time) -> int:
    """
    计算两个时间段的重叠分钟数(非跨日)
    """
    # 将time转换为当天的datetime以便计算
    from datetime import datetime, timedelta
    today = datetime.today().date()

    period_start_dt = datetime.combine(today, period_start)
    period_end_dt = datetime.combine(today, period_end)
    trade_start_dt = datetime.combine(today, trade_start)
    trade_end_dt = datetime.combine(today, trade_end)

    # 如果交易时段跨天，需要特殊处理
    if trade_end < trade_start:
        # 如果当前查询时段也是跨天的，才考虑跨天交易时段
        return 0  # 在非跨日查询中，不考虑跨天交易时段

    # 计算重叠时间
    latest_start = max(period_start_dt, trade_start_dt)
    earliest_end = min(period_end_dt, trade_end_dt)

    if latest_start < earliest_end:
        overlap_duration = earliest_end - latest_start
        return int(overlap_duration.total_seconds() // 60)

    return 0


def calculate_cross_midnight_overlap(period_start: time, period_end: time, trade_start: time, trade_end: time) -> int:
    """
    计算跨日时间段的重叠分钟数
    """
    from datetime import datetime, timedelta
    today = datetime.today().date()
    tomorrow = today + timedelta(days=1)

    # period是跨日的：从period_start到第二天的period_end
    period_start_dt = datetime.combine(today, period_start)
    period_end_dt = datetime.combine(tomorrow, period_end)  # 第二天的时间

    # trade也是跨日的：从trade_start到第二天的trade_end
    trade_start_dt = datetime.combine(today, trade_start)
    trade_end_dt = datetime.combine(tomorrow, trade_end)  # 第二天的时间

    # 计算重叠时间
    latest_start = max(period_start_dt, trade_start_dt)
    earliest_end = min(period_end_dt, trade_end_dt)

    if latest_start < earliest_end:
        overlap_duration = earliest_end - latest_start
        return int(overlap_duration.total_seconds() // 60)

    return 0


def validate_max_rank(value: int, param_name: str = "max_rank") -> Optional[int]:
    """
    验证排名上限参数，必须为大于等于 1 的正整数

    Args:
        value: 待验证的整数值
        param_name: 参数名称，用于错误提示

    Returns:
        int: 验证后的值，如果输入为 None 或空则返回 None

    Raises:
        ServiceError: 当参数类型错误或值无效时抛出
    """
    if value is None or value == "":
        return None

    if not isinstance(value, int):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为 int 类型，得到{type(value).__name__}类型"
        )

    if value < 1:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{value}无效：必须为大于等于 1 的正整数"
        )

    return value


def validate_position_type(position_type: str, param_name: str = "type") -> str:
    """
    验证持仓类型参数，仅支持 long 或 short

    Args:
        position_type: 待验证的持仓方向值
        param_name: 参数名称，用于错误提示

    Returns:
        str: 验证后的小写格式值，如果输入为 None 或空则返回 None

    Raises:
        ServiceError: 当参数类型错误或值无效时抛出
    """
    if position_type is None or position_type == "":
        return None

    if not isinstance(position_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为 str 类型，得到{type(position_type).__name__}类型"
        )

    valid_types = ["long", "short"]
    if position_type.lower() not in valid_types:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{position_type}无效：有效值为 long,short"
        )

    return position_type.lower()


def validate_broker_grade(grade: Optional[str], param_name: str = "grade") -> Optional[str]:
    """
    验证 broker 等级参数，仅支持 A, B, C, D, E 五种值

    Args:
        grade: 待验证的等级值
        param_name: 参数名称，用于错误提示

    Returns:
        str: 验证后的大写格式值，如果输入为 None 或空则返回 None

    Raises:
        ServiceError: 当参数类型错误或值无效时抛出
    """
    if grade is None or grade == "":
        return None

    if not isinstance(grade, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为 str 类型，得到{type(grade).__name__}类型"
        )

    valid_grades = ["A", "B", "C", "D", "E"]
    if grade.upper() not in valid_grades:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{grade}无效：有效值为 A,B,C,D,E"
        )

    return grade.upper()


def validate_rank_type(rank_type: str, param_name: str = "rank_type") -> str:
    """
    验证排名类型参数，仅支持 ratio 或 line

    Args:
        rank_type: 待验证的排名类型值
        param_name: 参数名称，用于错误提示

    Returns:
        str: 验证后的小写格式值

    Raises:
        ServiceError: 当参数类型错误或值无效时抛出
    """
    if rank_type is None or (isinstance(rank_type, str) and not rank_type.strip()):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
        )

    if not isinstance(rank_type, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为 str 类型，得到{type(rank_type).__name__}类型"
        )

    valid_types = ["ratio", "line"]
    if rank_type.strip().lower() not in valid_types:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{rank_type}无效：有效值为 ratio,line"
        )

    return rank_type.strip().lower()


def validate_quarter_interval(start_quarter: Optional[str], end_quarter: Optional[str], max_years: int = 5) -> None:
    """
    验证季度间隔是否超过限制（默认最大5年）

    Args:
        start_quarter: 开始季度（YYYYqN格式，如2020q1）
        end_quarter: 结束季度（YYYYqN格式，如2025q1）
        max_years: 最大年数限制，默认为5年

    Raises:
        ServiceError: 当季度间隔超过限制时抛出异常
    """
    if not start_quarter or not end_quarter:
        return

    # 解析季度
    start_year = int(start_quarter[:4])
    start_q = int(start_quarter[5])

    end_year = int(end_quarter[:4])
    end_q = int(end_quarter[5])

    # 计算年份差和季度差
    year_diff = end_year - start_year
    quarter_diff = end_q - start_q

    # 计算总季度差
    total_quarters = year_diff * 4 + quarter_diff

    # 5年 = 20个季度
    max_quarters = max_years * 4

    if total_quarters > max_quarters:
        raise ServiceError(
            code=ServiceErrorCode.DATE_RANGE_INVALID,
            message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 季度范围无效: 开始季度({start_quarter})和结束季度({end_quarter})的间隔不能超过{max_years}年（{max_quarters}个季度）"
        )


def validate_company_investor_max_rank(value: Optional[int], param_name: str = "max_rank") -> int:
    """
    验证公司投资者数据排名上限参数

    - 如果为空或None，默认设置为20
    - 否则必须为小于等于20的正整数

    Args:
        value: 待验证的整数值
        param_name: 参数名称，用于错误提示

    Returns:
        int: 验证后的值，默认为20

    Raises:
        ServiceError: 当参数类型错误或值无效时抛出
    """
    if value is None or value == "":
        return 20

    if not isinstance(value, int):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为 int 类型，得到{type(value).__name__}类型"
        )

    if value < 1:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{value}无效：必须为正整数"
        )

    if value > 20:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{value}无效：不能超过20"
        )

    return value


def validate_year_format(year_str: Optional[str], param_name: str = "year") -> Optional[str]:
    """
    验证年份格式，支持YYYY格式（如2024）

    Args:
        year_str: 待验证的年份字符串
        param_name: 参数名称，用于错误提示

    Returns:
        str: 验证后的年份字符串（YYYY格式）

    Raises:
        ServiceError: 当年份格式错误或包含非法值时抛出
    """
    if year_str is None or year_str == "":
        return None

    if not isinstance(year_str, str):
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str类型，得到{type(year_str).__name__}类型"
        )

    # 验证YYYY格式
    if not re.match(r'^\d{4}$', year_str):
        raise ServiceError(
            code=ServiceErrorCode.DATE_FORMAT_ERROR,
            message=f"[错误码 {ServiceErrorCode.DATE_FORMAT_ERROR}] {param_name}格式错误: {year_str}，应为YYYY格式（如2024）"
        )

    # 验证年份合理性（1900-2100）
    year_value = int(year_str)
    if year_value < 1900 or year_value > 2100:
        raise ServiceError(
            code=ServiceErrorCode.DATE_FORMAT_ERROR,
            message=f"[错误码 {ServiceErrorCode.DATE_FORMAT_ERROR}] {param_name}格式错误: {year_str}，年份必须在1900-2100之间"
        )

    return year_str


def validate_year_range(start_year: Optional[str], end_year: Optional[str]) -> None:
    """
    验证年份范围，确保end_year >= start_year

    Args:
        start_year: 开始年份（YYYY格式）
        end_year: 结束年份（YYYY格式）

    Raises:
        ServiceError: 当年份范围无效时抛出
    """
    if start_year and end_year:
        start_val = int(start_year)
        end_val = int(end_year)
        if end_val < start_val:
            raise ServiceError(
                code=ServiceErrorCode.DATE_RANGE_INVALID,
                message=f"[错误码 {ServiceErrorCode.DATE_RANGE_INVALID}] 年份范围无效: 开始年份({start_year})不能大于结束年份({end_year})"
            )


VALID_MACRO_CATEGORIES = [
    'US', 'EU', 'JP', 'KR', 'AS', 'UK', 'FR', 'DE', 'ID', 'IT', 'ES', 'CA',
    'SZ', 'RU', 'BR', 'ZA', 'MY', 'IA', 'TU', 'TL', 'GL', 'SG', 'VN', 'KH',
    'RP', 'BN', 'LA', 'MM', 'NA', 'IN', 'CI', 'PI', 'FA', 'FI', 'MB', 'IR',
    'FE', 'DT', 'EW', 'LI', 'PR', 'SE', 'SM', 'PM', 'EC', 'MD', 'EH', 'AD',
    'HA', 'OF', 'RB', 'RE', 'ED', 'EP', 'AR', 'CM', 'OR', 'AG', 'EN', 'CH',
    'ST', 'NF', 'BM', 'AU', 'ME', 'EE', 'TM', 'FB', 'TE', 'PP', 'PH', 'UT',
    'TR', 'RC', 'TH', 'CE', 'WR', 'FS', 'IS'
]


def validate_macro_category(category: Union[str, List[str]], param_name: str = "category") -> List[str]:
    """
    验证宏观经济分类参数

    Args:
        category: 分类代码，支持str或List[str]
        param_name: 参数名称，用于错误提示

    Returns:
        List[str]: 验证后的分类列表

    Raises:
        ServiceError: 当参数类型错误或值无效时抛出
    """
    if category is None:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
        )

    if isinstance(category, str):
        if not category.strip():
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
            )
        category_list = [category.strip().upper()]
    elif isinstance(category, list):
        if len(category) == 0:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
            )
        # 过滤空字符串并转为大写
        category_list = [str(c).strip().upper() for c in category if c and str(c).strip()]
        if len(category_list) == 0:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_EMPTY,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_EMPTY}] {param_name}参数不能为空"
            )
    else:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR}] {param_name}参数类型错误：应为str或List[str]类型，得到{type(category).__name__}类型"
        )

    # 验证每个category是否在合法列表中
    invalid_categories = [cat for cat in category_list if cat not in VALID_MACRO_CATEGORIES]
    if invalid_categories:
        raise ServiceError(
            code=ServiceErrorCode.REQUEST_PARAM_INVALID,
            message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] {param_name}参数值{invalid_categories}无效：有效值见参考文档"
        )

    return category_list


def validate_macro_symbol_format(symbols: Union[str, List[str]]) -> Union[str, List[str]]:
    """
    验证宏观经济symbol格式
    合法形式：前2位为合法的category代码 + 10位数字
    例如：IS0000000111, US1234567890

    Args:
        symbols: symbol代码，支持str或List[str]

    Returns:
        Union[str, List[str]]: 验证后的symbol

    Raises:
        ServiceError: 当symbol格式错误时抛出
    """
    if symbols is None:
        return None

    if isinstance(symbols, str):
        if symbols == "":
            return symbols
        symbols_list = [symbols]
    else:
        symbols_list = symbols
        if len(symbols_list) == 0 or all(s == "" for s in symbols_list):
            return symbols

    # symbol格式：2位category + 7位数字
    macro_symbol_pattern = r'^[A-Z]{2}\d{7}$'

    processed_symbols = []
    for sym in symbols_list:
        if sym == "":
            processed_symbols.append(sym)
            continue

        # 转换为大写进行验证
        sym_upper = sym.upper()

        if not re.match(macro_symbol_pattern, sym_upper):
            # 检查是否是长度问题
            if re.match(r'^[A-Z]{2}\d+$', sym_upper):
                digit_part = sym_upper[2:]
                if len(digit_part) != 10:
                    raise ServiceError(
                        code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                        message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，symbol格式应为2位字母+10位数字（如IS0000000111），当前数字部分长度为{len(digit_part)}"
                    )
            # 检查是否是字母部分问题
            elif re.match(r'^[A-Z]+\d{10}$', sym_upper):
                letter_part = sym_upper[:2] if len(sym_upper) > 2 else sym_upper
                if len(letter_part) != 2:
                    raise ServiceError(
                        code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                        message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，symbol格式应为2位字母+10位数字（如IS0000000111），当前字母部分长度为{len(letter_part)}"
                    )
            # 检查是否是小写格式
            elif re.match(r'^[a-z]{2}\d{10}$', sym):
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，字母部分必须为大写"
                )
            else:
                raise ServiceError(
                    code=ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR,
                    message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR}] 请求参数格式错误: 错误的参数值{sym}，格式应为2位字母+10位数字（如IS0000000111）"
                )

        # 验证前2位是否为合法的category
        prefix = sym_upper[:2]
        if prefix not in VALID_MACRO_CATEGORIES:
            raise ServiceError(
                code=ServiceErrorCode.REQUEST_PARAM_INVALID,
                message=f"[错误码 {ServiceErrorCode.REQUEST_PARAM_INVALID}] 请求参数值无效: 错误的参数值{sym}，前缀{prefix}不是有效的category代码"
            )

        processed_symbols.append(sym_upper)

    if isinstance(symbols, str):
        return processed_symbols[0]
    else:
        return processed_symbols