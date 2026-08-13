from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.admin import service as admin_service
from app.modules.admin.models import AdminAuditAction, AdminAuditLog
from app.modules.forum.models import ForumContentStatus, ForumPost
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


def _audit_log_count(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        return int(db.scalar(select(func.count(AdminAuditLog.id))) or 0)


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


def test_admin_can_create_another_admin_and_login(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    headers = _authorization(admin, settings)

    response = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin", "password": "secure-password"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["username"] == "new-admin"
    assert payload["role"] == "admin"
    assert payload["status"] == "active"
    assert "password_hash" not in payload

    with session_factory() as db:
        stored_user = db.get(User, payload["id"])
        assert stored_user is not None
        assert stored_user.role == UserRole.ADMIN
        assert stored_user.status == UserStatus.ACTIVE
        assert stored_user.password_hash != "secure-password"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "new-admin", "password": "secure-password"},
    )
    assert login_response.status_code == 200
    token_response = login_response.json()
    assert token_response["token_type"] == "bearer"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_response['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "new-admin"
    assert me_response.json()["role"] == "admin"


def test_admin_create_admin_validates_permissions_and_payload(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    regular = _create_user(session_factory, username="regular")
    disabled_admin = _create_user(
        session_factory,
        username="disabled-admin",
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )

    assert client.post("/api/v1/admin/users/admins").status_code == 401
    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin", "password": "secure-password"},
        headers=_authorization(regular, settings),
    ).status_code == 403
    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin", "password": "secure-password"},
        headers=_authorization(disabled_admin, settings),
    ).status_code == 401

    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": " ", "password": "secure-password"},
        headers=_authorization(admin, settings),
    ).status_code == 422
    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin-2", "password": "short"},
        headers=_authorization(admin, settings),
    ).status_code == 422
    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin-3", "password": "secure-password", "role": "user"},
        headers=_authorization(admin, settings),
    ).status_code == 422


def test_admin_create_admin_rejects_duplicate_username(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    _create_user(session_factory, username="existing-admin", role=UserRole.ADMIN)

    response = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "existing-admin", "password": "secure-password"},
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already exists."


def test_admin_can_create_another_admin_and_login(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    headers = _authorization(admin, settings)

    response = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin", "password": "secure-password"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["username"] == "new-admin"
    assert payload["role"] == "admin"
    assert payload["status"] == "active"
    assert "password_hash" not in payload

    with session_factory() as db:
        stored_user = db.get(User, payload["id"])
        assert stored_user is not None
        assert stored_user.role == UserRole.ADMIN
        assert stored_user.status == UserStatus.ACTIVE
        assert stored_user.password_hash != "secure-password"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "new-admin", "password": "secure-password"},
    )
    assert login_response.status_code == 200
    token_response = login_response.json()
    assert token_response["token_type"] == "bearer"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_response['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "new-admin"
    assert me_response.json()["role"] == "admin"


def test_admin_create_admin_validates_permissions_and_payload(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    regular = _create_user(session_factory, username="regular")
    disabled_admin = _create_user(
        session_factory,
        username="disabled-admin",
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )

    assert client.post("/api/v1/admin/users/admins").status_code == 401
    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin", "password": "secure-password"},
        headers=_authorization(regular, settings),
    ).status_code == 403
    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin", "password": "secure-password"},
        headers=_authorization(disabled_admin, settings),
    ).status_code == 401

    response = client.post(
        "/api/v1/admin/users/admins",
        json={"username": " ", "password": "secure-password"},
        headers=_authorization(admin, settings),
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin-2", "password": "short"},
        headers=_authorization(admin, settings),
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "new-admin-3", "password": "secure-password", "role": "user"},
        headers=_authorization(admin, settings),
    )
    assert response.status_code == 422


def test_admin_create_admin_rejects_duplicate_username(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    _create_user(session_factory, username="existing-admin", role=UserRole.ADMIN)

    response = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "existing-admin", "password": "secure-password"},
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already exists."


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


def test_admin_cannot_disable_last_active_admin(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        json={"is_active": False},
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Administrators cannot disable their own account."
    assert _audit_log_count(session_factory) == 0
    with session_factory() as db:
        active_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN,
                User.status == UserStatus.ACTIVE,
            )
        )
        assert active_admins == 1


