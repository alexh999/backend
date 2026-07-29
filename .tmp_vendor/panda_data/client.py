from __future__ import annotations

import os
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, Iterable, Optional, Type, TypeVar
from urllib.parse import urlparse

import pandas as pd


# 模块级函数，用于多进程处理（必须定义在类外部）
def _build_dataframe_chunk(chunk_data):
    """在子进程中构建 DataFrame（模块级函数，可被多进程序列化）"""
    return pd.DataFrame(chunk_data)


from panda_data.config import get_config
from panda_data.exceptions import ServiceError
from panda_data.transport.http import (
    HTTPClient,
    HTTPClientConfig,
)
from panda_data.utils.common_utils import find_project_root


@dataclass(frozen=True)
class ClientConfig:
    base_url: str  # HTTP base URL, 例如: "http://localhost:8080"
    username: str = field(default="")
    password: str = field(default="")
    timeout: float = 30.0
    retry: int = 3
    verify_ssl: bool = True
    proxy_type: Optional[str] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    use_gzip: bool = False
    data_field: Iterable[str] | None = field(default_factory=lambda: ("data",))
    abnormal_endpoint: str = field(default="/abnormal")


def _extract_nested(data: Any, path: Optional[Iterable[str]]) -> Any:
    """Utility to extract a nested value from a dictionary-like payload."""
    if data is None or path is None:
        return data

    # 如果 data 是列表，说明可能是流式响应直接返回的数据列表
    # 这种情况下，直接返回列表，不进行嵌套提取
    if isinstance(data, list):
        return data

    # 确保 current 是字典类型
    if not isinstance(data, dict):
        # 如果不是字典也不是列表，可能是其他类型，直接返回
        return data

    current = data
    # 检查错误码（只有当 current 是字典时才检查）
    if isinstance(current, dict):
        code = current.get("code")
        if code is not None and code != 200 and code != '200':
            raise ServiceError(f"服务返回错误:[错误码 {code} ：{current.get('message', '未知错误')}]")

    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


