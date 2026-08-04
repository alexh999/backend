from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from pydantic import SecretStr
from pwdlib import PasswordHash

from app.core.config import Settings


class SecurityConfigurationError(ValueError):
    """Raised when security configuration is missing or invalid."""


class TokenValidationError(ValueError):
    """Raised when an access token cannot be trusted."""


_password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(plain_password, password_hash)
    except Exception:
        return False


def create_access_token(
    user_id: int,
    settings: Settings,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    secret = _get_jwt_secret(settings)
    now = datetime.now(timezone.utc)
    expires_delta = expires_delta or timedelta(
        minutes=settings.jwt_access_token_expire_minutes,
    )
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> int:
    secret = _get_jwt_secret(settings)
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
        )
    except (jwt.InvalidTokenError, TypeError, ValueError) as exc:
        raise TokenValidationError from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise TokenValidationError

    user_id = int(subject)
    if user_id <= 0:
        raise TokenValidationError
    return user_id


def _get_jwt_secret(settings: Settings) -> str:
    secret: SecretStr | None = settings.jwt_secret
    value = secret.get_secret_value().strip() if secret is not None else ""
    if not value:
        raise SecurityConfigurationError(
            "JWT_SECRET must be configured before authentication is used."
        )
    return value