def test_admin_can_disable_another_admin_when_more_than_one_active_admin_exists(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    other_admin = _create_user(session_factory, username="other-admin", role=UserRole.ADMIN)

    response = client.patch(
        f"/api/v1/admin/users/{other_admin.id}/status",
        json={"is_active": False},
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    with session_factory() as db:
        stored_user = db.get(User, other_admin.id)
        assert stored_user is not None
        assert stored_user.status == UserStatus.DISABLED


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


def test_admin_creation_and_status_changes_create_audit_logs(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="audit-admin", role=UserRole.ADMIN)
    user = _create_user(session_factory, username="audit-target")
    headers = _authorization(admin, settings)

    created_admin = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "created-admin", "password": "secure-password"},
        headers=headers,
    )
    disabled = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        json={"is_active": False},
        headers=headers,
    )
    enabled = client.patch(
        f"/api/v1/admin/users/{user.id}/status",
        json={"is_active": True},
        headers=headers,
    )

    assert created_admin.status_code == 201
    assert disabled.status_code == 200
    assert enabled.status_code == 200
    with session_factory() as db:
        logs = list(db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.id)))

    assert [log.action for log in logs] == [
        AdminAuditAction.ADMIN_CREATED,
        AdminAuditAction.USER_DISABLED,
        AdminAuditAction.USER_ENABLED,
    ]
    assert all(log.actor_user_id == admin.id and log.actor_username == "audit-admin" for log in logs)
    assert logs[0].target_username == "created-admin"
    assert logs[0].metadata_ == {"new_role": "admin", "new_status": "active"}
    assert logs[1].target_user_id == user.id
    assert logs[1].target_username == "audit-target"
    assert logs[1].metadata_ == {"previous_status": "active", "new_status": "disabled"}
    assert logs[2].metadata_ == {"previous_status": "disabled", "new_status": "active"}


def test_failed_or_rejected_admin_operations_do_not_create_audit_logs(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    regular = _create_user(session_factory, username="regular")
    headers = _authorization(admin, settings)

    duplicate = client.post(
        "/api/v1/admin/users/admins",
        json={"username": "regular", "password": "secure-password"},
        headers=headers,
    )
    missing_user = client.patch(
        "/api/v1/admin/users/999/status",
        json={"is_active": False},
        headers=headers,
    )
    self_disable = client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        json={"is_active": False},
        headers=headers,
    )
    forbidden = client.patch(
        f"/api/v1/admin/users/{regular.id}/status",
        json={"is_active": False},
        headers=_authorization(regular, settings),
    )

    assert duplicate.status_code == 409
    assert missing_user.status_code == 404
    assert self_disable.status_code == 400
    assert forbidden.status_code == 403
    assert _audit_log_count(session_factory) == 0


def test_admin_audit_logs_are_paginated_sorted_filtered_and_safe(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="root-admin", role=UserRole.ADMIN)
    target = _create_user(session_factory, username="mixed-target")
    headers = _authorization(admin, settings)

    assert client.post(
        "/api/v1/admin/users/admins",
        json={"username": "created-admin", "password": "secure-password"},
        headers=headers,
    ).status_code == 201
    assert client.patch(
        f"/api/v1/admin/users/{target.id}/status",
        json={"is_active": False},
        headers=headers,
    ).status_code == 200
    assert client.patch(
        f"/api/v1/admin/users/{target.id}/status",
        json={"is_active": True},
        headers=headers,
    ).status_code == 200

    first_page = client.get(
        "/api/v1/admin/audit-logs?page=1&page_size=2",
        headers=headers,
    )
    assert first_page.status_code == 200
    payload = first_page.json()
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert [item["action"] for item in payload["items"]] == ["USER_ENABLED", "USER_DISABLED"]
    for item in payload["items"]:
        assert "metadata" in item
        assert not any("password" in field.lower() or "token" in field.lower() for field in item)

    second_page = client.get(
        "/api/v1/admin/audit-logs?page=2&page_size=2",
        headers=headers,
    )
    assert second_page.status_code == 200
    assert [item["action"] for item in second_page.json()["items"]] == ["ADMIN_CREATED"]

    disabled_logs = client.get(
        "/api/v1/admin/audit-logs?action=USER_DISABLED",
        headers=headers,
    )
    actor_logs = client.get(
        "/api/v1/admin/audit-logs?actor_username=%20ROOT%20",
        headers=headers,
    )
    target_logs = client.get(
        "/api/v1/admin/audit-logs?target_username=%20MIXED%20",
        headers=headers,
    )
    combined = client.get(
        "/api/v1/admin/audit-logs?action=USER_ENABLED&actor_username=root&target_username=target",
        headers=headers,
    )

    assert disabled_logs.status_code == 200
    assert [item["action"] for item in disabled_logs.json()["items"]] == ["USER_DISABLED"]
    assert actor_logs.status_code == 200
    assert actor_logs.json()["total"] == 3
    assert target_logs.status_code == 200
    assert target_logs.json()["total"] == 2
    assert combined.status_code == 200
    assert combined.json()["total"] == 1
    assert combined.json()["items"][0]["metadata"] == {
        "previous_status": "disabled",
        "new_status": "active",
    }


