from __future__ import annotations

import atexit
import base64
import gzip
import io
import json
import os
import ssl
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from urllib.request import (
    Request,
    urlopen,
    HTTPError,
    build_opener,
    ProxyHandler,
    HTTPBasicAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    HTTPSHandler,
)
from urllib.error import URLError
import http.client

# 尝试导入 zstd 库
try:
    import zstandard as zstd

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

# 尝试导入 DuckDB（用于读取 Parquet 文件）
try:
    import duckdb

    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    duckdb = None

from panda_data.exceptions import ServiceError
from panda_data.utils.common_utils import find_project_root
from panda_data.auth_manager import (
    get_token as _auth_get_token,
    get_token_ttl as _auth_get_ttl,
    auto_login_from_disk as _auth_auto_login,
    re_login as _auth_re_login,
    is_authenticated as _auth_is_authenticated,
    is_token_near_expiry as _auth_is_near_expiry,
)

# 全局变量：跟踪当前正在读取 Parquet 的并发数（用于多线程内存管理）
# 注意：这里限制的是多个HTTP请求线程同时调用接口读取Parquet的数量（应用层并发）
#       不是DuckDB内部读取Parquet时使用的线程数（数据库引擎层并行）
_parquet_read_lock = threading.Lock()
_active_parquet_reads = 0


# 根据系统内存动态计算最大并发数，但设置合理上限
def _get_max_concurrent_parquet_reads():
    """
    根据系统内存计算最大并发读取数

    这个函数返回的是：同时有多少个HTTP请求线程可以读取Parquet文件
    例如：返回8表示最多8个HTTP请求可以同时读取Parquet

    Returns:
        int: 最大并发HTTP请求数（不是DuckDB内部线程数）
    """
    try:
        import psutil
        total_memory_gb = psutil.virtual_memory().total / (1024 ** 3)
        # 根据总内存计算：每16GB内存允许1个并发HTTP请求读取Parquet，但最少2个，最多8个
        max_concurrent = max(2, min(8, int(total_memory_gb / 16)))
        return max_concurrent
    except Exception:
        # 如果无法获取内存信息，使用默认值4
        return 4


# 使用信号量限制最大并发HTTP请求数（限制同时有多少个请求在读取Parquet）
_parquet_read_semaphore = threading.Semaphore(_get_max_concurrent_parquet_reads())


@dataclass(frozen=True)
class HTTPClientConfig:
    """HTTP客户端配置"""
    base_url: str  # 例如: "http://localhost:8080"
    username: str = ""
    password: str = ""
    timeout: float = 30.0
    max_retries: int = 3
    verify_ssl: bool = True
    proxy_type: Optional[str] = None  # "http", "https", "socks5"
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    use_gzip: bool = False  # 是否使用 gzip 压缩请求体


