from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.activity.models import UserDailyActivity
from app.modules.activity.schemas import DailyMetric, UserActivitySummaryResponse
from app.modules.users.models import User, UserRole, utc_now


logger = logging.getLogger(__name__)

MAX_ACTIVITY_STATS_DAYS = 366
MAU_WINDOW_DAYS = 30


class UserActivityEvent(StrEnum):
    AI_CHAT = "AI_CHAT"
    QUANT_ANALYSIS = "QUANT_ANALYSIS"
    PAPER_ORDER = "PAPER_ORDER"


class ActivityStatsRangeError(ValueError):
    pass


@dataclass(frozen=True)
class ActivityDateRange:
    start_date: date
    end_date: date
    as_of_date: date


def record_user_activity(
    db: Session,
    *,
    user: User | None,
    event: UserActivityEvent,
    occurred_at: datetime | None = None,
) -> None:
    if user is None or user.role != UserRole.USER:
        return

    now = _as_utc(occurred_at or utc_now())
    try:
        _upsert_daily_activity(db, user_id=user.id, occurred_at=now)
        db.commit()
    except IntegrityError:
        db.rollback()
        try:
            _update_daily_activity(db, user_id=user.id, occurred_at=now)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to record user activity after unique constraint race",
                extra={"user_id": user.id, "event": event.value},
            )
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to record user activity",
            extra={"user_id": user.id, "event": event.value},
        )


def get_user_activity_summary(
    db: Session,
    *,
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> UserActivitySummaryResponse:
    range_ = _resolve_activity_date_range(
        as_of_date=as_of_date,
        start_date=start_date,
        end_date=end_date,
    )
    daily_dau = _daily_activity_counts(db, range_.start_date, range_.end_date)
    daily_new_users = _daily_new_user_counts(db, range_.start_date, range_.end_date)
    mau_start = range_.as_of_date - timedelta(days=MAU_WINDOW_DAYS - 1)

    dau = int(
        db.scalar(
            select(func.count(UserDailyActivity.user_id.distinct())).where(
                UserDailyActivity.activity_date == range_.as_of_date,
            )
        )
        or 0
    )
    mau = int(
        db.scalar(
            select(func.count(UserDailyActivity.user_id.distinct())).where(
                UserDailyActivity.activity_date >= mau_start,
                UserDailyActivity.activity_date <= range_.as_of_date,
            )
        )
        or 0
    )

    return UserActivitySummaryResponse(
        as_of_date=range_.as_of_date,
        start_date=range_.start_date,
        end_date=range_.end_date,
        dau=dau,
        mau=mau,
        daily_dau=_fill_daily_metrics(range_.start_date, range_.end_date, daily_dau),
        daily_new_users=_fill_daily_metrics(range_.start_date, range_.end_date, daily_new_users),
    )


def _upsert_daily_activity(
    db: Session,
    *,
    user_id: int,
    occurred_at: datetime,
) -> None:
    activity_date = occurred_at.date()
    activity = db.scalar(
        select(UserDailyActivity).where(
            UserDailyActivity.user_id == user_id,
            UserDailyActivity.activity_date == activity_date,
        )
    )
    if activity is None:
        db.add(
            UserDailyActivity(
                user_id=user_id,
                activity_date=activity_date,
                first_seen_at=occurred_at,
                last_seen_at=occurred_at,
                event_count=1,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        db.flush()
        return

    activity.last_seen_at = occurred_at
    activity.event_count += 1
    activity.updated_at = occurred_at
    db.flush()


def _update_daily_activity(
    db: Session,
    *,
    user_id: int,
    occurred_at: datetime,
) -> None:
    activity = db.scalar(
        select(UserDailyActivity).where(
            UserDailyActivity.user_id == user_id,
            UserDailyActivity.activity_date == occurred_at.date(),
        )
    )
    if activity is None:
        _upsert_daily_activity(db, user_id=user_id, occurred_at=occurred_at)
        return
    activity.last_seen_at = occurred_at
    activity.event_count += 1
    activity.updated_at = occurred_at
    db.flush()


def _resolve_activity_date_range(
    *,
    as_of_date: date | None,
    start_date: date | None,
    end_date: date | None,
) -> ActivityDateRange:
    resolved_as_of = as_of_date or end_date or datetime.now(UTC).date()
    resolved_end = end_date or resolved_as_of
    resolved_start = start_date or resolved_end - timedelta(days=29)
    if resolved_start > resolved_end:
        raise ActivityStatsRangeError("start_date must be on or before end_date.")
    if resolved_as_of < resolved_start or resolved_as_of > resolved_end:
        raise ActivityStatsRangeError("as_of_date must be within the requested date range.")
    if (resolved_end - resolved_start).days + 1 > MAX_ACTIVITY_STATS_DAYS:
        raise ActivityStatsRangeError(
            f"Date range cannot exceed {MAX_ACTIVITY_STATS_DAYS} days."
        )
    return ActivityDateRange(
        start_date=resolved_start,
        end_date=resolved_end,
        as_of_date=resolved_as_of,
    )


def _daily_activity_counts(db: Session, start_date: date, end_date: date) -> dict[date, int]:
    rows = db.execute(
        select(
            UserDailyActivity.activity_date,
            func.count(UserDailyActivity.user_id.distinct()),
        )
        .where(
            UserDailyActivity.activity_date >= start_date,
            UserDailyActivity.activity_date <= end_date,
        )
        .group_by(UserDailyActivity.activity_date)
    )
    return {row[0]: int(row[1] or 0) for row in rows}


def _daily_new_user_counts(db: Session, start_date: date, end_date: date) -> dict[date, int]:
    created_date = func.date(User.created_at)
    start_at = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
    rows = db.execute(
        select(
            created_date,
            func.count(User.id),
        )
        .where(
            User.role == UserRole.USER,
            User.created_at >= start_at,
            User.created_at < end_at,
        )
        .group_by(created_date)
    )
    return {_coerce_date(row[0]): int(row[1] or 0) for row in rows}


def _fill_daily_metrics(
    start_date: date,
    end_date: date,
    counts: dict[date, int],
) -> list[DailyMetric]:
    days = (end_date - start_date).days
    return [
        DailyMetric(
            date=start_date + timedelta(days=offset),
            count=counts.get(start_date + timedelta(days=offset), 0),
        )
        for offset in range(days + 1)
    ]


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
