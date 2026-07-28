from __future__ import annotations

import base64
import json
import time
from hashlib import md5
from typing import Optional
from urllib.parse import urljoin

from panda_data.config import get_config
from panda_data.exceptions import ServiceError
from panda_data.utils.common_utils import build_endpoint
from panda_data.client import init as init_client
from panda_data.transport.http import HTTPClient, HTTPClientConfig

config = get_config()
USERNAME = config.get("DEFAULT_USERNAME")
PASSWORD = config.get("DEFAULT_PASSWORD")
BASE_URL = config.get("JAVA_SERVICE_BASE_URL")


def _service_http_base(base_url: str) -> str:
    u = base_url.rstrip("/")
    for context_path in ("/pandaDataTick", "/pandaData"):
        if u.endswith(context_path):
            return u[: -len(context_path)]
    return u


def _login_http_base(base_url: str, tick_user: bool = False) -> str:
    """登录 HTTP 基地址；tick 用户走 /pandaDataTick，普通用户走 /pandaData。"""
    u = _service_http_base(base_url)
    return f"{u}/pandaDataTick" if tick_user else f"{u}/pandaData"


def _resolve_login_endpoint(
    cfg: dict,
    user_endpoint: Optional[str],
    login_path: Optional[str],
    tick_user: bool,
) -> str:
    if user_endpoint is None:
        if tick_user:
            user_endpoint = cfg.get("JAVA_SERVICE_TICK_USER_ENDPOINT", "/tickUser")
        else:
            user_endpoint = cfg.get("JAVA_SERVICE_USER_ENDPOINT", "/dataUser")

    if login_path is None:
        if tick_user:
            login_path = cfg.get("JAVA_SERVICE_TICK_USER_PATH_LOGIN", "/login")
        else:
            login_path = cfg.get("JAVA_SERVICE_USER_PATH_LOGIN", "/login")

    return build_endpoint(user_endpoint, login_path)


def init_token(
    username: Optional[str] = USERNAME,
    password: Optional[str] = PASSWORD,
    base_url: Optional[str] = BASE_URL,
    user_endpoint: Optional[str] = None,
    login_path: Optional[str] = None,
    tick_user: bool = False,
) -> str:
    """登录并保存 token。

    默认登录 `/pandaData/dataUser/login`；当 `tick_user=True` 时改为 `/pandaDataTick/tickUser/login`。
    也可通过 `user_endpoint` / `login_path` 显式覆盖登录路由。
    """
    # 检查用户名和密码是否为空
    if not username or not password or not base_url:
        raise ServiceError("username / password / base_url 不能为空")

    cfg = get_config()
    endpoint = _resolve_login_endpoint(
        cfg=cfg,
        user_endpoint=user_endpoint,
        login_path=login_path,
        tick_user=tick_user,
    )
    login_base_url = _login_http_base(base_url, tick_user=tick_user)
    full_login_url = urljoin(login_base_url.rstrip("/") + "/", endpoint.lstrip("/"))

    # 直接使用HTTPClient发送登录请求（登录接口不需要token，只需要用户名密码）
    http_config = HTTPClientConfig(
        base_url=login_base_url,
        username=username,
        password=password,
    )
    http_client = HTTPClient(http_config)

    # 构造请求载荷
    payload = {
        "username": username,
        "password": md5(password.encode('utf-8')).hexdigest()
    }

    # 发送登录请求
    try:
        raw_response = http_client.request(
            method="POST",
            endpoint=endpoint,
            payload=payload
        )

        # 检查响应是否包含错误码
        if isinstance(raw_response, dict) and raw_response.get("code") not in ["200", 200]:
            # 提取错误码和消息
            error_code = raw_response.get("code")
            error_message = raw_response.get("message", "未知错误")
            raise ServiceError(f"[错误码 {error_code} : {error_message}]")

        # 提取token：可能是字符串，也可能在data字段中
        # 新版响应格式: {code, data: {token, expires_in}} 或旧版: {code, data: "<token>"}
        result = None
        expires_in = 14400  # 默认 4 小时
        if isinstance(raw_response, str):
            result = raw_response
        elif isinstance(raw_response, dict):
            # 尝试从data字段提取
            if "data" in raw_response:
                data_val = raw_response["data"]
                if isinstance(data_val, dict):
                    result = data_val.get("token", "")
                    expires_in = int(data_val.get("expires_in", 14400))
                elif isinstance(data_val, str):
                    result = data_val
                else:
                    result = str(data_val) if data_val else ""
            elif "token" in raw_response:
                result = raw_response["token"]
            else:
                # 如果整个响应就是token（某些情况下）
                result = raw_response
    except ServiceError as e:
        msg = str(e)
        # 仅 HTTP 层的 404（urllib），避免与业务体 [错误码 404 ...] 混淆
        if msg.startswith("HTTP 404"):
            msg = (
                f"{msg}\n"
                f"登录请求 URL: {full_login_url}\n"
                f"若 404：该 base_url 端口上可能没有注册 POST {endpoint}（例如仅挂了 WebSocket）；"
                "请换为实际提供登录的 HTTP 网关地址，或通过 tick_user / user_endpoint / "
                "login_path 或环境变量调整登录路径。"
            )
        raise ServiceError(msg) from e
    except Exception as e:
        raise ServiceError(f"登录失败: {e}（请求 URL: {full_login_url}）") from e
    finally:
        http_client.close()

    # 确保result是字符串
    if isinstance(result, dict):
        # 如果还是dict，尝试转换为字符串或提取值
        result = str(result)
    if not result or not isinstance(result, str):
        raise ServiceError("登录失败：无法获取有效的token")

    # 从 JWT 的 exp 字段提取实际 TTL（覆盖默认值，与服务端一致）
    try:
        parts = result.split(".")
        if len(parts) == 3:
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            jwt_payload = json.loads(base64.b64decode(payload_b64))
            exp = jwt_payload.get("exp", 0)
            if exp > 0:
                expires_in = max(0, int(exp - time.time()))
    except Exception:
        pass

    # 使用 auth_manager 持久化加密凭据并缓存 token 到内存
    # token 不再以明文写入 user.json；user.json 仅存加密后的凭据和过期元数据
    # base_url 存储的是服务根地址（不含 /pandaData），init() 会自动追加
    from panda_data.auth_manager import save_auth_state as _save_auth_state
    _save_auth_state(
        username=username,
        password=password,
        base_url=_service_http_base(base_url),
        token=result,
        expires_in=expires_in,
    )

    # tick token 只给 WebSocket 使用；普通数据客户端仍按 /pandaData 初始化。
    if not tick_user:
        try:
            init_client(
                username=username,
                password=password,
                base_url=_service_http_base(base_url),
            )
        except Exception as e:
            # 如果初始化失败，不影响token保存，但记录警告
            print(f"警告：客户端初始化失败: {e}")

    return result

