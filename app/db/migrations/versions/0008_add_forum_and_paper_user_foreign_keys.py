"""add forum and paper user foreign keys

Revision ID: 0008_add_forum_and_paper_user_foreign_keys
Revises: 0007_add_forum_moderation_and_paper_reset
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_add_forum_and_paper_user_foreign_keys"
down_revision: Union[str, None] = "0007_add_forum_moderation_and_paper_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_foreign_key(inspector, "paper_accounts", "user_id"):
        with op.batch_alter_table("paper_accounts") as batch_op:
            batch_op.create_foreign_key(
                "fk_paper_accounts_user_id_users",
                "users",
                ["user_id"],
                ["id"],
            )

    inspector = sa.inspect(bind)
    if not _has_foreign_key(inspector, "forum_posts", "moderated_by_user_id"):
        with op.batch_alter_table("forum_posts") as batch_op:
            batch_op.create_foreign_key(
                "fk_forum_posts_moderated_by_user_id_users",
                "users",
                ["moderated_by_user_id"],
                ["id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_named_foreign_key(
        inspector,
        "forum_posts",
        "fk_forum_posts_moderated_by_user_id_users",
    ):
        with op.batch_alter_table("forum_posts") as batch_op:
            batch_op.drop_constraint(
                "fk_forum_posts_moderated_by_user_id_users",
                type_="foreignkey",
            )

    inspector = sa.inspect(bind)
    if _has_named_foreign_key(
        inspector,
        "paper_accounts",
        "fk_paper_accounts_user_id_users",
    ):
        with op.batch_alter_table("paper_accounts") as batch_op:
            batch_op.drop_constraint(
                "fk_paper_accounts_user_id_users",
                type_="foreignkey",
            )


def _has_foreign_key(inspector, table_name: str, column_name: str) -> bool:
    return any(
        foreign_key["constrained_columns"] == [column_name]
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _has_named_foreign_key(inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        foreign_key.get("name") == constraint_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )
