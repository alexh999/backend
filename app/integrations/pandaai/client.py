from __future__ import annotations

import base64
import gzip
import importlib
import json
import logging
import math
import ssl
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import md5
from io import BytesIO
from pathlib import Path
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPSHandler, Request, build_opener

import httpx
import pyarrow.parquet as pq
import zstandard as zstd

from app.core.config import Settings, get_settings
from app.integrations.pandaai.schemas import (
    PandaAICompanyProfile,
    PandaAIDailyBar,
    PandaAIIndexDetailRecord,
    PandaAIIndexProfile,
    PandaAIMktFinMetricRecord,
    PandaAIStockDetailRecord,
    PandaAIUsDailyRecord,
    PandaAIUsDetailRecord,
    PandaAIValuationSnapshot,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

LOGIN_ENDPOINT = "/dataUser/login"
US_DETAIL_ENDPOINT = "/multi/getUsDetail"
US_DAILY_ENDPOINT = "/usMarket/getStockMarketUSData"
US_MKTFIN_ENDPOINT = "/stock/getStockMktfinMetric"
CN_DETAIL_ENDPOINT = "/multi/getStockDetail"
CN_DAILY_ENDPOINT = "/multi/getStockDaily"
CN_RT_DAILY_ENDPOINT = "/multi/getStockRtDaily"
CN_INDEX_DETAIL_ENDPOINT = "/index/getIndexSymbolData"
CN_INDEX_DAILY_ENDPOINT = "/multi/getIndexDaily"
TOKEN_EXPIRED_CODES = {"200002", "200004"}


class PandaAIIntegrationError(Exception):
    pass


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class PandaAIClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http_client = httpx.Client(
            timeout=settings.pandaai_timeout_seconds,
            verify=settings.pandaai_verify_ssl,
            follow_redirects=False,
        )
        self._http_opener = self._build_http_opener()
        self._token_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._vendor_lock = threading.Lock()
        self._vendor_sdk: Any | None = None
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._cache: dict[str, _CacheEntry] = {}

    def get_us_detail(self, symbol: str) -> PandaAICompanyProfile:
        cache_key = f"us-detail:{symbol.upper()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {"symbol": [symbol.upper()]}
        raw_items = self._post_data(US_DETAIL_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIUsDetailRecord)
        if not records:
            raise PandaAIIntegrationError(f"PandaAI returned no company profile for {symbol.upper()}.")

        profile = self._map_profile(records[0])
        self._set_cached(cache_key, profile)
        return profile

    def get_us_daily(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PandaAIDailyBar]:
        cache_key = f"us-daily:{symbol.upper()}:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {
            "symbol": [symbol.upper()],
            "startDate": start_date.strftime("%Y%m%d"),
            "endDate": end_date.strftime("%Y%m%d"),
        }
        raw_items = self._post_data(US_DAILY_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIUsDailyRecord)
        daily_bars = [
            self._map_daily_bar(record)
            for record in records
            if record.close is not None
            and record.open is not None
            and record.high is not None
            and record.low is not None
        ]
        daily_bars.sort(key=lambda item: item.trade_date)
        self._set_cached(cache_key, daily_bars)
        return daily_bars

    def get_stock_mktfin_metric(self, symbol: str) -> PandaAIValuationSnapshot:
        cache_key = f"us-mktfin:{symbol.upper()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {"symbol": [symbol.upper()]}
        raw_items = self._post_data(US_MKTFIN_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIMktFinMetricRecord)
        if not records:
            raise PandaAIIntegrationError(f"PandaAI returned no financial metric snapshot for {symbol.upper()}.")

        latest_record = max(records, key=lambda item: item.date or "")
        snapshot = self._map_metric_snapshot(latest_record)
        self._set_cached(cache_key, snapshot)
        return snapshot

    def get_cn_detail(self, symbol: str) -> PandaAICompanyProfile:
        normalized_symbol = symbol.upper()
        cache_key = f"cn-detail:{normalized_symbol}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {"symbol": [normalized_symbol]}
        raw_items = self._post_data(CN_DETAIL_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIStockDetailRecord)
        if not records:
            raise PandaAIIntegrationError(f"PandaAI returned no company profile for {normalized_symbol}.")

        profile = self._map_cn_profile(records[0])
        self._set_cached(cache_key, profile)
        return profile

    def get_cn_daily(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PandaAIDailyBar]:
        normalized_symbol = symbol.upper()
        cache_key = f"cn-daily:{normalized_symbol}:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {
            "symbols": [normalized_symbol],
            "startDate": start_date.strftime("%Y%m%d"),
            "endDate": end_date.strftime("%Y%m%d"),
            "st": True,
        }
        raw_items = self._post_data(CN_DAILY_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIUsDailyRecord)
        daily_bars = [
            self._map_daily_bar(record)
            for record in records
            if record.close is not None
            and record.open is not None
            and record.high is not None
            and record.low is not None
        ]
        daily_bars.sort(key=lambda item: item.trade_date)
        self._set_cached(cache_key, daily_bars)
        return daily_bars

    def get_cn_rt_daily(self, symbol: str) -> PandaAIDailyBar | None:
        normalized_symbol = symbol.upper()
        cache_key = f"cn-rt-daily:{normalized_symbol}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {"symbol": [normalized_symbol]}
        raw_items = self._post_data(CN_RT_DAILY_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIUsDailyRecord)
        daily_bars = [
            self._map_daily_bar(record)
            for record in records
            if record.close is not None
            and record.open is not None
            and record.high is not None
            and record.low is not None
        ]
        if not daily_bars:
            self._set_cached(cache_key, None)
            return None

        latest_bar = max(daily_bars, key=lambda item: item.trade_date)
        self._set_cached(cache_key, latest_bar)
        return latest_bar

    def get_cn_index_detail(self, symbol: str) -> PandaAIIndexProfile:
        normalized_symbol = symbol.upper()
        cache_key = f"cn-index-detail:{normalized_symbol}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {
            "symbol": [normalized_symbol],
            "status": 1,
        }
        raw_items = self._post_data(CN_INDEX_DETAIL_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIIndexDetailRecord)
        if not records:
            payload = {"symbol": [normalized_symbol]}
            raw_items = self._post_data(CN_INDEX_DETAIL_ENDPOINT, payload)
            records = self._coerce_records(raw_items, PandaAIIndexDetailRecord)
        if not records:
            raise PandaAIIntegrationError(f"PandaAI returned no index profile for {normalized_symbol}.")

        profile = self._map_index_profile(records[0])
        self._set_cached(cache_key, profile)
        return profile

    def get_cn_index_details(self, symbols: list[str]) -> dict[str, PandaAIIndexProfile]:
        normalized_symbols = [symbol.upper() for symbol in symbols if symbol.strip()]
        if not normalized_symbols:
            return {}

        result: dict[str, PandaAIIndexProfile] = {}
        missing_symbols: list[str] = []
        for symbol in normalized_symbols:
            cache_key = f"cn-index-detail:{symbol}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                result[symbol] = cached
            else:
                missing_symbols.append(symbol)

        if missing_symbols:
            payload = {
                "symbol": missing_symbols,
                "status": 1,
            }
            raw_items = self._post_data(CN_INDEX_DETAIL_ENDPOINT, payload)
            records = self._coerce_records(raw_items, PandaAIIndexDetailRecord)
            if not records:
                payload = {"symbol": missing_symbols}
                raw_items = self._post_data(CN_INDEX_DETAIL_ENDPOINT, payload)
                records = self._coerce_records(raw_items, PandaAIIndexDetailRecord)

            for record in records:
                profile = self._map_index_profile(record)
                cache_key = f"cn-index-detail:{profile.symbol}"
                self._set_cached(cache_key, profile)
                result[profile.symbol] = profile

        return result

    def get_cn_index_daily(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PandaAIDailyBar]:
        normalized_symbol = symbol.upper()
        cache_key = f"cn-index-daily:{normalized_symbol}:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        payload = {
            "symbols": [normalized_symbol],
            "startDate": start_date.strftime("%Y%m%d"),
            "endDate": end_date.strftime("%Y%m%d"),
        }
        raw_items = self._post_data(CN_INDEX_DAILY_ENDPOINT, payload)
        records = self._coerce_records(raw_items, PandaAIUsDailyRecord)
        daily_bars = [
            self._map_daily_bar(record)
            for record in records
            if record.close is not None
            and record.open is not None
            and record.high is not None
            and record.low is not None
        ]
        daily_bars.sort(key=lambda item: item.trade_date)
        self._set_cached(cache_key, daily_bars)
        return daily_bars

    def get_cn_index_daily_batch(
        self,
        symbols: list[str],
        *,
        start_date: date,
        end_date: date,
    ) -> dict[str, list[PandaAIDailyBar]]:
        normalized_symbols = [symbol.upper() for symbol in symbols if symbol.strip()]
        if not normalized_symbols:
            return {}

        result: dict[str, list[PandaAIDailyBar]] = {}
        missing_symbols: list[str] = []
        for symbol in normalized_symbols:
            cache_key = f"cn-index-daily:{symbol}:{start_date.isoformat()}:{end_date.isoformat()}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                result[symbol] = cached
            else:
                missing_symbols.append(symbol)

        if missing_symbols:
            payload = {
                "symbols": missing_symbols,
                "startDate": start_date.strftime("%Y%m%d"),
                "endDate": end_date.strftime("%Y%m%d"),
            }
            raw_items = self._post_data(CN_INDEX_DAILY_ENDPOINT, payload)
            records = self._coerce_records(raw_items, PandaAIUsDailyRecord)
            grouped_records: dict[str, list[PandaAIDailyBar]] = {symbol: [] for symbol in missing_symbols}
            for record in records:
                if (
                    record.close is None
                    or record.open is None
                    or record.high is None
                    or record.low is None
                ):
                    continue
                daily_bar = self._map_daily_bar(record)
                grouped_records.setdefault(daily_bar.symbol, []).append(daily_bar)

            for symbol in missing_symbols:
                daily_bars = grouped_records.get(symbol, [])
                daily_bars.sort(key=lambda item: item.trade_date)
                cache_key = f"cn-index-daily:{symbol}:{start_date.isoformat()}:{end_date.isoformat()}"
                self._set_cached(cache_key, daily_bars)
                result[symbol] = daily_bars

        return result

    def _ensure_vendor_sdk_ready(self) -> Any:
        sdk = self._get_vendor_sdk()
        now = time.time()
        if self._token is not None and now < self._token_expires_at - 60:
            return sdk

        with self._token_lock:
            now = time.time()
            if self._token is not None and now < self._token_expires_at - 60:
                return sdk

            username = self._settings.pandaai_username.strip()
            password = self._settings.pandaai_password.strip()
            if not username or not password:
                raise PandaAIIntegrationError(
                    "PandaAI credentials are missing. Set PANDAAI_USERNAME and PANDAAI_PASSWORD in .env."
                )

            try:
                token, expires_in = self._login_with_vendor_compatible_httpx(username, password)
                auth_manager = importlib.import_module("panda_data.auth_manager")
                vendor_client = importlib.import_module("panda_data.client")
                auth_manager.save_auth_state(
                    username=username,
                    password=password,
                    base_url=self._service_root_url(),
                    token=token,
                    expires_in=expires_in,
                )
                vendor_client.init(
                    username=username,
                    password=password,
                    base_url=self._service_root_url(),
                    timeout=self._settings.pandaai_timeout_seconds,
                    max_retries=self._settings.pandaai_max_retries,
                    verify_ssl=self._settings.pandaai_verify_ssl,
                )
            except Exception as exc:
                raise PandaAIIntegrationError(f"PandaAI login request failed: {exc}") from exc

            self._token = token
            self._token_expires_at = self._decode_jwt_expiry(token) or (time.time() + expires_in)
            return sdk

    def _get_vendor_sdk(self) -> Any:
        with self._vendor_lock:
            if self._vendor_sdk is not None:
                return self._vendor_sdk

            candidate_roots = self._candidate_vendor_roots()
            vendor_root: Path | None = None
            for root in candidate_roots:
                if (root / "panda_data").exists():
                    vendor_root = root
                    break

            if vendor_root is None:
                raise PandaAIIntegrationError(
                    "Vendored panda_data package is missing in both the current repository and the backup backend directory."
                )

            vendor_root_text = str(vendor_root)
            if vendor_root_text not in sys.path:
                sys.path.insert(0, vendor_root_text)

            try:
                import panda_data  # type: ignore
            except Exception as exc:
                raise PandaAIIntegrationError(f"Unable to import vendored panda_data: {exc}") from exc

            self._vendor_sdk = panda_data
            return self._vendor_sdk

    def _candidate_vendor_roots(self) -> list[Path]:
        current_repo_vendor = Path(__file__).resolve().parents[3] / ".tmp_vendor"
        backup_vendor_roots: list[Path] = []
        try:
            for candidate in Path("D:/").glob("backend-main*"):
                vendor_root = candidate / ".tmp_vendor"
                if vendor_root.exists():
                    backup_vendor_roots.append(vendor_root)
        except OSError:
            pass

        # Prefer the original working backup directory first, then the current repo copy.
        return backup_vendor_roots + [current_repo_vendor]

    def _frame_to_records(self, frame: Any) -> list[dict[str, Any]]:
        if frame is None or getattr(frame, "empty", False):
            return []

        records = frame.to_dict(orient="records")
        normalized: list[dict[str, Any]] = []
        for item in records:
            normalized.append(
                {
                    key: _normalize_vendor_value(value)
                    for key, value in item.items()
                }
            )
        return normalized

    def _login_with_vendor_compatible_httpx(self, username: str, password: str) -> tuple[str, int]:
        payload = {
            "username": username,
            "password": md5(password.encode("utf-8")).hexdigest(),
        }
        headers = self._build_request_headers(include_basic_auth=True)
        retries = max(1, self._settings.pandaai_max_retries)
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                status_code, response_headers, response_content = self._post_with_httpx(
                    self._build_login_url(),
                    payload,
                    headers,
                    timeout=self._settings.pandaai_timeout_seconds,
                )
                if status_code >= 400:
                    raise PandaAIIntegrationError(
                        f"PandaAI login returned HTTP {status_code}: "
                        f"{_decode_text_preview(response_content)}"
                    )

                parsed = json.loads(response_content)
                code = str(parsed.get("code", "200"))
                if code != "200":
                    raise PandaAIIntegrationError(parsed.get("message") or "PandaAI login failed.")

                raw_data = parsed.get("data")
                token: str | None = None
                expires_in = 14400
                if isinstance(raw_data, dict):
                    token = raw_data.get("token")
                    expires_in = int(raw_data.get("expires_in", expires_in))
                elif isinstance(raw_data, str):
                    token = raw_data

                if not token:
                    raise PandaAIIntegrationError("PandaAI login response did not contain a token.")

                return token, expires_in
            except (httpx.HTTPError, ValueError, PandaAIIntegrationError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(min(0.5 * attempt, 2.0))

        raise PandaAIIntegrationError(f"PandaAI login request failed: {last_error}") from last_error

    def _post_data(self, endpoint: str, payload: dict[str, Any]) -> Any:
        retries = max(1, self._settings.pandaai_max_retries)
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            token = self._ensure_token(force_refresh=False)
            headers = self._build_request_headers(token=token)
            url = self._build_data_url(endpoint)
            start = time.perf_counter()

            try:
                status_code, response_headers, response_content = self._post_with_httpx(
                    url,
                    payload,
                    headers,
                    timeout=self._settings.pandaai_timeout_seconds,
                )
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.info(
                    "pandaai_request endpoint=%s status=%s attempt=%s duration_ms=%s",
                    endpoint,
                    status_code,
                    attempt,
                    duration_ms,
                )

                if status_code == 401:
                    self._ensure_token(force_refresh=True)
                    continue

                parsed_data, token_expired = self._parse_response_data(
                    endpoint,
                    response_content,
                    response_headers.get("Content-Type", ""),
                    response_headers.get("Content-Encoding", ""),
                )
                if token_expired:
                    self._ensure_token(force_refresh=True)
                    continue
                return parsed_data
            except (httpx.HTTPError, ValueError, PandaAIIntegrationError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(min(0.5 * attempt, 2.0))

        raise PandaAIIntegrationError(f"PandaAI request failed for {endpoint}: {last_error}") from last_error

    def _ensure_token(self, *, force_refresh: bool) -> str:
        with self._token_lock:
            now = time.time()
            if not force_refresh and self._token and now < self._token_expires_at - 60:
                return self._token

            username = self._settings.pandaai_username.strip()
            password = self._settings.pandaai_password.strip()
            if not username or not password:
                raise PandaAIIntegrationError(
                    "PandaAI credentials are missing. Set PANDAAI_USERNAME and PANDAAI_PASSWORD in .env."
                )

            try:
                token, expires_in = self._login_with_vendor_compatible_httpx(username, password)
                jwt_expiry = self._decode_jwt_expiry(token)
                self._token = token
                self._token_expires_at = jwt_expiry or (time.time() + expires_in)
                return token
            except (httpx.HTTPError, ValueError, PandaAIIntegrationError) as exc:
                raise PandaAIIntegrationError(f"PandaAI login request failed: {exc}") from exc

    def _build_login_url(self) -> str:
        return urljoin(self._login_base_url().rstrip("/") + "/", LOGIN_ENDPOINT.lstrip("/"))

    def _build_data_url(self, endpoint: str) -> str:
        return urljoin(self._service_base_url().rstrip("/") + "/", endpoint.lstrip("/"))

    def _parse_response_data(
        self,
        endpoint: str,
        response_content: bytes,
        content_type: str,
        content_encoding: str,
    ) -> tuple[Any, bool]:
        decoded_content = self._decode_response_bytes(response_content, content_encoding)
        normalized_content_type = (content_type or "").lower()

        if "application/json" in normalized_content_type or _looks_like_json(decoded_content):
            parsed = json.loads(decoded_content)
            code = str(parsed.get("code", "200"))
            if code in TOKEN_EXPIRED_CODES:
                return [], True
            if code != "200":
                raise PandaAIIntegrationError(
                    parsed.get("message") or f"PandaAI business error {code} on {endpoint}."
                )
            return parsed.get("data", []), False

        if _looks_like_parquet(decoded_content):
            return _decode_parquet_records(decoded_content), False

        raise PandaAIIntegrationError(
            f"Unsupported PandaAI response format for {endpoint}: {content_type or 'unknown'}."
        )

    def _service_root_url(self) -> str:
        raw_base = self._settings.pandaai_base_url.rstrip("/")
        for suffix in ("/pandaDataTick", "/pandaData"):
            if raw_base.endswith(suffix):
                return raw_base[: -len(suffix)]
        return raw_base

    def _service_base_url(self) -> str:
        return f"{self._service_root_url()}/pandaData"

    def _login_base_url(self) -> str:
        return f"{self._service_root_url()}/pandaData"

    def _build_http_opener(self):
        handlers: list[Any] = []
        if not self._settings.pandaai_verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            handlers.append(HTTPSHandler(context=ssl_context))
        else:
            handlers.append(HTTPSHandler())
        return build_opener(*handlers)

    def _build_request_headers(
        self,
        *,
        token: str | None = None,
        include_basic_auth: bool = False,
    ) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Encoding": "zstd",
        }
        if include_basic_auth:
            credentials = f"{self._settings.pandaai_username}:{self._settings.pandaai_password}"
            encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"
        elif token is not None:
            headers["Authorization"] = token
        return headers

    def _post_with_httpx(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        *,
        timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        try:
            response = self._http_client.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            return response.status_code, dict(response.headers.items()), response.content
        except httpx.HTTPError as exc:
            if not _should_try_curl_fallback(exc):
                raise
            return self._post_with_curl(url, payload, headers, timeout=timeout)

    def _post_with_curl(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        *,
        timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        command = [
            "curl.exe",
            "-sS",
            "-D",
            "-",
            "-X",
            "POST",
            url,
            "--max-time",
            str(max(1, math.ceil(timeout))),
            "--data-binary",
            json.dumps(payload, ensure_ascii=False),
        ]
        if url.lower().startswith("https://") and not self._settings.pandaai_verify_ssl:
            command.append("-k")

        for key, value in headers.items():
            if key.lower() == "accept-encoding":
                continue
            command.extend(["-H", f"{key}: {value}"])

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=max(2, math.ceil(timeout) + 2),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PandaAIIntegrationError(f"curl fallback failed: {exc}") from exc

        if completed.returncode != 0:
            stderr_text = _decode_text_preview(completed.stderr)
            raise PandaAIIntegrationError(
                f"curl fallback failed with exit code {completed.returncode}: {stderr_text}"
            )

        return _parse_curl_http_response(completed.stdout)

    def _open_json_request(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers=headers, method="POST")

        try:
            with self._http_opener.open(request, timeout=self._settings.pandaai_timeout_seconds) as response:
                return (
                    response.getcode(),
                    dict(response.headers.items()),
                    response.read(),
                )
        except HTTPError as exc:
            return (
                exc.code,
                dict(exc.headers.items()) if exc.headers is not None else {},
                exc.read(),
            )

    def _decode_response_bytes(self, payload: bytes, content_encoding: str) -> bytes:
        encoding = (content_encoding or "").lower()
        if not encoding:
            return payload
        if encoding == "gzip":
            return gzip.decompress(payload)
        if encoding in {"zstd", "z-standard"}:
            try:
                return zstd.ZstdDecompressor().decompress(payload)
            except zstd.ZstdError:
                reader = zstd.ZstdDecompressor().stream_reader(BytesIO(payload))
                try:
                    return reader.read()
                finally:
                    reader.close()
        return payload

    def _get_cached(self, key: str) -> Any | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() >= entry.expires_at:
                self._cache.pop(key, None)
                return None
            return entry.value

    def _set_cached(self, key: str, value: Any) -> None:
        with self._cache_lock:
            self._cache[key] = _CacheEntry(
                value=value,
                expires_at=time.time() + max(1, self._settings.pandaai_cache_ttl_seconds),
            )

    def _coerce_records(self, raw_data: Any, model_type: type[T]) -> list[T]:
        if raw_data is None:
            return []
        if isinstance(raw_data, dict):
            raw_items = [raw_data]
        elif isinstance(raw_data, list):
            raw_items = raw_data
        else:
            raise PandaAIIntegrationError(f"Unexpected PandaAI payload type: {type(raw_data).__name__}")
        return [model_type.model_validate(item) for item in raw_items if isinstance(item, dict)]

    def _get_vendor_records(self, method_name: str, model_type: type[T], /, **kwargs: Any) -> list[T]:
        sdk = self._ensure_vendor_sdk_ready()
        reader = getattr(sdk, method_name, None)
        if reader is None:
            raise PandaAIIntegrationError(f"Vendored panda_data is missing {method_name}.")

        try:
            frame = reader(**kwargs)
        except Exception as exc:
            raise PandaAIIntegrationError(f"PandaAI vendor call {method_name} failed: {exc}") from exc

        return self._coerce_records(self._frame_to_records(frame), model_type)

    def _map_profile(self, record: PandaAIUsDetailRecord) -> PandaAICompanyProfile:
        company_name = record.name or record.local_name or record.symbol.upper()
        exchange_label = None
        if record.exchange_name:
            exchange_label = record.exchange_name.split(" - ")[-1].strip()
        return PandaAICompanyProfile(
            symbol=record.symbol.upper(),
            company_name=company_name,
            local_name=record.local_name or company_name,
            exchange_label=exchange_label,
            listed_date=_parse_optional_date(record.listed_date),
            website=record.website,
            business_sector=record.business_sector,
            economic_sector=record.economic_sector,
            industry_group=record.industry_group,
            office_country=record.office_country,
            status=record.status,
        )

    def _map_cn_profile(self, record: PandaAIStockDetailRecord) -> PandaAICompanyProfile:
        company_name = record.name or record.symbol.upper()
        exchange_label = _exchange_label_from_symbol(record.symbol)
        sector_name = record.sector_code_name
        board_type = record.board_type
        province = record.province
        office_country = "China"
        if province:
            office_country = f"China / {province}"

        return PandaAICompanyProfile(
            symbol=record.symbol.upper(),
            company_name=company_name,
            local_name=company_name,
            exchange_label=exchange_label,
            listed_date=_parse_optional_date(record.listed_date),
            website=None,
            business_sector=sector_name,
            economic_sector=sector_name,
            industry_group=board_type,
            office_country=office_country,
            status=record.status,
        )

    def _map_index_profile(self, record: PandaAIIndexDetailRecord) -> PandaAIIndexProfile:
        index_name = (
            record.first_non_null("name", "index_name", "display_name", "full_name")
            or record.symbol.upper()
        )
        return PandaAIIndexProfile(
            symbol=record.symbol.upper(),
            index_name=str(index_name),
            exchange_label=_exchange_label_from_symbol(record.symbol) or record.exchange,
            listed_date=_parse_optional_date(record.listed_date),
            status=record.status,
            publisher=record.publisher,
            category=record.category,
        )

    def _map_daily_bar(self, record: PandaAIUsDailyRecord) -> PandaAIDailyBar:
        return PandaAIDailyBar(
            symbol=record.symbol.upper(),
            trade_date=_parse_required_date(record.date),
            open=float(record.open),
            high=float(record.high),
            low=float(record.low),
            close=float(record.close),
            volume=_coerce_float(record.volume),
            amount=_coerce_float(record.amount),
        )

    def _map_metric_snapshot(self, record: PandaAIMktFinMetricRecord) -> PandaAIValuationSnapshot:
        market_cap = _first_float(
            record,
            "curr_market_cap",
            "curr_market_value",
            "market_cap",
            "market_value",
            "curr_total_market_value",
            "total_market_value",
        )
        pe_ratio = _first_float(
            record,
            "curr_pe_ttm",
            "pe_ttm",
            "curr_price_to_eps_ttm",
            "price_to_eps_ttm",
        )
        dividend_yield = _first_float(
            record,
            "curr_dividend_yield_ttm",
            "dividend_yield_ttm",
            "curr_dividend_yield",
            "dividend_yield",
        )
        return PandaAIValuationSnapshot(
            symbol=record.symbol.upper(),
            as_of_date=_parse_optional_date(record.date),
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            dividend_yield=dividend_yield,
        )

    @staticmethod
    def _decode_jwt_expiry(token: str) -> float | None:
        try:
            payload_segment = token.split(".")[1]
            padding = "=" * (-len(payload_segment) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_segment + padding))
            expiry = payload.get("exp")
            return float(expiry) if expiry is not None else None
        except (IndexError, ValueError, json.JSONDecodeError):
            return None


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _normalize_vendor_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _first_float(record: Any, *names: str) -> float | None:
    value = record.first_non_null(*names)
    return _coerce_float(value)


def _parse_required_date(value: str) -> date:
    parsed = _parse_optional_date(value)
    if parsed is None:
        raise PandaAIIntegrationError(f"Unable to parse PandaAI date value: {value!r}")
    return parsed


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    raw_value = value.strip()
    if raw_value in {"0000-00-00", "00000000"}:
        return None
    for pattern in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_value, pattern).date()
        except ValueError:
            continue
    return None


def _exchange_label_from_symbol(symbol: str) -> str | None:
    normalized_symbol = symbol.upper()
    if normalized_symbol.endswith(".SH"):
        return "SSE"
    if normalized_symbol.endswith(".SZ"):
        return "SZSE"
    if normalized_symbol.endswith(".BJ"):
        return "BSE"
    return None


def _looks_like_json(payload: bytes) -> bool:
    stripped = payload.lstrip()
    return stripped.startswith(b"{") or stripped.startswith(b"[")


def _looks_like_parquet(payload: bytes) -> bool:
    return len(payload) >= 4 and payload[:4] == b"PAR1"


def _decode_parquet_records(payload: bytes) -> list[dict[str, Any]]:
    try:
        table = pq.read_table(BytesIO(payload))
    except Exception as exc:  # pragma: no cover - provider payload dependent
        raise PandaAIIntegrationError(f"Failed to decode PandaAI parquet payload: {exc}") from exc

    return table.to_pylist()


def _should_try_curl_fallback(exc: httpx.HTTPError) -> bool:
    message = str(exc)
    if "WinError 10013" in message:
        return True

    cause = exc.__cause__
    while cause is not None:
        if "WinError 10013" in str(cause):
            return True
        cause = getattr(cause, "__cause__", None)
    return False


def _parse_curl_http_response(raw_response: bytes) -> tuple[int, dict[str, str], bytes]:
    payload = raw_response
    while payload.startswith(b"HTTP/"):
        header_block, separator, body = payload.partition(b"\r\n\r\n")
        if not separator:
            break

        header_lines = header_block.split(b"\r\n")
        status_line = header_lines[0].decode("iso-8859-1", errors="replace")
        parts = status_line.split(" ", 2)
        if len(parts) < 2 or not parts[1].isdigit():
            raise PandaAIIntegrationError(f"Unable to parse curl status line: {status_line!r}")

        status_code = int(parts[1])
        if 100 <= status_code < 200:
            payload = body
            continue

        headers: dict[str, str] = {}
        for line in header_lines[1:]:
            key, _, value = line.partition(b":")
            if not _:
                continue
            headers[key.decode("iso-8859-1", errors="replace")] = value.decode(
                "iso-8859-1",
                errors="replace",
            ).strip()
        return status_code, headers, body

    raise PandaAIIntegrationError("curl fallback returned an unparseable HTTP response.")


def _decode_text_preview(payload: bytes) -> str:
    if not payload:
        return ""
    for encoding in ("utf-8", "gb18030", "latin1"):
        try:
            return payload.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return repr(payload[:200])


def get_pandaai_client(settings: Settings | None = None) -> PandaAIClient:
    return PandaAIClient(settings or get_settings())
