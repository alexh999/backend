from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.activity.service import ActivityStatsRangeError, get_user_activity_summary
from app.modules.admin.models import AdminAuditAction
from app.modules.admin.schemas import (
    AdminAuditLogListResponse,
    AdminContentModerationListResponse,
    AdminContentModerationRequest,
    AdminOverviewResponse,
    AdminSystemMonitoringResponse,
    AdminUserActivitySummaryResponse,
    AdminUserListResponse,
    AdminUserStatusUpdateRequest,
)
from app.modules.admin.service import (
    LastActiveAdminError,
    SelfDisableError,
    UserNotFoundError,
    UserServiceError,
    calculate_total_pages,
    create_admin_user,
    get_user_detail,
    get_user_statistics,
    list_content_moderation_posts,
    list_audit_logs,
    list_users,
    moderate_forum_post,
    update_user_status,
)
from app.modules.auth.dependencies import require_admin
from app.modules.forum.models import ForumContentStatus
from app.modules.forum.schemas import ForumPostResponse
from app.modules.forum.service import ForumModerationError, ForumPostNotFoundError, to_post_response
from app.modules.monitoring.schemas import MonitoringWindow
from app.modules.monitoring.service import get_system_monitoring_summary
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.schemas import UserCreateRequest, UserResponse
from app.modules.users.service import UserAlreadyExistsError


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewResponse)
def read_admin_overview(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> AdminOverviewResponse:
    return AdminOverviewResponse(users=get_user_statistics(db))


@router.get("/user-activity-summary", response_model=AdminUserActivitySummaryResponse)
def read_admin_user_activity_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AdminUserActivitySummaryResponse:
    try:
        return AdminUserActivitySummaryResponse.model_validate(
            get_user_activity_summary(
                db,
                as_of_date=as_of_date,
                start_date=start_date,
                end_date=end_date,
            ).model_dump()
        )
    except ActivityStatsRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("/system-monitoring", response_model=AdminSystemMonitoringResponse)
def read_admin_system_monitoring(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    window: MonitoringWindow = Query(default="24h"),
) -> AdminSystemMonitoringResponse:
    return AdminSystemMonitoringResponse.model_validate(
        get_system_monitoring_summary(db, window=window).model_dump()
    )


@router.get("/content-moderation/posts", response_model=AdminContentModerationListResponse)
def read_admin_content_moderation_posts(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    moderation_status: Annotated[ForumContentStatus | None, Query(alias="status")] = None,
    author: Annotated[str | None, Query(max_length=64)] = None,
    keyword: Annotated[str | None, Query(max_length=120)] = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AdminContentModerationListResponse:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_date must be on or before end_date.",
        )
    result = list_content_moderation_posts(
        db,
        page=page,
        page_size=page_size,
        status=moderation_status,
        author=author,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    return AdminContentModerationListResponse(
        items=[to_post_response(post) for post in result.items],
        total=result.total,
        total_pages=calculate_total_pages(result.total, page_size),
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/content-moderation/posts/{post_id}",
    response_model=ForumPostResponse,
    response_model_by_alias=False,
)
def update_admin_content_moderation_post(
    post_id: Annotated[int, Path(ge=1)],
    request: AdminContentModerationRequest,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        post = moderate_forum_post(
            db,
            post_id=post_id,
            actor=current_admin,
            status=request.status,
            reason=request.reason,
        )
    except ForumPostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ForumModerationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return to_post_response(post)


@router.get("/users", response_model=AdminUserListResponse)
def read_admin_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=64)] = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
    role: UserRole | None = None,
    status: UserStatus | None = None,
) -> AdminUserListResponse:
    query = search if search is not None else q
    result = list_users(
        db,
        page=page,
        page_size=page_size,
        query=query,
        role=role,
        status=status,
    )
    return AdminUserListResponse(
        items=result.items,
        total=result.total,
        total_pages=calculate_total_pages(result.total, page_size),
        page=page,
        page_size=page_size,
    )


@router.post("/users/admins", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_admin_account(
    request: UserCreateRequest,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    try:
        user = create_admin_user(
            db,
            actor=current_admin,
            username=request.username,
            password=request.password,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except UserServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
def read_admin_user(
    user_id: Annotated[int, Path(ge=1)],
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    user = get_user_detail(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_admin_user_status(
    user_id: Annotated[int, Path(ge=1)],
    request: AdminUserStatusUpdateRequest,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    try:
        user = update_user_status(
            db,
            user_id=user_id,
            actor=current_admin,
            is_active=request.is_active,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SelfDisableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LastActiveAdminError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return UserResponse.model_validate(user)


@router.get(
    "/audit-logs",
    response_model=AdminAuditLogListResponse,
    response_model_by_alias=False,
)
def read_admin_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    action: AdminAuditAction | None = None,
    actor_username: Annotated[str | None, Query(max_length=64)] = None,
    target_username: Annotated[str | None, Query(max_length=64)] = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AdminAuditLogListResponse:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_date must be on or before end_date.",
        )
    result = list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        action=action,
        actor_username=actor_username,
        target_username=target_username,
        start_date=start_date,
        end_date=end_date,
    )
    return AdminAuditLogListResponse(
        items=result.items,
        total=result.total,
        total_pages=calculate_total_pages(result.total, page_size),
        page=page,
        page_size=page_size,
    )
