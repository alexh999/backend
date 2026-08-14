"""create admin audit logs table

Revision ID: 0002_create_admin_audit_logs
Revises: 0001_create_users
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_create_admin_audit_logs"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_username", sa.String(length=64), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "ADMIN_CREATED",
                "USER_DISABLED",
                "USER_ENABLED",
                name="admin_audit_action",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("target_username", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])
    op.create_index("ix_admin_audit_logs_actor_username", "admin_audit_logs", ["actor_username"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])
    op.create_index("ix_admin_audit_logs_target_user_id", "admin_audit_logs", ["target_user_id"])
    op.create_index("ix_admin_audit_logs_target_username", "admin_audit_logs", ["target_username"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_target_username", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_target_user_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_actor_username", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_actor_user_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
