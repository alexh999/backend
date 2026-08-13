from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time
from math import ceil

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.forum.models import ForumContentStatus, ForumPost
from app.modules.forum.schemas import ForumPostResponse
from app.modules.users.models import User, utc_now


@dataclass(frozen=True)
class ForumPostPage:
    items: list[ForumPost]
    total: int


class ForumPostNotFoundError(Exception):
    pass


class ForumModerationError(Exception):
    pass


def create_post(
    db: Session,
    *,
    author: User,
    content: str,
    topic_label: str,
) -> ForumPost:
    normalized_content = content.strip()
    normalized_topic = topic_label.strip() or "Discussion"
    post = ForumPost(
        author_user_id=author.id,
        content=normalized_content,
        topic_label=normalized_topic[:32],
        status=ForumContentStatus.PENDING,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def list_public_posts(db: Session, *, limit: int) -> list[ForumPost]:
    return list(
        db.scalars(
            select(ForumPost)
            .where(ForumPost.status == ForumContentStatus.APPROVED)
            .order_by(ForumPost.created_at.desc(), ForumPost.id.desc())
            .limit(limit)
        )
    )


def list_my_posts(db: Session, *, author: User, limit: int) -> list[ForumPost]:
    return list(
        db.scalars(
            select(ForumPost)
            .where(ForumPost.author_user_id == author.id)
            .order_by(ForumPost.created_at.desc(), ForumPost.id.desc())
            .limit(limit)
        )
    )


def list_admin_posts(
    db: Session,
    *,
    page: int,
    page_size: int,
    status: ForumContentStatus | None = None,
    author: str | None = None,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ForumPostPage:
    filters = []
    if status is not None:
        filters.append(ForumPost.status == status)
    normalized_author = _normalize(author)
    if normalized_author:
        filters.append(
            func.lower(User.username).contains(normalized_author, autoescape=True)
        )
    normalized_keyword = _normalize(keyword)
    if normalized_keyword:
        filters.append(
            func.lower(ForumPost.content).contains(normalized_keyword, autoescape=True)
        )
    if start_date is not None:
        filters.append(ForumPost.created_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        filters.append(ForumPost.created_at <= datetime.combine(end_date, time.max))

    base_query: Select[tuple[ForumPost]] = (
        select(ForumPost)
        .join(User, User.id == ForumPost.author_user_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    items = list(
        db.scalars(
            base_query.order_by(ForumPost.created_at.desc(), ForumPost.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return ForumPostPage(items=items, total=int(total))


def moderate_post(
    db: Session,
    *,
    post_id: int,
    moderator: User,
    status: ForumContentStatus,
    reason: str | None = None,
) -> ForumPost:
    post = db.get(ForumPost, post_id)
    if post is None:
        raise ForumPostNotFoundError("Forum post not found.")
    if status == ForumContentStatus.PENDING:
        raise ForumModerationError("Cannot move content back to pending.")
    allowed_transitions = {
        ForumContentStatus.PENDING: {
            ForumContentStatus.APPROVED,
            ForumContentStatus.REJECTED,
        },
        ForumContentStatus.APPROVED: {ForumContentStatus.HIDDEN},
        ForumContentStatus.HIDDEN: {ForumContentStatus.APPROVED},
        ForumContentStatus.REJECTED: set(),
    }
    if status not in allowed_transitions[post.status]:
        raise ForumModerationError(
            f"Cannot move content from {post.status.value} to {status.value}."
        )
    normalized_reason = reason.strip() if reason else None
    if status in {ForumContentStatus.REJECTED, ForumContentStatus.HIDDEN} and not normalized_reason:
        raise ForumModerationError("A moderation reason is required.")
    previous_status = post.status
    post.status = status
    post.moderation_reason = normalized_reason if status in {
        ForumContentStatus.REJECTED,
        ForumContentStatus.HIDDEN,
    } else None
    post.moderated_by_user_id = moderator.id
    post.moderated_at = utc_now()
    post.updated_at = utc_now()
    db.flush()
    return post


def to_post_response(post: ForumPost) -> ForumPostResponse:
    return ForumPostResponse(
        id=post.id,
        author_user_id=post.author_user_id,
        author_username=post.author.username if post.author is not None else "Unknown",
        content=post.content,
        topic_label=post.topic_label,
        status=post.status,
        moderation_reason=post.moderation_reason,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def calculate_total_pages(total: int, page_size: int) -> int:
    return max(1, ceil(total / page_size))


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    return normalized or None
