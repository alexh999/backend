from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.admin.schemas import (
    AdminOverviewResponse,
    AdminUserListResponse,
    AdminUserStatusUpdateRequest,
)
from app.modules.admin.service import (
    create_admin_user,
    calculate_total_pages,
    SelfDisableError,
    UserNotFoundError,
    UserServiceError,
    get_user_detail,
    get_user_statistics,
    list_users,
    update_user_status,
)
from app.modules.auth.dependencies import require_admin
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
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    try:
        user = create_admin_user(
            db,
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
            actor_id=current_admin.id,
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
    return UserResponse.model_validate(user)
