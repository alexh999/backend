"""create user daily activities

Revision ID: 0004_create_user_daily_activities
Revises: 0003_create_paper_trading_tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_create_user_daily_activities"
down_revision: Union[str, None] = "0003_create_paper_trading_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "user_daily_activities" not in existing_tables:
        op.create_table(
            "user_daily_activities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("activity_date", sa.Date(), nullable=False),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("event_count", sa.Integer(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "activity_date",
                name="uq_user_daily_activities_user_date",
            ),
        )
        op.create_index(
            "ix_user_daily_activities_activity_date",
            "user_daily_activities",
            ["activity_date"],
            unique=False,
        )
        op.create_index(
            "ix_user_daily_activities_user_id",
            "user_daily_activities",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "user_daily_activities" in existing_tables:
        op.drop_index(
            "ix_user_daily_activities_user_id",
            table_name="user_daily_activities",
        )
        op.drop_index(
            "ix_user_daily_activities_activity_date",
            table_name="user_daily_activities",
        )
        op.drop_table("user_daily_activities")
