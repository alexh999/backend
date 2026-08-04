from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.integrations.newsapi.schemas import NewsApiArticle


class NewsApiIntegrationError(Exception):
    """Raised when NewsAPI cannot return usable news data."""


class NewsApiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.newsapi_base_url.rstrip("/")
        self._timeout = settings.newsapi_timeout_seconds
        self._language = settings.newsapi_default_language
        self._default_page_size = settings.newsapi_default_page_size

    def search(
        self,
        *,
        query: str,
        page_size: int | None = None,
        from_date: date | None = None,
    ) -> list[NewsApiArticle]:
        api_key = (
            self._settings.newsapi_api_key.get_secret_value()
            if self._settings.newsapi_api_key is not None
            else ""
        ).strip()
        if not api_key:
            raise NewsApiIntegrationError(
                "NewsAPI key is missing. Set NEWSAPI_API_KEY in .env."
            )

        params: dict[str, Any] = {
            "q": query,
            "language": self._language,
            "sortBy": "publishedAt",
            "pageSize": page_size or self._default_page_size,
        }
        if from_date is not None:
            params["from"] = from_date.isoformat()

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    f"{self._base_url}/everything",
                    params=params,
                    headers={"X-Api-Key": api_key, "Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NewsApiIntegrationError(f"NewsAPI request failed: {exc}") from exc

        if payload.get("status") != "ok":
            raise NewsApiIntegrationError(
                str(payload.get("message") or "NewsAPI returned an error.")
            )

        articles: list[NewsApiArticle] = []
        for raw_article in payload.get("articles", []):
            if not isinstance(raw_article, dict):
                continue
            title = str(raw_article.get("title") or "").strip()
            url = str(raw_article.get("url") or "").strip()
            if not title or not url or title == "[Removed]":
                continue
            source = raw_article.get("source") or {}
            published_at = raw_article.get("publishedAt")
            parsed_published_at = None
            if isinstance(published_at, str):
                try:
                    parsed_published_at = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    parsed_published_at = None
            articles.append(
                NewsApiArticle(
                    author=str(raw_article.get("author") or "").strip() or None,
                    title=title,
                    description=str(raw_article.get("description") or "").strip() or None,
                    article_url=url,
                    image_url=str(raw_article.get("urlToImage") or "").strip() or None,
                    published_at=parsed_published_at,
                    content=str(raw_article.get("content") or "").strip() or None,
                    source_name=str(source.get("name") or "NewsAPI").strip(),
                )
            )
        return articles


def get_newsapi_client(settings: Settings) -> NewsApiClient:
    return NewsApiClient(settings)
