from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time
from math import ceil
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.modules.admin.models import AdminAuditAction, AdminAuditLog
from app.modules.admin.schemas import UserStatistics
from app.modules.users.models import User, UserRole, UserStatus, utc_now
from app.modules.users.service import UserServiceError, create_user


@dataclass(frozen=True)
class UserPage:
    items: list[User]
    total: int


@dataclass(frozen=True)
class AuditLogPage:
    items: list[AdminAuditLog]
    total: int


class UserNotFoundError(UserServiceError):
    pass


class SelfDisableError(UserServiceError):
    pass


class LastActiveAdminError(UserServiceError):
    pass


def create_admin_user(
    db: Session,
    *,
    actor: User,
    username: str,
    password: str,
) -> User:
    try:
        user = create_user(
            db,
            username=username,
            password=password,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            commit=False,
        )
        _add_audit_log(
            db,
            actor=actor,
            action=AdminAuditAction.ADMIN_CREATED,
            target=user,
            metadata={
                "new_role": user.role.value,
                "new_status": user.status.value,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user


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
        filters.append(func.lower(User.username).contains(normalized_query, autoescape=True))
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
    actor: User,
    is_active: bool,
) -> User:
    user = get_user_detail(db, user_id)
    if user is None:
        raise UserNotFoundError("User not found.")
    if not is_active and user.id == actor.id:
        raise SelfDisableError("Administrators cannot disable their own account.")
    if (
        not is_active
        and user.role == UserRole.ADMIN
        and user.status == UserStatus.ACTIVE
        and _active_admin_count(db) <= 1
    ):
        raise LastActiveAdminError("The last active administrator cannot be disabled.")

    previous_status = user.status
    user.status = UserStatus.ACTIVE if is_active else UserStatus.DISABLED
    user.updated_at = utc_now()
    try:
        db.flush()
        _add_audit_log(
            db,
            actor=actor,
            action=AdminAuditAction.USER_ENABLED if is_active else AdminAuditAction.USER_DISABLED,
            target=user,
            metadata={
                "previous_status": previous_status.value,
                "new_status": user.status.value,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user


def list_audit_logs(
    db: Session,
    *,
    page: int,
    page_size: int,
    action: AdminAuditAction | None = None,
    actor_username: str | None = None,
    target_username: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AuditLogPage:
    filters = []
    normalized_actor_username = _normalize_search_query(actor_username)
    normalized_target_username = _normalize_search_query(target_username)
    if action is not None:
        filters.append(AdminAuditLog.action == action)
    if normalized_actor_username:
        filters.append(
            func.lower(AdminAuditLog.actor_username).contains(
                normalized_actor_username,
                autoescape=True,
            )
        )
    if normalized_target_username:
        filters.append(
            func.lower(AdminAuditLog.target_username).contains(
                normalized_target_username,
                autoescape=True,
            )
        )
    if start_date is not None:
        filters.append(AdminAuditLog.created_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        filters.append(AdminAuditLog.created_at <= datetime.combine(end_date, time.max))

    filtered_logs: Select[tuple[AdminAuditLog]] = select(AdminAuditLog).where(*filters)
    total = db.scalar(select(func.count()).select_from(filtered_logs.subquery())) or 0
    items = list(
        db.scalars(
            filtered_logs.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return AuditLogPage(items=items, total=int(total))


def _normalize_search_query(query: str | None) -> str | None:
    if query is None:
        return None
    normalized = unicodedata.normalize("NFKC", query).strip().casefold()
    return normalized or None


def calculate_total_pages(total: int, page_size: int) -> int:
    return max(1, ceil(total / page_size))


def _active_admin_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN,
                User.status == UserStatus.ACTIVE,
            )
        )
        or 0
    )


def _add_audit_log(
    db: Session,
    *,
    actor: User,
    action: AdminAuditAction,
    target: User,
    metadata: dict[str, Any] | None = None,
) -> AdminAuditLog:
    log = AdminAuditLog(
        actor_user_id=actor.id,
        actor_username=actor.username,
        action=action,
        target_user_id=target.id,
        target_username=target.username,
        metadata_=metadata or {},
    )
    db.add(log)
    db.flush()
    return log
