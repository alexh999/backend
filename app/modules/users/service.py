from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.users.models import USERNAME_MAX_LENGTH, User, UserRole, UserStatus


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class UserServiceError(ValueError):
    pass


class UserAlreadyExistsError(UserServiceError):
    pass


class AccountDisabledError(UserServiceError):
    pass


def normalize_username(username: str) -> str:
    normalized = unicodedata.normalize("NFKC", username).strip().casefold()
    if not normalized:
        raise UserServiceError("Username must not be blank.")
    if len(normalized) > USERNAME_MAX_LENGTH:
        raise UserServiceError(f"Username must not exceed {USERNAME_MAX_LENGTH} characters.")
    if any(char.isspace() or unicodedata.category(char).startswith("C") for char in normalized):
        raise UserServiceError("Username must not contain whitespace or control characters.")
    return normalized


def validate_password(password: str) -> str:
    if not password.strip():
        raise UserServiceError("Password must not be blank.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise UserServiceError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise UserServiceError(f"Password must not exceed {PASSWORD_MAX_LENGTH} characters.")
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
    commit: bool = True,
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
        db.flush()
        if commit:
            db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError("Username already exists.") from exc
    if commit:
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
        raise AccountDisabledError("Account is disabled.")
    return user
