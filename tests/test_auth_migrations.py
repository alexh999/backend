from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


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
        assert "user_daily_activities" in inspector.get_table_names()
        assert "forum_posts" in inspector.get_table_names()
        assert "paper_account_reset_events" in inspector.get_table_names()
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
        assert {column["name"] for column in inspector.get_columns("user_daily_activities")} == {
            "id",
            "user_id",
            "activity_date",
            "first_seen_at",
            "last_seen_at",
            "event_count",
            "created_at",
            "updated_at",
        }
        assert {column["name"] for column in inspector.get_columns("forum_posts")} == {
            "id",
            "author_user_id",
            "content",
            "topic_label",
            "status",
            "moderation_reason",
            "moderated_by_user_id",
            "moderated_at",
            "created_at",
            "updated_at",
        }
        paper_account_foreign_keys = inspector.get_foreign_keys("paper_accounts")
        assert any(
            foreign_key["constrained_columns"] == ["user_id"]
            and foreign_key["referred_table"] == "users"
            for foreign_key in paper_account_foreign_keys
        )
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
        assert "user_daily_activities" not in inspect(engine).get_table_names()
        assert "forum_posts" not in inspect(engine).get_table_names()
        assert "paper_account_reset_events" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_existing_forum_posts_are_approved_by_moderation_migration(tmp_path) -> None:
    database_path = tmp_path / "existing_forum_migration_test.db"
    database_url = f"sqlite:///{database_path}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "0006_allow_newsapi_monitoring_service")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, username, password_hash, role, status, created_at, updated_at) "
                    "VALUES (1, 'legacy-author', 'not-a-real-hash', 'user', 'active', "
                    "'2026-08-01 00:00:00', '2026-08-01 00:00:00')"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE forum_posts ("
                    "id INTEGER PRIMARY KEY, author_user_id INTEGER NOT NULL, content TEXT NOT NULL, "
                    "topic_label VARCHAR(32) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, "
                    "FOREIGN KEY(author_user_id) REFERENCES users(id))"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO forum_posts "
                    "(id, author_user_id, content, topic_label, created_at, updated_at) "
                    "VALUES (1, 1, 'Legacy public post', 'General', "
                    "'2026-08-01 00:00:00', '2026-08-01 00:00:00')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            status = connection.execute(
                text("SELECT status FROM forum_posts WHERE id = 1")
            ).scalar_one()
        assert status == "APPROVED"
        assert any(
            foreign_key["constrained_columns"] == ["moderated_by_user_id"]
            and foreign_key["referred_table"] == "users"
            for foreign_key in inspect(engine).get_foreign_keys("forum_posts")
        )
    finally:
        engine.dispose()

    command.downgrade(config, "0006_allow_newsapi_monitoring_service")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "forum_posts" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("forum_posts")} == {
            "id",
            "author_user_id",
            "content",
            "topic_label",
            "created_at",
            "updated_at",
        }
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT content FROM forum_posts WHERE id = 1")
            ).scalar_one() == "Legacy public post"
    finally:
        engine.dispose()
