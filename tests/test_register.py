from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import verify_password
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
    client, session_factory, _ = register_context

    response = _register(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["username"] == "new-user"
    assert payload["role"] == "user"
    assert payload["status"] == "active"
    assert "password" not in payload
    assert "password_hash" not in payload
    assert "access_token" not in payload

    with session_factory() as db:
        created = db.scalar(select(User).where(User.username == "new-user"))
        assert created is not None
        assert created.role == UserRole.USER
        assert created.status == UserStatus.ACTIVE
        assert created.password_hash != TEST_PASSWORD
        assert verify_password(TEST_PASSWORD, created.password_hash)


@pytest.mark.parametrize("extra_field", ["role", "status", "password_hash"])
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
