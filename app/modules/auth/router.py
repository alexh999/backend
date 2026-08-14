from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import SecurityConfigurationError, create_access_token
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    AuthErrorResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.service import (
    AccountDisabledError,
    UserAlreadyExistsError,
    UserServiceError,
    authenticate_user,
    create_user,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    try:
        user = create_user(
            db,
            username=request.username,
            password=request.password,
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        ) from exc
    except UserServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={status.HTTP_403_FORBIDDEN: {"model": AuthErrorResponse}},
)
def login(
    request: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        user = authenticate_user(
            db,
            username=request.username,
            password=request.password,
        )
    except AccountDisabledError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "code": "ACCOUNT_DISABLED",
                "detail": "Account is disabled.",
            },
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        access_token = create_access_token(user.id, settings)
    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured.",
        ) from exc

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)
