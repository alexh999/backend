from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewsArticleResponse(BaseModel):
    id: str
    category: str
    title: str
    summary: str
    source_name: str
    published_at: datetime | None = None
    published_text: str
    read_time_text: str
    article_url: str
    image_url: str | None = None
    content_paragraphs: list[str] = Field(default_factory=list)
    symbol: str | None = None


class NewsListResponse(BaseModel):
    articles: list[NewsArticleResponse]
