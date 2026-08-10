from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.service import create_user


TEST_PASSWORD = "test-only-password"
TEST_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


@pytest.fixture
def admin_context(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], Settings], None, None]:
    database_url = f"sqlite:///{tmp_path / 'admin_test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
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
    try:
        with TestClient(app) as client:
            yield client, session_factory, settings
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_user(
    session_factory: sessionmaker[Session],
    *,
    username: str,
    role: UserRole = UserRole.USER,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    with session_factory() as db:
        return create_user(
            db,
            username=username,
            password=TEST_PASSWORD,
            role=role,
            status=status,
        )


def _authorization(user: User, settings: Settings) -> dict[str, str]:
    token = create_access_token(user.id, settings)
    return {"Authorization": f"Bearer {token}"}


def test_admin_overview_returns_real_user_statistics(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin-one", role=UserRole.ADMIN)
    _create_user(session_factory, username="admin-disabled", role=UserRole.ADMIN, status=UserStatus.DISABLED)
    _create_user(session_factory, username="active-user")
    _create_user(session_factory, username="disabled-user", status=UserStatus.DISABLED)

    response = client.get("/api/v1/admin/overview", headers=_authorization(admin, settings))

    assert response.status_code == 200
    assert response.json() == {
        "users": {
            "total": 4,
            "active": 2,
            "disabled": 2,
            "admins": 2,
            "regular_users": 2,
        }
    }


def test_admin_overview_rejects_missing_and_regular_user_credentials(admin_context) -> None:
    client, session_factory, settings = admin_context
    regular_user = _create_user(session_factory, username="regular-user")

    assert client.get("/api/v1/admin/overview").status_code == 401
    assert client.get(
        "/api/v1/admin/overview",
        headers=_authorization(regular_user, settings),
    ).status_code == 403


def test_admin_users_is_paginated_sorted_and_safe(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    _create_user(session_factory, username="alpha")
    _create_user(session_factory, username="beta")

    response = client.get(
        "/api/v1/admin/users?page=1&page_size=2",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert [item["username"] for item in payload["items"]] == ["beta", "alpha"]
    for item in payload["items"]:
        assert not any("password" in field for field in item)

    out_of_range = client.get(
        "/api/v1/admin/users?page=10&page_size=2",
        headers=_authorization(admin, settings),
    )
    assert out_of_range.status_code == 200
    assert out_of_range.json()["items"] == []
    assert out_of_range.json()["total"] == 3


def test_admin_users_validates_page_size(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)

    response = client.get(
        "/api/v1/admin/users?page_size=101",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 422


def test_admin_users_searches_usernames_and_treats_blank_as_no_filter(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    _create_user(session_factory, username="alpha-one")
    _create_user(session_factory, username="second-alpha")
    _create_user(session_factory, username="beta")
    headers = _authorization(admin, settings)

    response = client.get("/api/v1/admin/users?search=ALPHA", headers=headers)
    legacy_response = client.get("/api/v1/admin/users?q=ALPHA", headers=headers)
    blank_response = client.get("/api/v1/admin/users?search=%20%20", headers=headers)

    assert response.status_code == 200
    assert legacy_response.status_code == 200
    assert {item["username"] for item in response.json()["items"]} == {
        "alpha-one",
        "second-alpha",
    }
    assert {item["username"] for item in legacy_response.json()["items"]} == {
        "alpha-one",
        "second-alpha",
    }
    assert blank_response.status_code == 200
    assert blank_response.json()["total"] == 4
    assert blank_response.json()["total_pages"] == 1


def test_admin_users_filters_by_role_status_and_combination(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    _create_user(session_factory, username="admin-disabled", role=UserRole.ADMIN, status=UserStatus.DISABLED)
    _create_user(session_factory, username="user-active")
    _create_user(session_factory, username="user-disabled", status=UserStatus.DISABLED)
    headers = _authorization(admin, settings)

    admins = client.get("/api/v1/admin/users?role=admin", headers=headers).json()
    disabled = client.get("/api/v1/admin/users?status=disabled", headers=headers).json()
    combined = client.get(
        "/api/v1/admin/users?role=user&status=disabled&search=user",
        headers=headers,
    ).json()

    assert {item["username"] for item in admins["items"]} == {"admin", "admin-disabled"}
    assert {item["username"] for item in disabled["items"]} == {"admin-disabled", "user-disabled"}
    assert [item["username"] for item in combined["items"]] == ["user-disabled"]
    assert combined["total"] == 1
    assert combined["total_pages"] == 1


@pytest.mark.parametrize("query", ["role=owner", "status=pending"])
def test_admin_users_rejects_invalid_role_or_status(admin_context, query: str) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)

    response = client.get(
        f"/api/v1/admin/users?{query}",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 422


def test_admin_users_rejects_regular_and_disabled_admin(admin_context) -> None:
    client, session_factory, settings = admin_context
    regular = _create_user(session_factory, username="regular")
    disabled_admin = _create_user(
        session_factory,
        username="disabled-admin",
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )

    assert client.get(
        "/api/v1/admin/users",
        headers=_authorization(regular, settings),
    ).status_code == 403
    assert client.get(
        "/api/v1/admin/users",
        headers=_authorization(disabled_admin, settings),
    ).status_code == 401


def test_existing_health_and_auth_me_behavior_is_unchanged(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)

    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    me_response = client.get(
        "/api/v1/auth/me",
        headers=_authorization(admin, settings),
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"
    assert "password_hash" not in me_response.json()


def test_admin_can_read_user_detail_without_sensitive_fields(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    user = _create_user(session_factory, username="detail-user")

    response = client.get(
        f"/api/v1/admin/users/{user.id}",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    assert response.json()["username"] == "detail-user"
    assert not any("password" in field for field in response.json())


def test_admin_can_disable_and_reenable_user(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    user = _create_user(session_factory, username="status-user")
    admin_headers = _authorization(admin, settings)

    disabled = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    with session_factory() as db:
        stored_user = db.get(User, user.id)
        assert stored_user is not None
        assert stored_user.status == UserStatus.DISABLED

    enabled = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"


def test_user_status_endpoints_enforce_admin_and_not_found(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    regular = _create_user(session_factory, username="regular")
    admin_headers = _authorization(admin, settings)

    assert client.get(f"/api/v1/admin/users/{regular.id}").status_code == 401
    assert client.get(
        f"/api/v1/admin/users/{regular.id}",
        headers=_authorization(regular, settings),
    ).status_code == 403
    assert client.get(
        "/api/v1/admin/users/99999",
        headers=admin_headers,
    ).status_code == 404
    assert client.patch(
        "/api/v1/admin/users/99999/status",
        json={"is_active": False},
        headers=admin_headers,
    ).status_code == 404


def test_admin_cannot_disable_self(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        json={"is_active": False},
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Administrators cannot disable their own account."


def test_disabled_user_cannot_login_or_use_old_token(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    user = _create_user(session_factory, username="status-user")
    user_headers = _authorization(user, settings)

    response = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        json={"is_active": False},
        headers=_authorization(admin, settings),
    )
    assert response.status_code == 200
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "status-user", "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 403
    assert login_response.json()["code"] == "ACCOUNT_DISABLED"
    assert client.get("/api/v1/auth/me", headers=user_headers).status_code == 401
    assert client.get("/api/v1/admin/overview", headers=user_headers).status_code == 401