class HTTPClient:
    """HTTP客户端，使用标准库 urllib"""

    def __init__(self, config: HTTPClientConfig) -> None:
        self._config = config
        self._opener = self._build_opener()
        # TCP持久连接监控相关
        self._monitor_connection: Optional[http.client.HTTPConnection] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._connection_lock = threading.Lock()
        self._token_file_path: Optional[str] = None
        # 注册退出时清理函数
        atexit.register(self._cleanup_on_exit)

    def _build_opener(self):
        """构建 urllib opener，支持代理、认证和 SSL 验证"""
        handlers = []

        # SSL 验证处理
        if not self._config.verify_ssl:
            # 创建不验证 SSL 证书的上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            handlers.append(HTTPSHandler(context=ssl_context))
        else:
            # 使用默认的 SSL 上下文（验证证书）
            handlers.append(HTTPSHandler())

        # 代理支持（仅支持 HTTP/HTTPS 代理，不支持 SOCKS5）
        if self._config.proxy_type and self._config.proxy_host and self._config.proxy_port:
            if self._config.proxy_type == "socks5":
                raise ServiceError(
                    "SOCKS5 proxy is not supported by urllib. "
                    "Please use HTTP or HTTPS proxy, or install a library like requests."
                )
            proxy_url = self._build_proxy_url()
            handlers.append(ProxyHandler({self._config.proxy_type: proxy_url}))

        # HTTP 基本认证（如果需要）
        if self._config.username or self._config.password:
            password_mgr = HTTPPasswordMgrWithDefaultRealm()
            parsed_url = urlparse(self._config.base_url)
            password_mgr.add_password(
                None,
                f"{parsed_url.scheme}://{parsed_url.netloc}",
                self._config.username,
                self._config.password,
            )
            handlers.append(HTTPBasicAuthHandler(password_mgr))

        return build_opener(*handlers)

    def _build_proxy_url(self) -> str:
        """构建代理 URL"""
        proxy_url = f"{self._config.proxy_type}://"
        if self._config.proxy_username and self._config.proxy_password:
            proxy_url += f"{self._config.proxy_username}:{self._config.proxy_password}@"
        proxy_url += f"{self._config.proxy_host}:{self._config.proxy_port}"
        return proxy_url

    def _get_token_file_path(self) -> Optional[str]:
        """获取token文件路径"""
        if self._token_file_path:
            return self._token_file_path
        try:
            project_root = find_project_root(os.path.dirname(__file__))
            self._token_file_path = os.path.join(project_root, "user.json")
            return self._token_file_path
        except Exception:
            return None

    def _delete_token_file(self) -> None:
        """删除token文件"""
        token_file = self._get_token_file_path()
        if token_file and os.path.exists(token_file):
            try:
                os.remove(token_file)
            except Exception:
                pass  # 忽略删除失败的情况

    def _establish_monitor_connection(self) -> bool:
        """建立TCP监控连接"""
        try:
            parsed_url = urlparse(self._config.base_url)
            host = parsed_url.hostname or "localhost"
            port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)

            with self._connection_lock:
                if self._monitor_connection:
                    try:
                        self._monitor_connection.close()
                    except Exception:
                        pass

                if parsed_url.scheme == "https":
                    context = None
                    if not self._config.verify_ssl:
                        context = ssl.create_default_context()
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                    self._monitor_connection = http.client.HTTPSConnection(
                        host, port, timeout=self._config.timeout, context=context
                    )
                else:
                    self._monitor_connection = http.client.HTTPConnection(
                        host, port, timeout=self._config.timeout
                    )

                # 建立连接（发送一个HEAD请求来建立TCP连接）
                self._monitor_connection.connect()
                return True
        except Exception:
            return False

    def _monitor_connection_thread(self) -> None:
        """监控TCP连接状态的线程。

        仅负责检测 TCP 连接的存活状态；不再干预 token 生命周期。
        Token 管理由 auth_manager 统一负责（过期、刷新、磁盘持久化等）。
        """
        check_interval = 10  # 每10秒检查一次
        consecutive_failures = 0
        max_failures = 3  # 连续3次失败才认为连接断开

        while not self._stop_monitoring.is_set():
            try:
                # 等待检查间隔
                if self._stop_monitoring.wait(timeout=check_interval):
                    break

                with self._connection_lock:
                    if not self._monitor_connection:
                        # 尝试重新建立连接
                        if not self._establish_monitor_connection():
                            consecutive_failures += 1
                            if consecutive_failures >= max_failures:
                                break
                        else:
                            consecutive_failures = 0
                        continue

                    # 检查连接是否存活
                    try:
                        # 发送一个简单的HEAD请求来检查连接
                        self._monitor_connection.request("HEAD", "/")
                        response = self._monitor_connection.getresponse()
                        response.read()  # 读取响应以清理连接
                        consecutive_failures = 0
                    except (socket.error, OSError, http.client.HTTPException, BrokenPipeError, ConnectionResetError):
                        # 连接断开
                        consecutive_failures += 1
                        if consecutive_failures >= max_failures:
                            # 清理连接
                            try:
                                self._monitor_connection.close()
                            except Exception:
                                pass
                            self._monitor_connection = None
                            break  # 连接断开，退出监控
                    except Exception:
                        # 其他异常，也视为连接问题
                        consecutive_failures += 1
                        if consecutive_failures >= max_failures:
                            try:
                                self._monitor_connection.close()
                            except Exception:
                                pass
                            self._monitor_connection = None
                            break

            except Exception:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    break

    def start_connection_monitoring(self) -> None:
        """启动TCP连接监控（仅当用户已登录时）。"""
        if not _auth_is_authenticated():
            return

        # 建立监控连接
        if not self._establish_monitor_connection():
            return

        # 启动监控线程
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_monitoring.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_connection_thread,
                daemon=True,
                name="TCPConnectionMonitor"
            )
            self._monitor_thread.start()

    def _cleanup_on_exit(self) -> None:
        """程序退出时的清理工作。

        进程退出（IDE 重启/关机）时删除 user.json，重新启动需重新登录。
        同进程内的连接中断、token 过期等由 auth_manager 自动恢复。
        """
        # 停止监控线程
        self._stop_monitoring.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

        # 关闭监控连接
        with self._connection_lock:
            if self._monitor_connection:
                try:
                    self._monitor_connection.close()
                except Exception:
                    pass
                self._monitor_connection = None

        # 进程退出时清除 user.json — 重启需重新登录
        self._delete_token_file()

    def _build_headers(
            self,
            method: str,
            content_type: str = "application/json",
            additional_headers: Optional[Dict[str, str]] = None,
            endpoint: str = ""
    ) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": content_type,
            "Accept": "application/json",
        }

        # 基本认证（HTTP Basic Auth 仅用于登录接口，数据接口使用 token）
        if self._config.username or self._config.password:
            auth_str = f"{self._config.username}:{self._config.password}"
            auth_bytes = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {auth_bytes}"

        # 压缩支持（gzip 和 zstd）
        # 对于流式接口，默认支持 zstd 压缩（即使库未安装，也告知服务端我们支持）
        accept_encodings = []
        if self._config.use_gzip:
            accept_encodings.append("gzip")
        # 默认添加 zstd 支持（服务端可能使用流式压缩）
        accept_encodings.append("zstd")
        if accept_encodings:
            headers["Accept-Encoding"] = ", ".join(accept_encodings)

        # Token 鉴权（登录接口本身不需要 token）
        if endpoint and "login" not in endpoint:
            token = _auth_get_token()
            if token is None:
                # 尝试从磁盘中保存的加密凭据自动登录
                if _auth_auto_login():
                    token = _auth_get_token()
            if token is None:
                raise ServiceError(
                    "未登录或登录已过期，请调用 panda_data.init_token() 进行登录！"
                )
            headers["Authorization"] = token
            # 主动刷新：距过期不足 30min 且不足 TTL 一半时触发
            # 短 TTL token（如 60s）不会每次请求都刷新
            threshold = min(1800.0, _auth_get_ttl() * 0.5) if _auth_get_ttl() > 0 else 1800.0
            if _auth_is_near_expiry(threshold_seconds=max(threshold, 30.0)):
                _auth_re_login()
                new_token = _auth_get_token()
                if new_token:
                    headers["Authorization"] = new_token
            # 启动TCP连接监控（如果尚未启动）
            if self._monitor_thread is None or not self._monitor_thread.is_alive():
                self.start_connection_monitoring()

        # 添加额外的请求头
        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _prepare_request_body(self, data: Optional[Dict[str, Any]]) -> Optional[bytes]:
        """准备请求体"""
        if data is None:
            return None

        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

        # Gzip 压缩
        if self._config.use_gzip:
            body = gzip.compress(body)

        return body

    def _decode_content(self, content: bytes, content_type: str = "") -> str:
        """
        解码响应内容，支持多种编码

        Args:
            content: 要解码的字节内容
            content_type: Content-Type 头，可能包含 charset 信息

        Returns:
            解码后的字符串

        Raises:
            ServiceError: 如果所有编码尝试都失败
        """
        # 尝试从 Content-Type 头获取字符集
        charset = None
        if content_type and "charset=" in content_type:
            try:
                charset = content_type.split("charset=")[1].split(";")[0].strip().lower()
            except Exception:
                pass

        # 尝试解码响应内容，支持多种编码
        encodings_to_try = []

        # 如果 Content-Type 指定了字符集，优先使用
        if charset:
            encodings_to_try.append(charset)

        # 添加常用编码
        encodings_to_try.extend(["utf-8", "gbk", "gb2312", "gb18030", "latin1"])

        # 去重并保持顺序
        seen = set()
        encodings_to_try = [enc for enc in encodings_to_try if enc not in seen and not seen.add(enc)]

        decode_error = None
        for encoding in encodings_to_try:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError as e:
                decode_error = e
                continue

        raise ServiceError(
            f"Failed to decode response content. Tried encodings: {', '.join(encodings_to_try)}. "
            f"Last error: {decode_error}"
        )

    def _decompress_content(self, content: bytes, content_encoding: str) -> bytes:
        """
        根据 Content-Encoding 头解压缩响应内容
        支持流式压缩（边压缩边传输的数据）

        Args:
            content: 压缩的字节内容
            content_encoding: Content-Encoding 头的值

        Returns:
            解压缩后的字节内容
        """
        if not content_encoding:
            return content

        content_encoding_lower = content_encoding.lower()

        try:
            if content_encoding_lower == "gzip":
                decompressed = gzip.decompress(content)
            elif content_encoding_lower in ("zstd", "z-standard"):
                if not HAS_ZSTD:
                    raise ServiceError(
                        "Response is compressed with zstd, but zstandard library is not installed. "
                        "Please install it with: pip install zstandard"
                    )
                try:
                    # 优化：使用更高效的解压器配置
                    # 对于大文件，使用更大的窗口大小可以提高性能
                    dctx = zstd.ZstdDecompressor()

                    # 优化：优先使用直接解压（更快），如果失败再尝试流式解压
                    # 直接解压通常比流式解压快 2-3 倍，且内存占用更少
                    try:
                        # 方法1：直接解压（最快，适用于完整数据）
                        # 对于大多数情况，即使数据是流式压缩的，完整接收后也可以直接解压
                        decompressed = dctx.decompress(content)
                    except Exception:
                        # 方法2：如果直接解压失败，使用流式解压（适用于流式压缩数据）
                        # 使用更大的缓冲区可以提高流式解压的性能
                        decompressor = dctx.stream_reader(io.BytesIO(content), read_size=1024 * 1024)  # 1MB 缓冲区
                        decompressed = decompressor.read()
                        decompressor.close()
                        if not decompressed:
                            # 如果流式解压返回空，再次尝试直接解压
                            decompressed = dctx.decompress(content)
                except Exception as e:
                    raise ServiceError(
                        f"Failed to decompress zstd content: {e}. "
                        f"This might be a streaming compression issue. "
                        f"Please ensure zstandard library is properly installed: pip install zstandard"
                    ) from e
            else:
                # 未知的压缩格式，返回原始内容
                decompressed = content

            return decompressed
        except ServiceError:
            raise
        except Exception as e:
            raise

    def _stream_to_temp_file(self, response, content_encoding: str, tmp_file_path: str) -> int:
        """
        将 HTTP 响应流式解压写入临时文件，避免全量数据同时驻留内存。
        大内存机器受益于更快的 I/O 吞吐；小内存机器（如 8GB）
        因不将全量解压数据加载到内存而避免 OOM。

        Returns:
            写入文件的总字节数
        """
        _CHUNK = 512 * 1024
        total_written = 0
        encoding = content_encoding.lower() if content_encoding else ""

        with open(tmp_file_path, 'wb') as out:
            if encoding in ("zstd", "z-standard"):
                if not HAS_ZSTD:
                    raise ServiceError(
                        "Response is compressed with zstd, but zstandard library is not installed. "
                        "Please install it with: pip install zstandard"
                    )
                dctx = zstd.ZstdDecompressor()
                reader = dctx.stream_reader(response, read_size=_CHUNK)
                try:
                    while True:
                        chunk = reader.read(_CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
                        total_written += len(chunk)
                finally:
                    reader.close()
            elif encoding == "gzip":
                import zlib
                decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
                while True:
                    compressed_chunk = response.read(_CHUNK)
                    if not compressed_chunk:
                        break
                    decompressed = decompressor.decompress(compressed_chunk)
                    if decompressed:
                        out.write(decompressed)
                        total_written += len(decompressed)
                remaining = decompressor.flush()
                if remaining:
                    out.write(remaining)
                    total_written += len(remaining)
            else:
                while True:
                    chunk = response.read(_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    total_written += len(chunk)

        return total_written

    @staticmethod
    def _parquet_col_ci(columns: List[str], name: str) -> Optional[str]:
        """按不区分大小写匹配列名，返回 Parquet/DuckDB 中的实际列名。"""
        nl = name.lower()
        for c in columns:
            if c.lower() == nl:
                return c
        return None

    def _infer_parquet_columns(self, conn, tmp_file_path: str) -> List[str]:
        """读取 Parquet 列名：优先用 pyarrow 仅读 footer 元数据（最快且保持物理列序），
        失败时再回退到 DuckDB LIMIT 1 / DESCRIBE。"""
        try:
            import pyarrow.parquet as pq
            return list(pq.read_schema(tmp_file_path).names)
        except Exception:
            pass
        try:
            sample_result = conn.execute(
                f"SELECT * FROM read_parquet('{tmp_file_path}') LIMIT 1"
            )
            return list(sample_result.df().columns)
        except Exception:
            pass
        try:
            import pyarrow.parquet as pq

            return list(pq.read_schema(tmp_file_path).names)
        except Exception:
            pass
        try:
            desc = conn.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{tmp_file_path}')"
            ).df()
            return desc.iloc[:, 0].astype(str).tolist()
        except Exception:
            pass
        return []

    def _parse_response(self, response, endpoint: str = "") -> Dict[str, Any]:
        """解析响应，支持标准JSON、流式响应（NDJSON格式）和Parquet格式"""
        content_encoding = response.headers.get("Content-Encoding", "")
        content_type = response.headers.get("Content-Type", "")

        # 已知返回 Parquet 格式的接口关键词
        _parquet_ep_kws = (
            "getmultimarketmindata", "getfuturetickdata", "getfinancialstatementdata",
            "getstockmarkethkdata", "getstockmarkethkmindata",
            "getstockmarkethkprecaldata", "getstockmarkethkpostcaldata",
            "getstockmarketusdata", "getstockmarketusmindata",
            "getstockmarketusprecaldata", "getstockmarketuspostcaldata",
            "getfunddailydata", "getfunddetaildata",
            "getfunddailypostdata", "getfunddailypredata",
            "getfundetfcrdata", "getfundetfconstituentsdata",
            "getfundetfcrnetdata", "getfundetfcrlimitsdata",
        )
        endpoint_lower = endpoint.lower()
        is_known_parquet_ep = (
                "parquet" in content_type.lower()
                or "application/x-parquet" in content_type.lower()
                or any(kw in endpoint_lower for kw in _parquet_ep_kws)
        )

        # 对于已知 Parquet 接口，流式写入临时文件以避免全量数据驻留内存
        _streamed_tmp_path = None
        _streamed_size_mb = 0.0
        if is_known_parquet_ep:
            import tempfile
            import os
            _tmp_fd, _streamed_tmp_path = tempfile.mkstemp(suffix='.parquet')
            os.close(_tmp_fd)
            try:
                _total_written = self._stream_to_temp_file(
                    response, content_encoding, _streamed_tmp_path
                )
            except Exception as _e:
                try:
                    os.remove(_streamed_tmp_path)
                except Exception:
                    pass
                raise ServiceError(f"流式写入临时文件失败: {_e}") from _e
            # 验证文件确实是 Parquet 格式（检查 "PAR1" 魔数）
            _is_valid_parquet = False
            if _total_written >= 4:
                with open(_streamed_tmp_path, 'rb') as _f:
                    _is_valid_parquet = _f.read(4) == b"PAR1"
            if _is_valid_parquet:
                _streamed_size_mb = _total_written / (1024 * 1024)
                content = None
            else:
                # 非 Parquet（可能是 JSON 错误响应），回退到内存解析
                with open(_streamed_tmp_path, 'rb') as _f:
                    content = _f.read()
                try:
                    os.remove(_streamed_tmp_path)
                except Exception:
                    pass
                _streamed_tmp_path = None
        else:
            content = response.read()
            content = self._decompress_content(content, content_encoding)

        # 非流式路径：通过文件魔数检测是否为 Parquet
        is_parquet_by_content = False
        if content is not None and len(content) >= 4:
            is_parquet_by_content = content[:4] == b"PAR1"

        is_parquet = (_streamed_tmp_path is not None) or is_parquet_by_content

        # 如果是 Parquet 格式，使用 DuckDB 读取
        if is_parquet:
            if not HAS_DUCKDB or duckdb is None:
                if _streamed_tmp_path:
                    try:
                        os.remove(_streamed_tmp_path)
                    except Exception:
                        pass
                raise ServiceError(
                    "响应是 Parquet 格式，但 DuckDB 库未安装。"
                    "请安装: pip install duckdb"
                )

            global _active_parquet_reads
            try:
                import tempfile

                if _streamed_tmp_path is not None:
                    tmp_file_path = _streamed_tmp_path
                    file_size_mb = _streamed_size_mb
                else:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.parquet') as tmp_file:
                        tmp_file.write(content)
                        tmp_file_path = tmp_file.name
                    file_size_mb = len(content) / 1024 / 1024
                    del content

                _parquet_read_semaphore.acquire()

                with _parquet_read_lock:
                    _active_parquet_reads += 1
                    current_concurrency = _active_parquet_reads

                try:
                    # 使用 DuckDB 读取 Parquet 文件
                    conn = duckdb.connect()
                    try:
                        try:
                            import psutil
                            HAS_PSUTIL = True
                        except ImportError:
                            HAS_PSUTIL = False
                            psutil = None

                        if HAS_PSUTIL and psutil is not None:
                            try:
                                available_memory_gb = psutil.virtual_memory().available / (1024 ** 3)
                                total_memory_gb = psutil.virtual_memory().total / (1024 ** 3)
                            except Exception:
                                available_memory_gb = 4.0
                                total_memory_gb = 8.0
                        else:
                            available_memory_gb = 4.0
                            total_memory_gb = 8.0

                        cpu_count = os.cpu_count() or 4
                        effective_concurrency = max(current_concurrency, 1)

                        # Parquet 展开后通常是文件大小的 5~15 倍，排序还需要额外临时空间
                        estimated_expanded_gb = file_size_mb * 10 / 1024
                        estimated_need_gb = max(estimated_expanded_gb * 2.5, 1.0)

                        # 根据总内存渐进式分配 DuckDB 内存预算：
                        #   ≤8GB  → 20%（配合 temp_directory 溢写磁盘防 OOM）
                        #   8~16GB → 20%~40% 线性过渡（平衡速度与安全）
                        #   >16GB → 积极分配（充分利用内存提升速度）
                        if total_memory_gb <= 8:
                            per_conn_budget_gb = total_memory_gb * 0.20 / effective_concurrency
                        elif total_memory_gb <= 16:
                            _ratio = 0.20 + (total_memory_gb - 8) / 8 * 0.20
                            per_conn_budget_gb = total_memory_gb * _ratio / effective_concurrency
                        else:
                            per_conn_budget_gb = max(
                                total_memory_gb * 0.5,
                                available_memory_gb * 0.9,
                            ) / effective_concurrency
                        cap_ratio = float(os.environ.get("PANDA_DATA_DUCKDB_MEMORY_CAP_RATIO", "0.65"))
                        per_conn_budget_gb = min(
                            per_conn_budget_gb,
                            total_memory_gb * cap_ratio / effective_concurrency,
                        )
                        memory_limit_gb = min(estimated_need_gb, per_conn_budget_gb)
                        memory_limit_gb = max(memory_limit_gb, 0.5)

                        env_mem = os.environ.get("PANDA_DATA_DUCKDB_MEMORY_GB", "").strip()
                        if env_mem:
                            try:
                                memory_limit_gb = max(0.5, float(env_mem))
                            except ValueError:
                                pass

                        memory_limit = f"{memory_limit_gb:.1f}GB"

                        # 线程：内存过小时少开线程；避免 available=4 时 int(4/4)=1 单核跑满
                        env_thr = os.environ.get("PANDA_DATA_DUCKDB_THREADS", "").strip()
                        if env_thr:
                            try:
                                num_threads = max(1, min(cpu_count, int(env_thr)))
                            except ValueError:
                                num_threads = min(
                                    cpu_count,
                                    max(2, min(16, int(memory_limit_gb // 1.2))),
                                )
                        else:
                            num_threads = min(
                                cpu_count,
                                max(2, min(16, int(memory_limit_gb // 1.2))),
                            )
                        num_threads = max(1, num_threads)

                        conn.execute(f"SET threads TO {num_threads}")
                        conn.execute(f"SET memory_limit='{memory_limit}'")
                        conn.execute("SET enable_object_cache TO true")
                        conn.execute("SET enable_progress_bar TO false")
                        conn.execute("SET preserve_insertion_order TO false")
                        _td = tempfile.gettempdir()
                        conn.execute(f"SET temp_directory='{_td}'")
                    except Exception as config_error:
                        num_threads = 1
                        memory_limit = "512MB"
                        try:
                            conn.execute("SET threads TO 1")
                            conn.execute("SET memory_limit='512MB'")
                            conn.execute("SET enable_object_cache TO false")
                            conn.execute("SET enable_progress_bar TO false")
                            conn.execute("SET preserve_insertion_order TO false")
                            try:
                                _td = tempfile.gettempdir()
                                conn.execute(f"SET temp_directory='{_td}'")
                            except Exception:
                                pass
                        except Exception:
                            pass

                    # 读取列信息（LIMIT 1 失败时用 pyarrow schema 兜底，避免无 ORDER BY 时保持 Parquet 物理顺序）
                    available_columns = self._infer_parquet_columns(conn, tmp_file_path)

                    # 构建查询语句
                    # 判断 endpoint 类型并设置排序和列选择逻辑（列名大小写不敏感，ORDER BY 使用实际列名）
                    if "getfuturetickdata" in endpoint.lower():
                        # tick 数据：服务端已按 symbol+timestamp 排序，客户端不再 ORDER BY（省掉千万级行全局排序）。
                        # 仅做列顺序调整：将 symbol, date, timestamp 放到前三列。
                        sym_col = self._parquet_col_ci(available_columns, "symbol")
                        ts_col = self._parquet_col_ci(available_columns, "timestamp")
                        date_col = self._parquet_col_ci(available_columns, "date")

                        order_by_clause = ""

                        if sym_col and date_col and ts_col:
                            other_columns = [
                                col
                                for col in available_columns
                                if col not in (sym_col, date_col, ts_col)
                            ]
                            select_columns = [sym_col, date_col, ts_col] + other_columns
                            select_clause = ", ".join([f'"{col}"' for col in select_columns])
                        elif sym_col and date_col:
                            other_columns = [
                                col for col in available_columns if col not in (sym_col, date_col)
                            ]
                            select_columns = [sym_col, date_col] + other_columns
                            select_clause = ", ".join([f'"{col}"' for col in select_columns])
                        elif sym_col:
                            other_columns = [col for col in available_columns if col != sym_col]
                            select_columns = [sym_col] + other_columns
                            select_clause = ", ".join([f'"{col}"' for col in select_columns])
                        else:
                            select_clause = "*"
                    else:
                        # 默认：日频/分钟等行情——优先 symbol，再 date / minute 降序
                        sym_col = self._parquet_col_ci(available_columns, "symbol")
                        date_col = self._parquet_col_ci(available_columns, "date")
                        min_col = self._parquet_col_ci(available_columns, "minute")

                        order_by_clause = ""
                        if sym_col and date_col and min_col:
                            order_by_clause = (
                                f' ORDER BY "{sym_col}" ASC, "{date_col}" DESC, "{min_col}" DESC'
                            )
                        elif sym_col and date_col:
                            order_by_clause = f' ORDER BY "{sym_col}" ASC, "{date_col}" DESC'
                        elif sym_col:
                            order_by_clause = f' ORDER BY "{sym_col}" ASC'
                        elif date_col and min_col:
                            order_by_clause = f' ORDER BY "{date_col}" DESC, "{min_col}" DESC'
                        elif date_col:
                            order_by_clause = f' ORDER BY "{date_col}" DESC'
                        elif min_col:
                            order_by_clause = f' ORDER BY "{min_col}" DESC'

                        if sym_col and date_col:
                            other_columns = [
                                col for col in available_columns if col not in (sym_col, date_col)
                            ]
                            select_columns = [sym_col, date_col] + other_columns
                            select_clause = ", ".join([f'"{col}"' for col in select_columns])
                        elif sym_col:
                            other_columns = [col for col in available_columns if col != sym_col]
                            select_columns = [sym_col] + other_columns
                            select_clause = ", ".join([f'"{col}"' for col in select_columns])
                        elif date_col:
                            other_columns = [col for col in available_columns if col != date_col]
                            select_columns = [date_col] + other_columns
                            select_clause = ", ".join([f'"{col}"' for col in select_columns])
                        else:
                            select_clause = "*"

                    # 执行主查询
                    query = f"SELECT {select_clause} FROM read_parquet('{tmp_file_path}'){order_by_clause}"

                    try:
                        import pyarrow as pa
                        HAS_PYARROW = True
                    except ImportError:
                        HAS_PYARROW = False
                        pa = None

                    if HAS_PYARROW:
                        result = conn.execute(query)
                        try:
                            arrow_result = result.arrow()
                            if isinstance(arrow_result, pa.Table):
                                # self_destruct=True：转换时释放底层 arrow 缓冲区，降低峰值内存
                                df = arrow_result.to_pandas(self_destruct=True)
                            elif isinstance(arrow_result, pa.RecordBatchReader):
                                df = arrow_result.read_all().to_pandas(self_destruct=True)
                            elif hasattr(arrow_result, "to_pandas"):
                                df = arrow_result.to_pandas(self_destruct=True)
                            else:
                                raise TypeError(f"unexpected arrow result type: {type(arrow_result)}")
                        except Exception:
                            result = conn.execute(query)
                            df = result.df()
                    else:
                        df = conn.execute(query).df()

                    # 确保df已正确赋值
                    if df is None:
                        raise ServiceError("Failed to convert query result to DataFrame")

                    conn.close()

                    # 清理临时文件
                    try:
                        if os.path.exists(tmp_file_path):
                            os.remove(tmp_file_path)
                    except Exception as e:
                        # 清理失败不影响主流程，只记录错误
                        pass

                    result = {"__dataframe__": df, "data": df}
                    return result
                except Exception as e:
                    with _parquet_read_lock:
                        _active_parquet_reads = max(0, _active_parquet_reads - 1)
                    try:
                        _parquet_read_semaphore.release()
                    except Exception:
                        pass
                    # 如果是文件太小的错误，返回空DataFrame
                    if "too small to be a Parquet file" in str(e):
                        import pandas as pd
                        empty_df = pd.DataFrame()  # 创建空 DataFrame
                        return {"__dataframe__": empty_df, "data": empty_df}
                    else:
                        raise ServiceError(f"Failed to read Parquet file: {e}") from e
            finally:
                with _parquet_read_lock:
                    _active_parquet_reads = max(0, _active_parquet_reads - 1)
                _parquet_read_semaphore.release()

        # 解码响应内容
        decoded_content = self._decode_content(content, content_type)
        decoded_size_mb = len(decoded_content) / 1024 / 1024

        # JSON 解析（标准库）
        try:
            result = json.loads(decoded_content)
            return result
        except (json.JSONDecodeError, ValueError):
            # 如果标准 JSON 解析失败，尝试流式响应（NDJSON 格式）
            try:
                decoded_size_mb = len(decoded_content) / 1024 / 1024
                if decoded_size_mb > 100:
                    line_count = decoded_content.count('\n') + (
                        1 if decoded_content and not decoded_content.endswith('\n') else 0)
                    import io
                    lines_iter = io.StringIO(decoded_content)
                    lines = None
                    use_iterator = True
                else:
                    lines = decoded_content.strip().split('\n')
                    line_count = len(lines)
                    use_iterator = False
                if line_count > 100000:
                    json_objects = []
                    chunk_size = 100000
                    if use_iterator:
                        current_chunk = []
                        chunk_index = 0
                        processed_count = 0
                        for line in lines_iter:
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith('data: '):
                                line = line[6:]
                            if line.startswith(('event:', 'id:', 'retry:')):
                                continue
                            current_chunk.append(line)
                            processed_count += 1
                            if len(current_chunk) >= chunk_size:
                                chunk_lines = current_chunk
                                current_chunk = []
                                chunk_objects = []
                                for chunk_line in chunk_lines:
                                    try:
                                        obj = json.loads(chunk_line)
                                        chunk_objects.append(obj)
                                    except (json.JSONDecodeError, ValueError, TypeError):
                                        continue
                                json_objects.extend(chunk_objects)
                                del chunk_lines, chunk_objects
                                chunk_index += 1
                                if chunk_index % 20 == 0:
                                    import gc
                                    gc.collect()
                        if current_chunk:
                            chunk_objects = []
                            for chunk_line in current_chunk:
                                try:
                                    obj = json.loads(chunk_line)
                                    chunk_objects.append(obj)
                                except (json.JSONDecodeError, ValueError, TypeError):
                                    continue
                            json_objects.extend(chunk_objects)
                            del current_chunk, chunk_objects
                    else:
                        for chunk_start in range(0, line_count, chunk_size):
                            chunk_end = min(chunk_start + chunk_size, line_count)
                            chunk_lines = lines[chunk_start:chunk_end]
                            valid_lines = []
                            for line in chunk_lines:
                                line = line.strip()
                                if not line:
                                    continue
                                if line.startswith('data: '):
                                    line = line[6:]
                                if line.startswith(('event:', 'id:', 'retry:')):
                                    continue
                                valid_lines.append(line)
                            chunk_objects = []
                            for line in valid_lines:
                                try:
                                    obj = json.loads(line)
                                    chunk_objects.append(obj)
                                except (json.JSONDecodeError, ValueError, TypeError):
                                    continue
                            json_objects.extend(chunk_objects)
                            del chunk_lines, valid_lines, chunk_objects
                            if chunk_start % (chunk_size * 2) == 0:
                                import gc
                                gc.collect()
                else:
                    json_objects = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith('data: '):
                            line = line[6:]
                        if line.startswith(('event:', 'id:', 'retry:')):
                            continue
                        try:
                            obj = json.loads(line)
                            json_objects.append(obj)
                        except (json.JSONDecodeError, ValueError):
                            continue
                if json_objects:
                    if len(json_objects) == 1:
                        obj = json_objects[0]
                        if isinstance(obj, dict):
                            return obj
                        else:
                            return {'data': obj}
                    else:
                        if all(isinstance(obj, dict) and 'data' in obj for obj in json_objects):
                            merged_data = []
                            for obj in json_objects:
                                if isinstance(obj.get('data'), list):
                                    merged_data.extend(obj['data'])
                                else:
                                    merged_data.append(obj['data'])
                            result = json_objects[0].copy()
                            result['data'] = merged_data
                            return result
                        else:
                            return {'data': json_objects}
                raise ValueError(
                    f"No valid JSON objects found in streaming response. "
                    f"Content preview (first 500 chars): {decoded_content[:500]}"
                )
            except Exception as e:
                # 如果流式响应也失败，则返回空 DataFrame
                import pandas as pd
                empty_df = pd.DataFrame()  # 创建空 DataFrame
                return {"__dataframe__": empty_df, "data": empty_df}

    def request(
            self,
            method: str,
            endpoint: str,
            payload: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE 等）
            endpoint: 端点路径（如 "/abnormal"）
            payload: 请求体数据（字典）
            params: URL 查询参数
            headers: 额外的请求头
            timeout: 超时时间（秒）

        Returns:
            响应数据（字典）
        """
        # 构建完整 URL
        url = urljoin(self._config.base_url.rstrip("/") + "/", endpoint.lstrip("/"))

        # 添加查询参数
        if params:
            from urllib.parse import urlencode
            query_string = urlencode(params)
            url = f"{url}?{query_string}" if "?" not in url else f"{url}&{query_string}"

        # 准备请求体和请求头
        request_body = None
        content_type = "application/json"
        if method.upper() in ("POST", "PUT", "PATCH"):
            request_body = self._prepare_request_body(payload)
            if self._config.use_gzip and request_body:
                content_type = "application/json; charset=utf-8"

        request_headers = self._build_headers(method, content_type, headers, endpoint)

        # 如果是 GET 或 DELETE，且 payload 不为空，将其转换为查询参数
        if method.upper() in ("GET", "DELETE") and payload:
            from urllib.parse import urlencode
            query_string = urlencode(payload)
            url = f"{url}?{query_string}" if "?" not in url else f"{url}&{query_string}"

        # 创建请求对象
        request = Request(url, data=request_body, headers=request_headers, method=method.upper())

        # 重试逻辑
        retries = max(1, self._config.max_retries)
        last_error: Optional[Exception] = None
        timeout_value = timeout or self._config.timeout

        # 对于流式接口，自动增加超时时间
        # 识别流式接口的关键词
        streaming_keywords = ['min', 'stream', 'flow', 'getmultimarketmindata']
        if timeout is None and any(keyword in endpoint.lower() for keyword in streaming_keywords):
            # 流式接口可能需要更长的处理时间，自动增加到 5 分钟（300秒）
            # 但如果用户已经指定了 timeout，则使用用户指定的值
            timeout_value = max(timeout_value, 5000.0)

        for attempt in range(retries):
            try:
                response = self._opener.open(request, timeout=timeout_value)
                return self._parse_response(response, endpoint)

            except HTTPError as e:
                # HTTP 错误（4xx, 5xx）
                error_body = None
                error_msg = str(e)
                try:
                    error_content = e.read()
                    content_type = e.headers.get("Content-Type", "") if hasattr(e, 'headers') else ""
                    error_body = self._decode_content(error_content, content_type)
                    try:
                        error_data = json.loads(error_body)
                        error_msg = error_data.get("error", error_data.get("message", error_data.get("msg", str(e))))
                    except (json.JSONDecodeError, ValueError):
                        # 如果不是 JSON，使用原始内容
                        error_msg = error_body[:500] if error_body else str(e)
                except Exception as ex:
                    # 如果读取错误响应失败，使用默认错误信息
                    error_msg = f"{str(e)} (无法读取错误详情: {ex})"

                if 400 <= e.code < 500:
                    # 客户端错误（4xx）
                    # 401 — token 可能已过期，尝试自动重新登录后重试（指数退避）
                    if e.code == 401:
                        re_logged_in = False
                        for backoff_attempt in range(2):  # 最多重试 2 次（指数退避）
                            re_logged_in = _auth_re_login()
                            if re_logged_in:
                                break
                            if backoff_attempt < 1:
                                wait_s = 1.0 * (2 ** backoff_attempt)  # 1s, 2s
                                time.sleep(wait_s)
                        if re_logged_in:
                            new_token = _auth_get_token()
                            if new_token:
                                request_headers["Authorization"] = new_token
                                request = Request(
                                    url, data=request_body,
                                    headers=request_headers,
                                    method=method.upper()
                                )
                                try:
                                    response = self._opener.open(request, timeout=timeout_value)
                                    return self._parse_response(response, endpoint)
                                except Exception:
                                    pass  # 重试失败，继续抛出原始错误
                    raise ServiceError(f"HTTP {e.code}: {error_msg}") from e
                else:
                    # 服务器错误，可以重试
                    # 对于 500 错误，提供更详细的提示
                    if e.code == 500:
                        hint = ""
                        # 检查是否是流式接口（可能处理时间较长）
                        if endpoint and any(keyword in endpoint.lower() for keyword in ['min', 'stream', 'flow']):
                            hint = f" 提示：这可能是流式接口，处理时间可能较长。当前超时设置为 {timeout_value} 秒。"
                            hint += " 如果数据量较大，建议增加超时时间（通过 timeout 参数或配置）。"
                        error_msg = f"{error_msg}{hint}"

                    last_error = ServiceError(f"HTTP {e.code}: {error_msg}")
                    if attempt == retries - 1:
                        raise last_error
                    # 服务器错误重试前等待更长时间
                    wait_time = min(1.0 * (attempt + 1), 5.0)
                    time.sleep(wait_time)

            except URLError as e:
                # 网络错误，可以重试
                last_error = ServiceError(f"Network error: {e.reason}")
                if attempt == retries - 1:
                    raise last_error
                time.sleep(min(0.1 * (attempt + 1), 1.0))

            except Exception as e:
                # 其他错误，不重试
                raise ServiceError(f"Unexpected error: {e}") from e

        if last_error is not None:
            raise last_error

        raise ServiceError("Request failed after retries")

    def call(
            self,
            endpoint: str,
            payload: Optional[Dict[str, Any]] = None,
            timeout: Optional[float] = None,
    ) -> Any:
        """
        调用 HTTP POST 端点

        Args:
            endpoint: 端点路径（如 "/abnormal"）
            payload: 请求负载（字典）
            timeout: 超时时间（秒）

        Returns:
            响应数据
        """
        # 所有数据获取接口都使用 POST 方法
        response = self.request(
            method="POST",
            endpoint=endpoint,
            payload=payload,
            timeout=timeout,
        )

        # 返回响应数据
        return response.get("data", response)

    def close(self) -> None:
        """关闭客户端，清理 TCP 监控线程、连接资源和 user.json。

        进程退出时调用，重启后需重新 init_token 登录。
        """
        self._cleanup_on_exit()

