from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.modules.admin.schemas import UserStatistics
from app.modules.users.models import User, UserRole, UserStatus, utc_now
from app.modules.users.service import UserServiceError


@dataclass(frozen=True)
class UserPage:
    items: list[User]
    total: int


class UserNotFoundError(UserServiceError):
    pass


class SelfDisableError(UserServiceError):
    pass


def get_user_statistics(db: Session) -> UserStatistics:
    row = db.execute(
        select(
            func.count(User.id),
            func.sum(case((User.status == UserStatus.ACTIVE, 1), else_=0)),
            func.sum(case((User.status == UserStatus.DISABLED, 1), else_=0)),
            func.sum(case((User.role == UserRole.ADMIN, 1), else_=0)),
            func.sum(case((User.role == UserRole.USER, 1), else_=0)),
        )
    ).one()
    return UserStatistics(
        total=int(row[0] or 0),
        active=int(row[1] or 0),
        disabled=int(row[2] or 0),
        admins=int(row[3] or 0),
        regular_users=int(row[4] or 0),
    )


def list_users(
    db: Session,
    *,
    page: int,
    page_size: int,
    query: str | None = None,
    role: UserRole | None = None,
    status: UserStatus | None = None,
) -> UserPage:
    filters = []
    normalized_query = _normalize_search_query(query)
    if normalized_query:
        filters.append(User.username.contains(normalized_query, autoescape=True))
    if role is not None:
        filters.append(User.role == role)
    if status is not None:
        filters.append(User.status == status)

    filtered_users: Select[tuple[User]] = select(User).where(*filters)
    total = db.scalar(select(func.count()).select_from(filtered_users.subquery())) or 0
    items = list(
        db.scalars(
            filtered_users.order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return UserPage(items=items, total=int(total))


def get_user_detail(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def update_user_status(
    db: Session,
    *,
    user_id: int,
    actor_id: int,
    is_active: bool,
) -> User:
    user = get_user_detail(db, user_id)
    if user is None:
        raise UserNotFoundError("User not found.")
    if not is_active and user.id == actor_id:
        raise SelfDisableError("Administrators cannot disable their own account.")

    user.status = UserStatus.ACTIVE if is_active else UserStatus.DISABLED
    user.updated_at = utc_now()
    db.commit()
    db.refresh(user)
    return user


def _normalize_search_query(query: str | None) -> str | None:
    if query is None:
        return None
    normalized = unicodedata.normalize("NFKC", query).strip().casefold()
    return normalized or None
