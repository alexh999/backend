from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_users_migration_upgrades_and_downgrades_isolated_database(tmp_path) -> None:
    database_path = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_path}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "users" in inspector.get_table_names()
        assert "admin_audit_logs" in inspector.get_table_names()
        assert "paper_accounts" in inspector.get_table_names()
        assert "paper_positions" in inspector.get_table_names()
        assert "paper_orders" in inspector.get_table_names()
        assert "paper_executions" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("users")} == {
            "id",
            "username",
            "password_hash",
            "role",
            "status",
            "created_at",
            "updated_at",
        }
        assert {column["name"] for column in inspector.get_columns("admin_audit_logs")} == {
            "id",
            "actor_user_id",
            "actor_username",
            "action",
            "target_user_id",
            "target_username",
            "created_at",
            "metadata",
        }
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(database_url)
    try:
        assert "users" not in inspect(engine).get_table_names()
        assert "admin_audit_logs" not in inspect(engine).get_table_names()
        assert "paper_accounts" not in inspect(engine).get_table_names()
        assert "paper_positions" not in inspect(engine).get_table_names()
        assert "paper_orders" not in inspect(engine).get_table_names()
        assert "paper_executions" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
