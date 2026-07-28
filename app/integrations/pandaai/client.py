from __future__ import annotations

import base64
from io import BytesIO
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import md5
from typing import Any, TypeVar
from urllib.parse import urljoin

import httpx
import pyarrow.parquet as pq

from app.core.config import Settings, get_settings
from app.integrations.pandaai.schemas import (
    PandaAICompanyProfile,
    PandaAIDailyBar,
    PandaAIMktFinMetricRecord,
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
        )
        self._token_lock = threading.Lock()
        self._cache_lock = threading.Lock()
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

    def _post_data(self, endpoint: str, payload: dict[str, Any]) -> Any:
        retries = max(1, self._settings.pandaai_max_retries)
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            token = self._ensure_token(force_refresh=False)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": token,
            }
            url = self._build_data_url(endpoint)
            start = time.perf_counter()

            try:
                response = self._http_client.post(url, json=payload, headers=headers)
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.info(
                    "pandaai_request endpoint=%s status=%s attempt=%s duration_ms=%s",
                    endpoint,
                    response.status_code,
                    attempt,
                    duration_ms,
                )

                if response.status_code == 401:
                    self._ensure_token(force_refresh=True)
                    continue

                response.raise_for_status()
                parsed_data, token_expired = self._parse_response_data(endpoint, response)
                if token_expired:
                    self._ensure_token(force_refresh=True)
                    continue
                return parsed_data
            except (httpx.HTTPError, ValueError, PandaAIIntegrationError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(min(0.4 * attempt, 1.2))

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

            payload = {
                "username": username,
                "password": md5(password.encode("utf-8")).hexdigest(),
            }
            response = self._http_client.post(
                self._build_login_url(),
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            parsed = response.json()
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

            jwt_expiry = self._decode_jwt_expiry(token)
            self._token = token
            self._token_expires_at = jwt_expiry or (time.time() + expires_in)
            return token

    def _build_login_url(self) -> str:
        return urljoin(self._login_base_url().rstrip("/") + "/", LOGIN_ENDPOINT.lstrip("/"))

    def _build_data_url(self, endpoint: str) -> str:
        return urljoin(self._service_base_url().rstrip("/") + "/", endpoint.lstrip("/"))

    def _parse_response_data(
        self,
        endpoint: str,
        response: httpx.Response,
    ) -> tuple[Any, bool]:
        content_type = (response.headers.get("content-type") or "").lower()
        if "application/json" in content_type or _looks_like_json(response.content):
            parsed = response.json()
            code = str(parsed.get("code", "200"))
            if code in TOKEN_EXPIRED_CODES:
                return [], True
            if code != "200":
                raise PandaAIIntegrationError(
                    parsed.get("message") or f"PandaAI business error {code} on {endpoint}."
                )
            return parsed.get("data", []), False

        if _looks_like_parquet(response.content):
            return _decode_parquet_records(response.content), False

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
    for pattern in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_value, pattern).date()
        except ValueError:
            continue
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


def get_pandaai_client(settings: Settings | None = None) -> PandaAIClient:
    return PandaAIClient(settings or get_settings())
