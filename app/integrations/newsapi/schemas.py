from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsApiArticle(BaseModel):
    author: str | None = None
    title: str
    description: str | None = None
    article_url: str
    image_url: str | None = None
    published_at: datetime | None = None
    content: str | None = None
    source_name: str
