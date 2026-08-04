from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.users.models import User, UserRole, UserStatus


class UserServiceError(ValueError):
    pass


class UserAlreadyExistsError(UserServiceError):
    pass


def normalize_username(username: str) -> str:
    normalized = unicodedata.normalize("NFKC", username).strip().casefold()
    if not normalized:
        raise UserServiceError("Username must not be blank.")
    if len(normalized) > 64:
        raise UserServiceError("Username must not exceed 64 characters.")
    if any(char.isspace() or unicodedata.category(char).startswith("C") for char in normalized):
        raise UserServiceError("Username must not contain whitespace or control characters.")
    return normalized


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise UserServiceError("Password must be at least 8 characters.")
    if len(password) > 128:
        raise UserServiceError("Password must not exceed 128 characters.")
    return password


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = normalize_username(username)
    return db.scalar(select(User).where(User.username == normalized))


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: UserRole = UserRole.USER,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    normalized_username = normalize_username(username)
    validated_password = validate_password(password)
    if db.scalar(select(User.id).where(User.username == normalized_username)) is not None:
        raise UserAlreadyExistsError("Username already exists.")

    user = User(
        username=normalized_username,
        password_hash=hash_password(validated_password),
        role=role,
        status=status,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError("Username already exists.") from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, username: str, password: str) -> User | None:
    try:
        user = get_user_by_username(db, username)
    except UserServiceError:
        return None

    if user is None or not verify_password(password, user.password_hash):
        return None
    if user.status != UserStatus.ACTIVE:
        return None
    return user
