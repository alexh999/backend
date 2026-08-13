"""allow newsapi monitoring service

Revision ID: 0006_allow_newsapi_monitoring_service
Revises: 0005_create_system_monitoring_events
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_allow_newsapi_monitoring_service"
down_revision: Union[str, None] = "0005_create_system_monitoring_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SERVICES_WITH_NEWSAPI = ("pandaai", "ai_model", "newsapi", "backend")
SERVICES_WITHOUT_NEWSAPI = ("pandaai", "ai_model", "backend")
STATUSES = ("success", "failure")


def upgrade() -> None:
    _rebuild_sqlite_table_if_needed(SERVICES_WITH_NEWSAPI, required_value="newsapi")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    newsapi_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM system_monitoring_events "
            "WHERE service = 'newsapi'"
        )
    ).scalar()
    if newsapi_count:
        raise RuntimeError("Cannot downgrade while newsapi monitoring records exist.")
    _rebuild_sqlite_table(SERVICES_WITHOUT_NEWSAPI)


def _rebuild_sqlite_table_if_needed(
    services: tuple[str, ...],
    *,
    required_value: str,
) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    table_sql = bind.execute(
        sa.text(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'system_monitoring_events'"
        )
    ).scalar()
    if not table_sql or f"'{required_value}'" in table_sql:
        return
    _rebuild_sqlite_table(services)


def _rebuild_sqlite_table(services: tuple[str, ...]) -> None:
    bind = op.get_bind()
    existing_indexes = {
        row[1]
        for row in bind.execute(
            sa.text("PRAGMA index_list('system_monitoring_events')")
        ).fetchall()
    }
    for index_name in existing_indexes:
        if index_name.startswith("ix_system_monitoring_events_"):
            op.drop_index(index_name, table_name="system_monitoring_events")

    op.rename_table("system_monitoring_events", "system_monitoring_events_old")
    _create_monitoring_table(services)
    bind.execute(
        sa.text(
            "INSERT INTO system_monitoring_events "
            "(id, service, endpoint, status, occurred_at, duration_ms, "
            "http_status_code, error_type, error_message, created_at) "
            "SELECT id, service, endpoint, status, occurred_at, duration_ms, "
            "http_status_code, error_type, error_message, created_at "
            "FROM system_monitoring_events_old"
        )
    )
    op.drop_table("system_monitoring_events_old")
    _create_monitoring_indexes()


def _create_monitoring_table(services: tuple[str, ...]) -> None:
    op.create_table(
        "system_monitoring_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "service",
            sa.Enum(
                *services,
                name="monitoring_service_name",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                *STATUSES,
                name="monitoring_event_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_monitoring_indexes() -> None:
    for name, columns in (
        ("ix_system_monitoring_events_id", ["id"]),
        ("ix_system_monitoring_events_service", ["service"]),
        ("ix_system_monitoring_events_status", ["status"]),
        ("ix_system_monitoring_events_occurred_at", ["occurred_at"]),
        ("ix_system_monitoring_events_service_occurred_at", ["service", "occurred_at"]),
        ("ix_system_monitoring_events_status_occurred_at", ["status", "occurred_at"]),
    ):
        op.create_index(name, "system_monitoring_events", columns, unique=False)
