"""
auth_manager.py — Centralized authentication state management.

Security design:
- Token lives ONLY in memory (never written to disk).
- Credentials are encrypted at rest in ``user.json`` using a key derived from
  the machine fingerprint (hostname + MAC + fixed salt).
- The public API exposes only auth-status / remaining-duration information;
  it never leaks the raw token string or internal user-id.

Usage::

    # Login
    panda_data.init_token(username, password, base_url)

    # Check auth status
    panda_data.is_authenticated()          # → True / False
    panda_data.auth_remaining_seconds()    # → 86340 (seconds until expiry)

    # On subsequent sessions, auto-login happens transparently
    df = panda_data.get_stock_daily(...)   # re-logs in if user.json exists
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import os
import platform
import secrets
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# Machine-fingerprint key derivation (standard library only — zero deps)
# ---------------------------------------------------------------------------

_SALT = b"panda_data_auth_v2"  # v2: HMAC-protected encryption
_KEY_ITERATIONS = 200_000
_HMAC_SEPARATOR = b"::hmac::"


def _get_pepper() -> bytes:
    """Return the pepper from env var ``PANDA_DATA_AUTH_PEPPER``.

    If not set, encryption still works with machine-fingerprint-derived key.
    Production deployments that need defense-in-depth should set this,
    but the primary security boundary is server-side (Gateway JWT + Redis).
    """
    pepper = os.environ.get("PANDA_DATA_AUTH_PEPPER", "").strip()
    return pepper.encode("utf-8") if pepper else b""


def _get_machine_fingerprint() -> str:
    """Return a host-specific string used to encrypt on-disk credentials."""
    try:
        parts = [
            platform.node() or "unknown-host",
            str(uuid.getnode()),
            socket.gethostname() or "unknown-name",
            platform.machine() or "unknown-arch",
        ]
    except Exception:
        parts = ["fallback", str(uuid.getnode())]
    return "|".join(parts)


def _derive_key(fingerprint: str) -> Tuple[bytes, bytes]:
    """Derive encryption + signing keys (each 32 bytes) from fingerprint + pepper.

    Returns ``(encryption_key, signing_key)``.
    """
    pepper = _get_pepper()
    # HKDF-style: derive 64 bytes, split into enc-key (first 32) and hmac-key (last 32)
    material = fingerprint.encode() + _HMAC_SEPARATOR + pepper
    raw = hashlib.pbkdf2_hmac(
        "sha256", material, _SALT, _KEY_ITERATIONS, dklen=64
    )
    return raw[:32], raw[32:]


def _generate_key_stream(key: bytes, iv: bytes, length: int) -> bytes:
    """Expand *key* + *iv* into a deterministic stream of *length* bytes."""
    result = b""
    counter = 0
    while len(result) < length:
        h = hashlib.sha256(key + iv + counter.to_bytes(4, "big")).digest()
        result += h
        counter += 1
    return result[:length]


def _encrypt(plaintext: str, enc_key: bytes, sign_key: bytes) -> str:
    """Encrypt + HMAC-sign *plaintext*.

    Output format: ``base64(iv || ciphertext || hmac_sha256)``
    where *iv* is 16 random bytes and *hmac* is 32 bytes.
    Any tampering with the ciphertext will cause decryption to fail.
    """
    iv = secrets.token_bytes(16)
    plain_bytes = plaintext.encode("utf-8")
    key_stream = _generate_key_stream(enc_key, iv, len(plain_bytes))
    ciphertext = bytes(a ^ b for a, b in zip(plain_bytes, key_stream))

    # HMAC over iv + ciphertext (authenticated encryption)
    payload = iv + ciphertext
    mac = hmac_mod.digest(sign_key, payload, "sha256")

    return base64.b64encode(payload + mac).decode("ascii")


def _decrypt(encrypted: str, enc_key: bytes, sign_key: bytes) -> str:
    """Verify HMAC then decrypt.  Raises ``ValueError`` on integrity failure."""
    data = base64.b64decode(encrypted.encode("ascii"))

    if len(data) < 16 + 32:  # iv + hmac minimum
        raise ValueError("Encrypted data too short — may be corrupted")

    payload = data[:-32]  # iv + ciphertext
    mac = data[-32:]  # HMAC tag

    # Verify integrity before decrypting
    expected_mac = hmac_mod.digest(sign_key, payload, "sha256")
    if not secrets.compare_digest(mac, expected_mac):
        raise ValueError(
            "Credential integrity check failed — the user.json file may have "
            "been tampered with.  Delete it and re-login."
        )

    iv = payload[:16]
    ciphertext = payload[16:]
    key_stream = _generate_key_stream(enc_key, iv, len(ciphertext))
    plain_bytes = bytes(a ^ b for a, b in zip(ciphertext, key_stream))
    return plain_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# Auth state (module-private globals)
# ---------------------------------------------------------------------------


@dataclass
class _AuthState:
    token: Optional[str] = None
    username: Optional[str] = None
    base_url: Optional[str] = None
    login_timestamp: float = 0.0
    token_expires_in_seconds: int = 14400  # default 4 h

    @property
    def is_valid(self) -> bool:
        return self.token is not None

    @property
    def expires_at(self) -> float:
        return self.login_timestamp + self.token_expires_in_seconds

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.expires_at - time.time())


_auth_state = _AuthState()
_auth_lock = threading.Lock()

# ---------------------------------------------------------------------------
# user.json helpers
# ---------------------------------------------------------------------------

# Keep a module-level cache so we don't walk the filesystem on every call.
_user_json_dir: Optional[str] = None


def _get_user_json_path() -> str:
    global _user_json_dir
    if _user_json_dir is None:
        from panda_data.utils.common_utils import find_project_root

        _user_json_dir = find_project_root(os.path.dirname(__file__))
    return os.path.join(_user_json_dir, "user.json")


def _read_persisted_credentials() -> Optional[Dict[str, Any]]:
    """Decrypt and return the credential blob from *user.json*, or *None*."""
    filepath = _get_user_json_path()
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None

    enc_creds = data.get("encrypted_credentials")
    if not enc_creds:
        # Legacy / empty file — treat as absent.
        return None

    try:
        enc_key, sign_key = _derive_key(_get_machine_fingerprint())
        creds_json = _decrypt(enc_creds, enc_key, sign_key)
        creds = json.loads(creds_json)
    except Exception:
        return None

    return {
        "username": creds.get("username", ""),
        "password": creds.get("password", ""),
        "base_url": data.get("base_url", ""),
        "login_timestamp": data.get("login_timestamp", 0.0),
        "token_expires_in_seconds": data.get("token_expires_in_seconds", 14400),
    }


def _persist_credentials(username: str, password: str, base_url: str, expires_in: int) -> None:
    """Write encrypted credentials + metadata to *user.json* (NO token)."""
    enc_key, sign_key = _derive_key(_get_machine_fingerprint())
    creds_json = json.dumps({"username": username, "password": password})
    encrypted = _encrypt(creds_json, enc_key, sign_key)

    file_data: Dict[str, Any] = {
        "encrypted_credentials": encrypted,
        "base_url": base_url,
        "login_timestamp": time.time(),
        "token_expires_in_seconds": expires_in,
        "last_verified_at": time.time(),
    }

    filepath = _get_user_json_path()
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(file_data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Internal HTTP login helper (avoids circular imports from init_token)
# ---------------------------------------------------------------------------


def _http_login(
    username: str, password: str, base_url: str
) -> Tuple[str, int]:
    """POST to the login endpoint and return ``(token, expires_in_seconds)``.

    This is a self-contained helper that does **not** depend on init_token or
    the global client factory so that auth_manager stays importable even before
    the rest of the SDK is wired.
    """
    from hashlib import md5
    from panda_data.config import get_config
    from panda_data.exceptions import ServiceError
    from panda_data.transport.http import HTTPClient, HTTPClientConfig
    from panda_data.utils.common_utils import build_endpoint

    cfg = get_config()
    # Resolve the login URL
    user_endpoint = cfg.get("JAVA_SERVICE_USER_ENDPOINT", "/dataUser")
    login_path = cfg.get("JAVA_SERVICE_USER_PATH_LOGIN", "/login")
    endpoint = build_endpoint(user_endpoint, login_path)

    # Strip any /pandaData or /pandaDataTick context path to get the bare
    # login base URL.
    def _service_http_base(url: str) -> str:
        u = url.rstrip("/")
        for cp in ("/pandaDataTick", "/pandaData"):
            if u.endswith(cp):
                return u[: -len(cp)]
        return u

    login_base = _service_http_base(base_url) + "/pandaData"
    full_login_url = urljoin(login_base.rstrip("/") + "/", endpoint.lstrip("/"))

    http_config = HTTPClientConfig(
        base_url=login_base, username=username, password=password
    )
    http_client = HTTPClient(http_config)

    payload = {
        "username": username,
        "password": md5(password.encode("utf-8")).hexdigest(),
    }

    try:
        raw_response = http_client.request(
            method="POST", endpoint=endpoint, payload=payload
        )
    except ServiceError as exc:
        msg = str(exc)
        if msg.startswith("HTTP 404"):
            msg = (
                f"{msg}\n"
                f"Login URL: {full_login_url}\n"
                "If this port does not serve the HTTP login endpoint, "
                "specify the correct gateway address."
            )
        raise ServiceError(msg) from exc
    except Exception as exc:
        raise ServiceError(f"Login failed: {exc} (URL: {full_login_url})") from exc
    finally:
        http_client.close()

    # Parse response: may be {code, data: "<token>"} (legacy format) or
    # {code, data: {token, expires_in}} (extended format).
    expires_in = int(os.environ.get("PANDA_AUTH_TOKEN_TTL", "14400"))  # fallback 默认
    if isinstance(raw_response, str):
        result = raw_response
    elif isinstance(raw_response, dict):
        code = raw_response.get("code")
        if code is not None and code not in (200, "200"):
            raise ServiceError(
                f"[Error code {code}: {raw_response.get('message', 'unknown')}]"
            )
        data = raw_response.get("data")
        if isinstance(data, dict):
            result = data.get("token", "")
            expires_in = int(data.get("expires_in", 14400))
        elif isinstance(data, str):
            result = data
        elif data is None and "token" in raw_response:
            result = raw_response["token"]
        else:
            result = str(data) if data else ""
    else:
        result = str(raw_response)

    if not result or not isinstance(result, str):
        raise ServiceError("Login failed: unable to obtain a valid token")

    # 从 JWT 的 exp 字段提取实际 TTL（覆盖默认值）
    try:
        parts = result.split(".")
        if len(parts) == 3:
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            jwt_payload = json.loads(base64.b64decode(payload_b64))
            exp = jwt_payload.get("exp", 0)
            if exp > 0:
                expires_in = max(0, int(exp - time.time()))
    except Exception:
        pass  # 解析失败就用默认值

    return result, expires_in


# ---------------------------------------------------------------------------
# Public API — used by the rest of the SDK
# ---------------------------------------------------------------------------


def save_auth_state(
    username: str,
    password: str,
    base_url: str,
    token: str,
    expires_in: int = 14400,
) -> None:
    """Persist encrypted credentials to disk and cache *token* in memory."""
    global _auth_state
    with _auth_lock:
        _auth_state.token = token
        _auth_state.username = username
        _auth_state.base_url = base_url
        _auth_state.login_timestamp = time.time()
        _auth_state.token_expires_in_seconds = expires_in

    _persist_credentials(username, password, base_url, expires_in)


def get_token() -> Optional[str]:
    """Return the currently cached token (in-memory), or *None*."""
    with _auth_lock:
        return _auth_state.token


def get_base_url() -> Optional[str]:
    with _auth_lock:
        return _auth_state.base_url


def get_username() -> Optional[str]:
    with _auth_lock:
        return _auth_state.username


def get_password() -> Optional[str]:
    """Return the decrypted password from disk (used for re-login)."""
    creds = _read_persisted_credentials()
    return creds.get("password") if creds else None


def get_decrypted_credentials() -> Optional[Dict[str, Any]]:
    """Return the full decrypted credential dict or *None*."""
    return _read_persisted_credentials()


# -- Public status queries (safe to expose to end users) --


def is_authenticated() -> bool:
    """Return *True* if a valid token is cached in memory."""
    with _auth_lock:
        return _auth_state.is_valid


def auth_remaining_seconds() -> float:
    """Approximate seconds until the current session expires.

    Returns 0.0 when not authenticated or when the expiry has already passed.
    """
    with _auth_lock:
        return _auth_state.remaining_seconds


def auth_expires_at() -> Optional[float]:
    """Return the POSIX timestamp at which the current session expires, or *None*."""
    with _auth_lock:
        if _auth_state.is_valid:
            return _auth_state.expires_at
        return None


def get_token_ttl() -> int:
    """Return the token's configured TTL in seconds (the full duration, not remaining)."""
    with _auth_lock:
        return _auth_state.token_expires_in_seconds


