from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.service import UserAlreadyExistsError, create_user


TEST_PASSWORD = "registration-test-password"
TEST_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


@pytest.fixture
def register_context(
    tmp_path,
) -> Generator[tuple[TestClient, sessionmaker[Session], Settings], None, None]:
    database_url = f"sqlite:///{tmp_path / 'register_test.db'}"
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


def _register(client: TestClient, username: str = "new-user", password: str = TEST_PASSWORD):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )


def _login(client: TestClient, username: str, password: str = TEST_PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_register_creates_safe_active_regular_user(register_context) -> None:
    client, _, _ = register_context

    response = _register(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["username"] == "new-user"
    assert payload["role"] == "user"
    assert payload["status"] == "active"
    assert "password" not in payload
    assert "password_hash" not in payload
    assert "access_token" not in payload


@pytest.mark.parametrize("extra_field", ["role", "status", "password_hash", "is_admin"])
def test_register_rejects_privileged_or_internal_fields(register_context, extra_field: str) -> None:
    client, _, _ = register_context
    payload = {"username": "new-user", "password": TEST_PASSWORD, extra_field: "admin"}

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("short-password", "1234567"),
        ("long-password", "x" * 129),
        ("blank-password", "        "),
        ("   ", TEST_PASSWORD),
    ],
)
def test_register_rejects_invalid_username_or_password(
    register_context,
    username: str,
    password: str,
) -> None:
    client, _, _ = register_context

    response = _register(client, username=username, password=password)

    assert response.status_code == 422
    assert "password_hash" not in response.text


def test_register_normalizes_username_and_rejects_normalized_duplicate(register_context) -> None:
    client, _, _ = register_context

    first = _register(client, username="  MixedCase  ")
    duplicate = _register(client, username="mixedcase")

    assert first.status_code == 201
    assert first.json()["username"] == "mixedcase"
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Username already exists."}


def test_create_user_rolls_back_integrity_error_race(register_context, monkeypatch) -> None:
    _, session_factory, _ = register_context
    with session_factory() as db:
        create_user(db, username="race-user", password=TEST_PASSWORD)

    with session_factory() as db:
        monkeypatch.setattr(db, "scalar", lambda _statement: None)
        with pytest.raises(UserAlreadyExistsError, match="Username already exists"):
            create_user(db, username="race-user", password=TEST_PASSWORD)
        assert not db.in_transaction()


def test_registered_user_can_login_and_read_auth_me(register_context) -> None:
    client, _, _ = register_context
    assert _register(client, username="login-user").status_code == 201

    token = _login(client, " LOGIN-USER ")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "login-user"
    assert response.json()["role"] == "user"


def test_registered_user_cannot_access_admin_endpoints(register_context) -> None:
    client, _, _ = register_context
    assert _register(client, username="regular-user").status_code == 201
    token = _login(client, "regular-user")
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/admin/overview", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403


def test_registered_user_appears_in_admin_users_and_overview(register_context) -> None:
    client, session_factory, settings = register_context
    assert _register(client, username="visible-user").status_code == 201
    with session_factory() as db:
        admin = create_user(
            db,
            username="local-admin",
            password=TEST_PASSWORD,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        admin_id = admin.id

    from app.core.security import create_access_token

    token = create_access_token(admin_id, settings)
    headers = {"Authorization": f"Bearer {token}"}
    users_response = client.get("/api/v1/admin/users?q=visible-user", headers=headers)
    overview_response = client.get("/api/v1/admin/overview", headers=headers)

    assert users_response.status_code == 200
    assert [item["username"] for item in users_response.json()["items"]] == ["visible-user"]
    assert overview_response.status_code == 200
    assert overview_response.json()["users"] == {
        "total": 2,
        "active": 2,
        "disabled": 0,
        "admins": 1,
        "regular_users": 1,
    }


def test_create_admin_uses_shared_creation_and_password_rules(register_context, monkeypatch) -> None:
    _, session_factory, settings = register_context
    from app.scripts import create_admin

    passwords = iter([TEST_PASSWORD, TEST_PASSWORD])
    monkeypatch.setattr(create_admin, "get_settings", lambda: settings)
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt: next(passwords))
    monkeypatch.setattr("sys.argv", ["create_admin", "--username", "ScriptAdmin"])

    assert create_admin.main() == 0
    with session_factory() as db:
        created = db.scalar(select(User).where(User.username == "scriptadmin"))
        assert created is not None
        assert created.role == UserRole.ADMIN
        assert created.status == UserStatus.ACTIVE
        assert created.password_hash != TEST_PASSWORD


def test_existing_public_health_route_remains_public(register_context) -> None:
    client, _, _ = register_context

    assert client.get("/api/v1/health").status_code == 200
