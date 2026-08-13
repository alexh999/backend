"""create system monitoring events

Revision ID: 0005_create_system_monitoring_events
Revises: 0004_create_user_daily_activities
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_create_system_monitoring_events"
down_revision: Union[str, None] = "0004_create_user_daily_activities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "system_monitoring_events" not in existing_tables:
        op.create_table(
            "system_monitoring_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "service",
                sa.Enum(
                    "pandaai",
                    "ai_model",
                    "newsapi",
                    "backend",
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
                    "success",
                    "failure",
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
        op.create_index(
            "ix_system_monitoring_events_id",
            "system_monitoring_events",
            ["id"],
            unique=False,
        )
        op.create_index(
            "ix_system_monitoring_events_service",
            "system_monitoring_events",
            ["service"],
            unique=False,
        )
        op.create_index(
            "ix_system_monitoring_events_status",
            "system_monitoring_events",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_system_monitoring_events_occurred_at",
            "system_monitoring_events",
            ["occurred_at"],
            unique=False,
        )
        op.create_index(
            "ix_system_monitoring_events_service_occurred_at",
            "system_monitoring_events",
            ["service", "occurred_at"],
            unique=False,
        )
        op.create_index(
            "ix_system_monitoring_events_status_occurred_at",
            "system_monitoring_events",
            ["status", "occurred_at"],
            unique=False,
        )
    else:
        _ensure_newsapi_service_allowed()


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "system_monitoring_events" in existing_tables:
        op.drop_index(
            "ix_system_monitoring_events_status_occurred_at",
            table_name="system_monitoring_events",
        )
        op.drop_index(
            "ix_system_monitoring_events_service_occurred_at",
            table_name="system_monitoring_events",
        )
        op.drop_index(
            "ix_system_monitoring_events_occurred_at",
            table_name="system_monitoring_events",
        )
        op.drop_index("ix_system_monitoring_events_status", table_name="system_monitoring_events")
        op.drop_index("ix_system_monitoring_events_service", table_name="system_monitoring_events")
        op.drop_index("ix_system_monitoring_events_id", table_name="system_monitoring_events")
        op.drop_table("system_monitoring_events")


def _ensure_newsapi_service_allowed() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    table_sql = bind.execute(
        sa.text(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'system_monitoring_events'"
        )
    ).scalar()
    if not table_sql or "'newsapi'" in table_sql:
        return

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
    op.create_table(
        "system_monitoring_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "service",
            sa.Enum(
                "pandaai",
                "ai_model",
                "newsapi",
                "backend",
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
                "success",
                "failure",
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
    op.create_index(
        "ix_system_monitoring_events_id",
        "system_monitoring_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_system_monitoring_events_service",
        "system_monitoring_events",
        ["service"],
        unique=False,
    )
    op.create_index(
        "ix_system_monitoring_events_status",
        "system_monitoring_events",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_system_monitoring_events_occurred_at",
        "system_monitoring_events",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_system_monitoring_events_service_occurred_at",
        "system_monitoring_events",
        ["service", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_system_monitoring_events_status_occurred_at",
        "system_monitoring_events",
        ["status", "occurred_at"],
        unique=False,
    )
