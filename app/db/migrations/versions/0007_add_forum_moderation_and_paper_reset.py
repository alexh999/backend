"""add forum moderation and paper reset

Revision ID: 0007_add_forum_moderation_and_paper_reset
Revises: 0006_allow_newsapi_monitoring_service
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_add_forum_moderation_and_paper_reset"
down_revision: Union[str, None] = "0006_allow_newsapi_monitoring_service"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FORUM_STATUSES = ("PENDING", "APPROVED", "REJECTED", "HIDDEN")
ADMIN_ACTIONS = (
    "ADMIN_CREATED",
    "USER_DISABLED",
    "USER_ENABLED",
    "FORUM_POST_APPROVED",
    "FORUM_POST_REJECTED",
    "FORUM_POST_HIDDEN",
    "FORUM_POST_RESTORED",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "forum_posts" not in existing_tables:
        op.create_table(
            "forum_posts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("topic_label", sa.String(length=32), nullable=False, server_default="Discussion"),
            sa.Column(
                "status",
                sa.Enum(
                    *FORUM_STATUSES,
                    name="forum_content_status",
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=False,
                server_default="PENDING",
            ),
            sa.Column("moderation_reason", sa.String(length=255), nullable=True),
            sa.Column("moderated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["moderated_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_forum_posts_author_user_id", "forum_posts", ["author_user_id"], unique=False)
        op.create_index("ix_forum_posts_created_at", "forum_posts", ["created_at"], unique=False)
        op.create_index("ix_forum_posts_status", "forum_posts", ["status"], unique=False)
    elif "status" not in {column["name"] for column in sa.inspect(bind).get_columns("forum_posts")}:
        op.add_column(
            "forum_posts",
            sa.Column("status", sa.String(length=16), nullable=False, server_default="APPROVED"),
        )
        op.add_column("forum_posts", sa.Column("moderation_reason", sa.String(length=255), nullable=True))
        op.add_column("forum_posts", sa.Column("moderated_by_user_id", sa.Integer(), nullable=True))
        op.add_column("forum_posts", sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_forum_posts_status", "forum_posts", ["status"], unique=False)

    paper_columns = {column["name"] for column in sa.inspect(bind).get_columns("paper_accounts")}
    if "user_id" not in paper_columns:
        op.add_column("paper_accounts", sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_index("ix_paper_accounts_user_id", "paper_accounts", ["user_id"], unique=True)

    if "paper_account_reset_events" not in existing_tables:
        op.create_table(
            "paper_account_reset_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("result", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_paper_account_reset_events_account_id", "paper_account_reset_events", ["account_id"], unique=False)
        op.create_index("ix_paper_account_reset_events_id", "paper_account_reset_events", ["id"], unique=False)
        op.create_index("ix_paper_account_reset_events_user_id", "paper_account_reset_events", ["user_id"], unique=False)

    _rebuild_admin_audit_log_actions_if_needed()


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    if "paper_account_reset_events" in existing_tables:
        op.drop_index("ix_paper_account_reset_events_user_id", table_name="paper_account_reset_events")
        op.drop_index("ix_paper_account_reset_events_id", table_name="paper_account_reset_events")
        op.drop_index("ix_paper_account_reset_events_account_id", table_name="paper_account_reset_events")
        op.drop_table("paper_account_reset_events")
    paper_columns = {column["name"] for column in sa.inspect(bind).get_columns("paper_accounts")}
    if "user_id" in paper_columns:
        op.drop_index("ix_paper_accounts_user_id", table_name="paper_accounts")
        op.drop_column("paper_accounts", "user_id")
    if "forum_posts" in existing_tables:
        status_column = next(
            (
                column
                for column in sa.inspect(bind).get_columns("forum_posts")
                if column["name"] == "status"
            ),
            None,
        )
        status_default = str(status_column.get("default") or "") if status_column else ""
        if "APPROVED" in status_default:
            with op.batch_alter_table("forum_posts") as batch_op:
                batch_op.drop_index("ix_forum_posts_status")
                batch_op.drop_column("moderated_at")
                batch_op.drop_column("moderated_by_user_id")
                batch_op.drop_column("moderation_reason")
                batch_op.drop_column("status")
        else:
            op.drop_index("ix_forum_posts_status", table_name="forum_posts")
            op.drop_index("ix_forum_posts_created_at", table_name="forum_posts")
            op.drop_index("ix_forum_posts_author_user_id", table_name="forum_posts")
            op.drop_table("forum_posts")


def _rebuild_admin_audit_log_actions_if_needed() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    table_sql = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='admin_audit_logs'")
    ).scalar()
    if not table_sql or "FORUM_POST_APPROVED" in table_sql:
        return
    indexes = {
        row[1]
        for row in bind.execute(sa.text("PRAGMA index_list('admin_audit_logs')")).fetchall()
    }
    for index_name in indexes:
        if index_name.startswith("ix_admin_audit_logs_"):
            op.drop_index(index_name, table_name="admin_audit_logs")
    op.rename_table("admin_audit_logs", "admin_audit_logs_old")
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_username", sa.String(length=64), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                *ADMIN_ACTIONS,
                name="admin_audit_action",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("target_username", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO admin_audit_logs "
            "(id, actor_user_id, actor_username, action, target_user_id, target_username, created_at, metadata) "
            "SELECT id, actor_user_id, actor_username, action, target_user_id, target_username, created_at, metadata "
            "FROM admin_audit_logs_old"
        )
    )
    op.drop_table("admin_audit_logs_old")
    for name, columns in (
        ("ix_admin_audit_logs_action", ["action"]),
        ("ix_admin_audit_logs_actor_user_id", ["actor_user_id"]),
        ("ix_admin_audit_logs_actor_username", ["actor_username"]),
        ("ix_admin_audit_logs_created_at", ["created_at"]),
        ("ix_admin_audit_logs_target_user_id", ["target_user_id"]),
        ("ix_admin_audit_logs_target_username", ["target_username"]),
    ):
        op.create_index(name, "admin_audit_logs", columns, unique=False)