def test_admin_audit_logs_filter_by_date_range(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    target = _create_user(session_factory, username="target")
    with session_factory() as db:
        db.add_all(
            [
                AdminAuditLog(
                    actor_user_id=admin.id,
                    actor_username=admin.username,
                    action=AdminAuditAction.USER_DISABLED,
                    target_user_id=target.id,
                    target_username=target.username,
                    created_at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
                    metadata_={"previous_status": "active", "new_status": "disabled"},
                ),
                AdminAuditLog(
                    actor_user_id=admin.id,
                    actor_username=admin.username,
                    action=AdminAuditAction.USER_ENABLED,
                    target_user_id=target.id,
                    target_username=target.username,
                    created_at=datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc),
                    metadata_={"previous_status": "disabled", "new_status": "active"},
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/admin/audit-logs?start_date=2026-08-02&end_date=2026-08-06",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["action"] == "USER_ENABLED"


def test_admin_audit_logs_do_not_return_sensitive_metadata(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    target = _create_user(session_factory, username="target")
    with session_factory() as db:
        db.add(
            AdminAuditLog(
                actor_user_id=admin.id,
                actor_username=admin.username,
                action=AdminAuditAction.USER_DISABLED,
                target_user_id=target.id,
                target_username=target.username,
                metadata_={
                    "previous_status": "active",
                    "new_status": "disabled",
                    "password_hash": "must-not-leak",
                    "token": "must-not-leak",
                },
            )
        )
        db.commit()

    response = client.get(
        "/api/v1/admin/audit-logs",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["metadata"] == {
        "previous_status": "active",
        "new_status": "disabled",
    }
    assert "must-not-leak" not in response.text


def test_user_status_change_rolls_back_when_audit_log_write_fails(admin_context, monkeypatch) -> None:
    _, session_factory, _ = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    target = _create_user(session_factory, username="target")

    def fail_audit_log(*args, **kwargs):
        raise RuntimeError("audit log write failed")

    monkeypatch.setattr(admin_service, "_add_audit_log", fail_audit_log)

    with session_factory() as db:
        actor = db.get(User, admin.id)
        stored_target = db.get(User, target.id)
        assert actor is not None
        assert stored_target is not None
        with pytest.raises(RuntimeError, match="audit log write failed"):
            admin_service.update_user_status(
                db,
                user_id=stored_target.id,
                actor=actor,
                is_active=False,
            )

    with session_factory() as db:
        stored_target = db.get(User, target.id)
        assert stored_target is not None
        assert stored_target.status == UserStatus.ACTIVE
        assert db.scalar(select(func.count(AdminAuditLog.id))) == 0


@pytest.mark.parametrize(
    "query",
    ["page=0", "page_size=101", "action=PASSWORD_CHANGED", "start_date=2026-08-05&end_date=2026-08-01"],
)
def test_admin_audit_logs_reject_invalid_query_parameters(admin_context, query: str) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)

    response = client.get(
        f"/api/v1/admin/audit-logs?{query}",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 422


def test_admin_audit_logs_reject_missing_regular_and_disabled_admin(admin_context) -> None:
    client, session_factory, settings = admin_context
    regular = _create_user(session_factory, username="regular")
    disabled_admin = _create_user(
        session_factory,
        username="disabled-admin",
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )

    assert client.get("/api/v1/admin/audit-logs").status_code == 401
    assert client.get(
        "/api/v1/admin/audit-logs",
        headers=_authorization(regular, settings),
    ).status_code == 403
    assert client.get(
        "/api/v1/admin/audit-logs",
        headers=_authorization(disabled_admin, settings),
    ).status_code == 401


def test_forum_posts_default_pending_and_are_hidden_from_public_list(admin_context) -> None:
    client, session_factory, settings = admin_context
    user = _create_user(session_factory, username="forum-user")
    headers = _authorization(user, settings)

    created = client.post(
        "/api/v1/forum/posts",
        json={"content": "<script>alert(1)</script> Real question", "topic_label": "Risk"},
        headers=headers,
    )
    public = client.get("/api/v1/forum/posts")
    mine = client.get("/api/v1/forum/me/posts", headers=headers)

    assert created.status_code == 201
    assert created.json()["status"] == "PENDING"
    assert public.status_code == 200
    assert public.json()["items"] == []
    assert mine.status_code == 200
    assert mine.json()["items"][0]["status"] == "PENDING"
    assert mine.json()["items"][0]["content"] == "<script>alert(1)</script> Real question"
    with session_factory() as db:
        post = db.scalar(select(ForumPost))
        assert post is not None
        assert post.status == ForumContentStatus.PENDING


def test_admin_content_moderation_approves_rejects_hides_and_restores_posts(admin_context) -> None:
    client, session_factory, settings = admin_context
    admin = _create_user(session_factory, username="moderator", role=UserRole.ADMIN)
    author = _create_user(session_factory, username="author")
    admin_headers = _authorization(admin, settings)
    author_headers = _authorization(author, settings)

    pending = client.post(
        "/api/v1/forum/posts",
        json={"content": "Please review this", "topic_label": "General"},
        headers=author_headers,
    ).json()

    listed = client.get(
        "/api/v1/admin/content-moderation/posts?status=PENDING&author=auth&keyword=review",
        headers=admin_headers,
    )
    hidden_while_pending = client.patch(
        f"/api/v1/admin/content-moderation/posts/{pending['id']}",
        json={"status": "HIDDEN", "reason": "Not published yet"},
        headers=admin_headers,
    )
    approved = client.patch(
        f"/api/v1/admin/content-moderation/posts/{pending['id']}",
        json={"status": "APPROVED"},
        headers=admin_headers,
    )
    public_after_approve = client.get("/api/v1/forum/posts")
    hidden_without_reason = client.patch(
        f"/api/v1/admin/content-moderation/posts/{pending['id']}",
        json={"status": "HIDDEN"},
        headers=admin_headers,
    )
    hidden = client.patch(
        f"/api/v1/admin/content-moderation/posts/{pending['id']}",
        json={"status": "HIDDEN", "reason": "Off-topic after publication"},
        headers=admin_headers,
    )
    public_after_hide = client.get("/api/v1/forum/posts")
    restored = client.patch(
        f"/api/v1/admin/content-moderation/posts/{pending['id']}",
        json={"status": "APPROVED"},
        headers=admin_headers,
    )

    rejected_source = client.post(
        "/api/v1/forum/posts",
        json={"content": "Reject me", "topic_label": "General"},
        headers=author_headers,
    ).json()
    rejected = client.patch(
        f"/api/v1/admin/content-moderation/posts/{rejected_source['id']}",
        json={"status": "REJECTED", "reason": "Contains unverifiable claim"},
        headers=admin_headers,
    )
    mine = client.get("/api/v1/forum/me/posts", headers=author_headers)

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == pending["id"]
    assert hidden_while_pending.status_code == 422
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert public_after_approve.json()["items"][0]["id"] == pending["id"]
    assert hidden_without_reason.status_code == 422
    assert hidden.status_code == 200
    assert hidden.json()["status"] == "HIDDEN"
    assert public_after_hide.json()["items"] == []
    assert restored.status_code == 200
    assert restored.json()["status"] == "APPROVED"
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["moderation_reason"] == "Contains unverifiable claim"
    mine_by_id = {item["id"]: item for item in mine.json()["items"]}
    assert mine_by_id[rejected_source["id"]]["moderation_reason"] == "Contains unverifiable claim"

    with session_factory() as db:
        logs = list(db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.id)))
    assert [log.action for log in logs] == [
        AdminAuditAction.FORUM_POST_APPROVED,
        AdminAuditAction.FORUM_POST_HIDDEN,
        AdminAuditAction.FORUM_POST_RESTORED,
        AdminAuditAction.FORUM_POST_REJECTED,
    ]
    assert logs[-1].metadata_["content_type"] == "forum_post"
    assert logs[-1].metadata_["result"] == "success"
    assert logs[-1].metadata_["reason"] == "Contains unverifiable claim"


def test_content_moderation_rejects_non_admin_credentials(admin_context) -> None:
    client, session_factory, settings = admin_context
    user = _create_user(session_factory, username="regular")

    assert client.get("/api/v1/admin/content-moderation/posts").status_code == 401
    assert client.get(
        "/api/v1/admin/content-moderation/posts",
        headers=_authorization(user, settings),
    ).status_code == 403
