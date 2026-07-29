from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import pandas as pd

from panda_data.client import get_client


def request_service(
    endpoint: str,
    base_url: Optional[str] = None,
    *,
    payload: Optional[Dict[str, Any]] = None,
    method: str = "POST",
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    data_path: Optional[Iterable[str]] = None,
) -> Any:
    client = get_client(base_url)
    return client.request(
        endpoint=endpoint,
        payload=payload,
        method=method,
        params=params,
        headers=headers,
        data_path=data_path,
    )


def fetch_dataframe(
    endpoint: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    method: str = "POST",
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    data_path: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    client = get_client()
    return client.fetch_dataframe(
        endpoint=endpoint,
        payload=payload,
        method=method,
        params=params,
        headers=headers,
        data_path=data_path,
    )