class PandaServiceClient:
    """Client responsible for communicating with the Java service via HTTP."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        http_config = HTTPClientConfig(
            base_url=config.base_url,
            username=config.username,
            password=config.password,
            timeout=config.timeout,
            max_retries=config.retry,
            verify_ssl=config.verify_ssl,
            proxy_type=config.proxy_type,
            proxy_host=config.proxy_host,
            proxy_port=config.proxy_port,
            proxy_username=config.proxy_username,
            proxy_password=config.proxy_password,
            use_gzip=config.use_gzip,
        )
        self._http_client = HTTPClient(http_config)

    @property
    def config(self) -> ClientConfig:
        return self._config

    # Gateway 返回的业务错误码（HTTP 200 + body 中 code ≠ 200）
    _TOKEN_EXPIRED_CODES = frozenset(("200002", "200004"))

    def request(
            self,
            *,
            endpoint: str,
            payload: Optional[Dict[str, Any]] = None,
            method: str = "POST",
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            data_path: Optional[Iterable[str]] = None,
    ) -> Any:
        result = self._http_client.request(
            method=method,
            endpoint=endpoint,
            payload=payload,
            params=params,
            headers=headers,
        )
        try:
            data = _extract_nested(result, data_path or self._config.data_field)
        except ServiceError as e:
            # Gateway 返回业务层 token 过期错误（HTTP 200 + code 200002/200004）
            # → 尝试自动 relogin 后重试一次
            msg = str(e)
            if any(c in msg for c in self._TOKEN_EXPIRED_CODES):
                from panda_data.auth_manager import re_login as _relogin
                if _relogin():
                    # 重试：更新 token 后重新发送
                    result = self._http_client.request(
                        method=method,
                        endpoint=endpoint,
                        payload=payload,
                        params=params,
                        headers=headers,
                    )
                    data = _extract_nested(result, data_path or self._config.data_field)
                else:
                    raise
            else:
                raise
        return data

    def fetch_dataframe(
            self,
            *,
            endpoint: str,
            payload: Optional[Dict[str, Any]] = None,
            method: str = "POST",
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            data_path: Optional[Iterable[str]] = None,
    ) -> pd.DataFrame:
        data = self.request(
            endpoint=endpoint,
            payload=payload,
            method=method,
            params=params,
            headers=headers,
            data_path=data_path,
        )

        if data is None:
            return pd.DataFrame()

        # 检查是否直接是 DataFrame（Parquet 返回的情况，经过 _extract_nested 后）
        if isinstance(data, pd.DataFrame):
            return data

        # 检查是否是 Parquet 格式返回的 DataFrame（特殊标记）
        if isinstance(data, dict) and "__dataframe__" in data:
            return data["__dataframe__"]

        if isinstance(data, dict):
            # 如果数据是字典，检查是否有 'data' 字段
            if 'data' in data:
                # 检查 data 字段是否是 DataFrame（Parquet 返回的情况）
                if isinstance(data['data'], pd.DataFrame):
                    return data['data']
                elif isinstance(data['data'], list):
                    # 如果 data 字段是列表，直接使用它
                    data_list = data['data']
                else:
                    # 其他类型，转换为列表
                    data_list = [data['data']]
            else:
                # 否则将整个字典作为一行
                data_list = [data]
        elif isinstance(data, (list, tuple)):
            data_list = data
        else:
            raise ServiceError(
                f"Unexpected payload format returned by the service. Type: {type(data)}, Value: {str(data)[:200]}")

        # 对于大数据量，使用分块处理以避免内存峰值和提升性能
        if len(data_list) > 100000:  # 超过 10 万条记录时使用分块处理
            total_rows = len(data_list)
            chunk_size = 100000  # 增大块大小到 10 万条，减少合并次数

            # 对于超大数据量，使用优化的单进程分块处理
            # 注意：多进程的数据序列化开销很大，对于 Python 对象列表，单进程可能更快
            # 如果未来需要多进程，建议使用共享内存或 Arrow 格式
            chunks = []
            for i in range(0, total_rows, chunk_size):
                chunk_end = min(i + chunk_size, total_rows)
                chunk = data_list[i:chunk_end]
                df_chunk = pd.DataFrame(chunk)
                chunks.append(df_chunk)
            if chunks:
                df = pd.concat(chunks, ignore_index=True)
                del chunks
                import gc
                gc.collect()
            else:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame(data_list)
        return df

    def close(self) -> None:
        self._http_client.close()


ReaderT = TypeVar("ReaderT")


class ClientFactory:
    """Factory responsible for creating readers bound to a shared client instance."""

    def __init__(self, client: PandaServiceClient) -> None:
        self._client = client
        self._instances: Dict[Type[Any], Any] = {}
        self._lock = Lock()

    @property
    def client(self) -> PandaServiceClient:
        return self._client

    def get_reader(self, reader_cls: Type[ReaderT]) -> ReaderT:
        with self._lock:
            if reader_cls not in self._instances:
                self._instances[reader_cls] = reader_cls(self._client)
            return self._instances[reader_cls]


_factory: Optional[ClientFactory] = None
_factory_lock = Lock()


def _parse_address(address: str) -> tuple:
    """解析地址字符串为(host, port)"""
    # 支持格式: "host:port", "tcp://host:port", "host"
    if "://" in address:
        parsed = urlparse(address)
        host = parsed.hostname or parsed.path.split(":")[0]
        port = parsed.port or (int(parsed.path.split(":")[-1]) if ":" in parsed.path else 8080)
    elif ":" in address:
        parts = address.rsplit(":", 1)
        host = parts[0]
        port = int(parts[1])
    else:
        host = address
        port = 8080  # 默认端口

    if not host:
        raise ServiceError(f"Invalid address format: {address}")

    return host, port


def init(
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        base_url: Optional[str] = None,  # HTTP base URL, 例如: "http://localhost:8080"
        address: Optional[str] = None,  # 兼容旧接口，格式: "host:port" 或 "http://host:port"
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        verify_ssl: Optional[bool] = None,
        proxy_type: Optional[str] = None,
        proxy_host: Optional[str] = None,
        proxy_port: Optional[int] = None,
        proxy_username: Optional[str] = None,
        proxy_password: Optional[str] = None,
        use_gzip: Optional[bool] = None,
        data_field: Optional[Iterable[str]] = None,
        abnormal_endpoint: Optional[str] = None,
) -> PandaServiceClient:
    """
    初始化客户端。需先调用 init_token() 登录后使用。
    """
    global _factory
    service_config = get_config()

    if not username:
        username = service_config.get("DEFAULT_USERNAME", "")
    if not password:
        password = service_config.get("DEFAULT_PASSWORD", "")

    # 解析 base_url
    if base_url:
        http_base_url = base_url
    elif address:
        # 兼容旧的 address 格式
        if address.startswith("http://") or address.startswith("https://"):
            http_base_url = address
        else:
            # 格式: "host:port" 或 "tcp://host:port"
            parsed_host, parsed_port = _parse_address(address)
            http_base_url = f"http://{parsed_host}:{parsed_port}"
    else:
        # 从配置中获取
        http_base_url = (
                service_config.get("HTTP_SERVICE_BASE_URL")
                or service_config.get("JAVA_SERVICE_BASE_URL")
        )
        if http_base_url:
            # 如果配置中没有协议，添加 http://
            if not http_base_url.startswith(("http://", "https://")):
                parsed_host, parsed_port = _parse_address(http_base_url)
                http_base_url = f"http://{parsed_host}:{parsed_port}"
        else:
            http_base_url = "http://localhost:8080"

    config_kwargs: Dict[str, Any] = {
        "base_url": http_base_url + "/pandaData",
        "username": username,
        "password": password,
        "timeout": timeout or float(
            service_config.get("HTTP_TIMEOUT") or service_config.get("JAVA_SERVICE_TIMEOUT", 30.0)),
        "retry": max_retries
        if max_retries is not None
        else int(service_config.get("HTTP_MAX_RETRIES") or service_config.get("JAVA_SERVICE_MAX_RETRIES", 3)),
        "verify_ssl": (
            verify_ssl
            if verify_ssl is not None
            else service_config.get("HTTP_VERIFY_SSL",
                                    service_config.get("JAVA_SERVICE_VERIFY_SSL", "true")).lower() in {"true", "1",
                                                                                                       "yes"}
        ),
        "proxy_type": proxy_type or service_config.get("HTTP_PROXY_TYPE"),
        "proxy_host": proxy_host or service_config.get("HTTP_PROXY_HOST"),
        "proxy_port": (
            proxy_port
            if proxy_port is not None
            else (
                int(service_config["HTTP_PROXY_PORT"])
                if service_config.get("HTTP_PROXY_PORT")
                else None
            )
        ),
        "proxy_username": proxy_username or service_config.get("HTTP_PROXY_USERNAME"),
        "proxy_password": proxy_password or service_config.get("HTTP_PROXY_PASSWORD"),
        "use_gzip": (
            use_gzip
            if use_gzip is not None
            else service_config.get("HTTP_USE_GZIP", "false").lower() in {"true", "1", "yes"}
        ),
        "data_field": data_field
        if data_field is not None
        else _parse_data_field(service_config.get("HTTP_DATA_FIELD") or service_config.get("JAVA_SERVICE_DATA_FIELD")),
        "abnormal_endpoint": abnormal_endpoint
                             or service_config.get("HTTP_ABNORMAL_ENDPOINT")
                             or service_config.get("JAVA_SERVICE_ABNORMAL_ENDPOINT", "/abnormal"),
    }

    client_config = ClientConfig(**config_kwargs)
    client = PandaServiceClient(client_config)

    with _factory_lock:
        _factory = ClientFactory(client)

    return client


def get_factory(base_url: Optional[str] = None) -> ClientFactory:
    global _factory
    if _factory is None:
        # 尝试从磁盘中保存的加密凭据自动登录
        from panda_data.auth_manager import auto_login_from_disk, get_decrypted_credentials, \
            get_base_url as _auth_base_url
        if auto_login_from_disk():
            creds = get_decrypted_credentials()
            if creds:
                init(
                    username=creds.get("username", ""),
                    password=creds.get("password", ""),
                    base_url=creds.get("base_url") or _auth_base_url(),
                )
        if _factory is None:
            from panda_data.exceptions import ClientNotInitializedError
            raise ClientNotInitializedError(
                "客户端未初始化，请先调用 panda_data.init_token() 进行登录！"
            )
    return _factory


def get_client(base_url: Optional[str] = None) -> PandaServiceClient:
    return get_factory(base_url).client


def _parse_data_field(raw: Optional[str]) -> Optional[Iterable[str]]:
    if not raw:
        return None
    parts = [segment.strip() for segment in raw.split(".") if segment.strip()]
    return tuple(parts) if parts else None
