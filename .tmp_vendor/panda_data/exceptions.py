from __future__ import annotations

from enum import IntEnum
from typing import Optional, Union


class PandaDataError(Exception):
    """Base exception for the panda_data SDK."""


class ClientNotInitializedError(PandaDataError):
    """Raised when attempting to use the SDK without calling init."""

    def __init__(self, message: Optional[str] = None) -> None:
        default_message = (
            "panda_data client is not initialized. Call panda_data.init(...) first."
        )
        super().__init__(message or default_message)


class AuthenticationError(PandaDataError):
    """Raised when authentication with the remote service fails."""


class ServiceErrorCode(IntEnum):
    # 客户端请求错误
    REQUEST_PARAM_ERROR = 100000  # 请求参数错误
    REQUEST_PARAM_EMPTY = 100001  # 请求参数不能为空
    REQUEST_PARAM_FORMAT_ERROR = 100002  # 请求参数值格式错误
    REQUEST_PARAM_TYPE_ERROR = 100003  # 请求参数类型错误
    REQUEST_PARAM_OUT_OF_RANGE = 100004  # 请求参数值超出范围
    REQUEST_PARAM_DUPLICATED = 100005  # 请求参数值中存在重复
    REQUEST_PARAM_INVALID = 100006  # 请求参数值无效
    DATE_FORMAT_ERROR = 100007  # 日期格式错误
    DATE_RANGE_INVALID = 100008  # 日期范围无效

    # 认证相关错误
    AUTHENTICATION_FAILED = 200001  # 认证失败
    TOKEN_INVALID_OR_EXPIRED = 200002  # 未登录或登录已过期
    TOKEN_FORMAT_ERROR = 200003  # Token格式错误
    TOKEN_EXPIRED = 200004  # Token已过期
    USERNAME_OR_PASSWORD_ERROR = 200005  # 用户名或密码错误
    USER_NOT_EXISTS = 200006  # 用户未注册
    USER_DISABLED = 200007  # 用户已被禁用

    # 权限相关错误
    RESOURCE_ACCESS_DENIED = 200101  # 无权限访问该资源
    OPERATION_ACCESS_DENIED = 200102  # 无权限执行该操作
    API_ACCESS_DENIED = 200103  # API访问权限不足
    DATA_ACCESS_DENIED = 200104  # 数据访问权限受限

    # 业务逻辑错误
    BUSINESS_ERROR = 400001  # 业务逻辑异常
    DATA_QUERY_TIMEOUT = 400002  # 数据查询超时

    # 限流熔断错误
    REQUEST_FREQUENCY_LIMIT = 500001  # 请求频率超限
    HOTSPOT_PARAM_LIMIT = 500002  # 热点参数限流
    IP_REQUEST_FREQUENCY_LIMIT = 500003  # IP请求频率超限
    SERVICE_DEGRADED = 500004  # 服务降级中
    SERVICE_CIRCUIT_BREAKER = 500005  # 服务熔断中
    CONCURRENT_REQUEST_LIMIT = 500006  # 并发请求数超限

    # 数据查询错误
    DATA_QUERY_FAILED = 600001  # 数据查询失败
    QUERY_RESULT_TOO_LARGE = 600002  # 查询结果集过大

    # 系统异常
    RC500 = 900001  # 系统异常，请稍后重试


class ServiceError(PandaDataError):
    """Raised when the remote service returns an error or an invalid response."""

    ERROR_MESSAGES = {
        ServiceErrorCode.REQUEST_PARAM_ERROR: "请求参数错误",
        ServiceErrorCode.REQUEST_PARAM_EMPTY: "请求参数不能为空",
        ServiceErrorCode.REQUEST_PARAM_FORMAT_ERROR: "请求参数值格式错误",
        ServiceErrorCode.REQUEST_PARAM_TYPE_ERROR: "请求参数类型错误",
        ServiceErrorCode.REQUEST_PARAM_OUT_OF_RANGE: "请求参数值超出范围",
        ServiceErrorCode.REQUEST_PARAM_DUPLICATED: "请求参数值中存在重复",
        ServiceErrorCode.REQUEST_PARAM_INVALID: "请求参数值无效",
        ServiceErrorCode.DATE_FORMAT_ERROR: "日期格式错误",
        ServiceErrorCode.DATE_RANGE_INVALID: "日期范围无效",

        ServiceErrorCode.AUTHENTICATION_FAILED: "认证失败",
        ServiceErrorCode.TOKEN_INVALID_OR_EXPIRED: "未登录或登录已过期",
        ServiceErrorCode.TOKEN_FORMAT_ERROR: "Token格式错误",
        ServiceErrorCode.TOKEN_EXPIRED: "Token已过期",
        ServiceErrorCode.USERNAME_OR_PASSWORD_ERROR: "用户名或密码错误",
        ServiceErrorCode.USER_NOT_EXISTS: "用户未注册",
        ServiceErrorCode.USER_DISABLED: "用户已被禁用",

        ServiceErrorCode.RESOURCE_ACCESS_DENIED: "无权限访问该资源",
        ServiceErrorCode.OPERATION_ACCESS_DENIED: "无权限执行该操作",
        ServiceErrorCode.API_ACCESS_DENIED: "API访问权限不足",
        ServiceErrorCode.DATA_ACCESS_DENIED: "数据访问权限受限",

        ServiceErrorCode.BUSINESS_ERROR: "业务逻辑异常",
        ServiceErrorCode.DATA_QUERY_TIMEOUT: "数据查询超时",

        ServiceErrorCode.REQUEST_FREQUENCY_LIMIT: "请求频率超限",
        ServiceErrorCode.HOTSPOT_PARAM_LIMIT: "热点参数限流",
        ServiceErrorCode.IP_REQUEST_FREQUENCY_LIMIT: "IP请求频率超限",
        ServiceErrorCode.SERVICE_DEGRADED: "服务降级中",
        ServiceErrorCode.SERVICE_CIRCUIT_BREAKER: "服务熔断中",
        ServiceErrorCode.CONCURRENT_REQUEST_LIMIT: "并发请求数超限",

        ServiceErrorCode.DATA_QUERY_FAILED: "数据查询失败",
        ServiceErrorCode.QUERY_RESULT_TOO_LARGE: "查询结果集过大",

        ServiceErrorCode.RC500: "系统异常，请稍后重试",
    }

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[Union[ServiceErrorCode, int]] = None,
    ) -> None:
        self.code: Optional[int] = None
        if code is not None:
            code_enum: Optional[ServiceErrorCode]
            try:
                code_enum = (
                    code
                    if isinstance(code, ServiceErrorCode)
                    else ServiceErrorCode(int(code))
                )
            except ValueError:
                code_enum = None

            if code_enum is not None:
                self.code = int(code_enum)
                message = message or self.ERROR_MESSAGES[code_enum]
            else:
                self.code = int(code)
                message = message or f"Service returned error code {self.code}"

        super().__init__(message or "Service error occurred.")
