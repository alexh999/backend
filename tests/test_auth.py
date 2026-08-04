from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.auth.dependencies import require_admin
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.service import create_user


TEST_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


@pytest.fixture
def auth_context(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'auth_test.db'}"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    settings = Settings(
        cors_origins="",
        database_url=database_url,
        jwt_secret=SecretStr("test-only-jwt-secret-that-is-not-used-in-production"),
        jwt_algorithm="HS256",
        siliconflow_model=TEST_MODEL,
    )
    app = create_app(settings)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/test-admin")
    def admin_probe(
        _: Annotated[User, Depends(require_admin)],
    ) -> dict[str, bool]:
        return {"ok": True}

    try:
        with TestClient(app) as client:
            yield client, session_factory, settings
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_test_user(
    session_factory,
    *,
    username: str,
    password: str = "correct horse battery staple",
    role: UserRole = UserRole.USER,
) -> User:
    db: Session = session_factory()
    try:
        return create_user(
            db,
            username=username,
            password=password,
            role=role,
        )
    finally:
        db.close()


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_passwords_are_hashed_and_verifiable() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_login_and_me_return_safe_user_fields(auth_context) -> None:
    client, session_factory, _ = auth_context
    _create_test_user(session_factory, username="Alice")

    token = _login(client, "ALICE", "correct horse battery staple")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "alice"
    assert payload["role"] == "user"
    assert payload["status"] == "active"
    assert "password_hash" not in payload


def test_invalid_missing_expired_and_disabled_credentials_are_rejected(auth_context) -> None:
    client, session_factory, settings = auth_context
    user = _create_test_user(session_factory, username="disabled-user")

    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    ).status_code == 401

    expired_token = create_access_token(
        user.id,
        settings,
        expires_delta=timedelta(seconds=-1),
    )
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    ).status_code == 401

    db: Session = session_factory()
    try:
        stored_user = db.get(User, user.id)
        assert stored_user is not None
        stored_user.status = UserStatus.DISABLED
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "disabled-user", "password": "correct horse battery staple"},
    )
    assert response.status_code == 401


def test_login_reports_missing_jwt_configuration_without_exposing_details(auth_context) -> None:
    client, session_factory, settings = auth_context
    _create_test_user(session_factory, username="configured-later")
    settings.jwt_secret = None

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "configured-later",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service is not configured."}


def test_admin_dependency_uses_current_database_role(auth_context) -> None:
    client, session_factory, _ = auth_context
    regular_user = _create_test_user(session_factory, username="regular")
    admin_user = _create_test_user(
        session_factory,
        username="admin",
        role=UserRole.ADMIN,
    )

    regular_token = _login(client, "regular", "correct horse battery staple")
    admin_token = _login(client, "admin", "correct horse battery staple")

    assert client.get(
        "/test-admin",
        headers={"Authorization": f"Bearer {regular_token}"},
    ).status_code == 403
    assert client.get(
        "/test-admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).status_code == 200

    db: Session = session_factory()
    try:
        stored_admin = db.get(User, admin_user.id)
        assert stored_admin is not None
        stored_admin.role = UserRole.USER
        db.commit()
    finally:
        db.close()

    assert client.get(
        "/test-admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).status_code == 403
    assert regular_user.id != admin_user.id


def test_existing_health_and_quant_routes_remain_public(auth_context) -> None:
    client, _, _ = auth_context

    assert client.get("/api/v1/health").status_code == 200
    response = client.post("/api/v1/quant/technical-summary", json=[])

    assert response.status_code == 200


def test_duplicate_usernames_fail_after_normalization(auth_context) -> None:
    _, session_factory, _ = auth_context
    _create_test_user(session_factory, username="Duplicate")

    db: Session = session_factory()
    try:
        with pytest.raises(Exception, match="Username already exists"):
            create_user(
                db,
                username=" duplicate ",
                password="another correct password",
            )
    finally:
        db.close()