def auth_info() -> Dict[str, Any]:
    """Return a user-safe dict with auth status and duration (no token / uid)."""
    with _auth_lock:
        return {
            "authenticated": _auth_state.is_valid,
            "remaining_seconds": _auth_state.remaining_seconds,
            "expires_at": _auth_state.expires_at if _auth_state.is_valid else None,
            "username": _auth_state.username,
        }


# -- Auto-login & re-login --


def auto_login_from_disk() -> bool:
    """Attempt to log in using persisted credentials.

    Returns *True* when login succeeds and the in-memory token is refreshed.
    """
    creds = _read_persisted_credentials()
    if not creds:
        return False

    username = creds["username"]
    password = creds["password"]
    base_url = creds["base_url"]

    if not all([username, password, base_url]):
        return False

    try:
        token, expires_in = _http_login(username, password, base_url)
        save_auth_state(username, password, base_url, token, expires_in)
        return True
    except Exception:
        return False


# 防止并发 re-login 的互斥锁
_relogin_lock = threading.Lock()
# 记录最后一次 re-login 尝试的时间戳，避免短时间内重复尝试
_last_relogin_attempt: float = 0.0
_RELOGIN_COOLDOWN_SECONDS = 5.0  # 两次 re-login 之间的最小间隔


def re_login() -> bool:
    """Re-login using persisted credentials (called on 401 or proactive refresh).

    线程安全：同一时刻只允许一个线程执行 HTTP 登录；
    其余线程短暂等待后复用结果，避免惊群效应。

    Returns *True* on success.  On failure the in-memory token is cleared.
    """
    global _last_relogin_attempt

    # 快速路径：如果 token 仍然有效且不接近过期，直接返回成功
    with _auth_lock:
        if _auth_state.is_valid and _auth_state.remaining_seconds > 60:
            return True

    # 冷却期检查：避免短时间内重复尝试（比如网关暂时不可达）
    now = time.time()
    if now - _last_relogin_attempt < _RELOGIN_COOLDOWN_SECONDS:
        with _auth_lock:
            return _auth_state.is_valid

    # 尝试获取 re-login 锁（非阻塞）
    if not _relogin_lock.acquire(blocking=False):
        # 另一个线程正在执行 re-login，等待其完成（最多 5 秒）
        for _ in range(50):
            time.sleep(0.1)
            with _auth_lock:
                if _auth_state.is_valid:
                    return True
        # 等待超时 → 返回当前状态
        with _auth_lock:
            return _auth_state.is_valid

    try:
        # 双重检查：获取锁后再次确认是否需要 re-login
        with _auth_lock:
            if _auth_state.is_valid and _auth_state.remaining_seconds > 60:
                return True

        _last_relogin_attempt = time.time()

        creds = _read_persisted_credentials()
        if not creds:
            return False

        username = creds["username"]
        password = creds["password"]
        base_url = creds["base_url"]

        if not all([username, password, base_url]):
            return False

        token, expires_in = _http_login(username, password, base_url)
        save_auth_state(username, password, base_url, token, expires_in)
        return True
    except Exception:
        with _auth_lock:
            _auth_state.token = None
        return False
    finally:
        _relogin_lock.release()


def is_token_near_expiry(threshold_seconds: float = 1800.0) -> bool:
    """Return *True* when the token expires within *threshold_seconds* (default 30 min)."""
    with _auth_lock:
        if not _auth_state.is_valid:
            return False
        return _auth_state.remaining_seconds <= threshold_seconds


def proactive_refresh_if_needed(threshold_seconds: float = 1800.0) -> bool:
    """If the token is near expiry, attempt a proactive re-login.

    Returns *True* if a refresh was attempted and succeeded.
    """
    if is_token_near_expiry(threshold_seconds):
        return re_login()
    return False  # no refresh needed


def clear_auth() -> None:
    """Clear in-memory token and remove *user.json*."""
    global _auth_state
    with _auth_lock:
        _auth_state = _AuthState()
    try:
        os.remove(_get_user_json_path())
    except OSError:
        pass
