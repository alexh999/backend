from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
import re
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.errors import ApplicationError
from app.integrations.newsapi.client import NewsApiClient, NewsApiIntegrationError
from app.integrations.newsapi.schemas import NewsApiArticle
from app.modules.news.schemas import NewsArticleResponse, NewsListResponse


CATEGORY_QUERIES = {
    "markets": "(\"stock market\" OR stocks OR equities OR investing OR inflation OR \"interest rates\" OR \"Federal Reserve\" OR earnings)",
    "technology": "technology OR artificial intelligence OR semiconductor OR cloud",
    "earnings": "earnings OR quarterly results OR revenue guidance",
    "crypto": "bitcoin OR ethereum OR cryptocurrency",
    "business": "business OR finance OR economy",
}


class NewsService:
    def __init__(self, client: NewsApiClient) -> None:
        self._client = client

    def list_news(
        self,
        *,
        category: str,
        query: str | None,
        limit: int,
    ) -> NewsListResponse:
        category_key = category.strip().lower() or "markets"
        search_query = query.strip() if query and query.strip() else CATEGORY_QUERIES.get(
            category_key,
            CATEGORY_QUERIES["markets"],
        )
        try:
            articles = self._client.search(query=search_query, page_size=limit)
        except NewsApiIntegrationError as exc:
            raise ApplicationError(str(exc), status_code=502) from exc
        return NewsListResponse(
            articles=[self._to_response(article, category=category_key) for article in articles]
        )

    def list_symbol_news(self, *, symbol: str, limit: int) -> NewsListResponse:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ApplicationError("Stock symbol is required.", status_code=400)
        query_symbol = normalized.split(".", 1)[0]
        try:
            articles = self._client.search(
                query=f'"{query_symbol}" AND (stock OR shares OR earnings OR market)',
                page_size=limit,
            )
        except NewsApiIntegrationError as exc:
            raise ApplicationError(str(exc), status_code=502) from exc
        return NewsListResponse(
            articles=[
                self._to_response(article, category="stocks", symbol=normalized)
                for article in articles
            ]
        )

    def _to_response(
        self,
        article: NewsApiArticle,
        *,
        category: str,
        symbol: str | None = None,
    ) -> NewsArticleResponse:
        summary = article.description or _strip_provider_suffix(article.content) or article.title
        content = _strip_provider_suffix(article.content)
        paragraphs = [part for part in re.split(r"\n+", summary) if part.strip()]
        if content and content != summary:
            paragraphs.append(content)
        if not paragraphs:
            paragraphs = [article.title]
        return NewsArticleResponse(
            id=sha1(article.article_url.encode("utf-8")).hexdigest()[:16],
            category=category,
            title=article.title,
            summary=summary,
            source_name=article.source_name,
            published_at=article.published_at,
            published_text=_format_published_text(article.published_at),
            read_time_text=_format_read_time(summary, content),
            article_url=article.article_url,
            image_url=article.image_url,
            content_paragraphs=paragraphs[:4],
            symbol=symbol,
        )


def _strip_provider_suffix(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s*\[\+\d+ chars\]\s*$", "", value).strip()


def _format_published_text(value: datetime | None) -> str:
    if value is None:
        return "Recently"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - value.astimezone(timezone.utc)
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 60:
        return f"{max(1, minutes)} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


def _format_read_time(summary: str, content: str) -> str:
    word_count = len(f"{summary} {content}".split())
    minutes = max(1, round(word_count / 220))
    return f"{minutes} min read"


def get_news_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> NewsService:
    return NewsService(NewsApiClient(settings))
