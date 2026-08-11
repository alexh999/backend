"""create paper trading tables

Revision ID: 0003_create_paper_trading_tables
Revises: 0002_create_admin_audit_logs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_create_paper_trading_tables"
down_revision: Union[str, None] = "0002_create_admin_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "paper_accounts" not in existing_tables:
        op.create_table(
            "paper_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_key", sa.String(length=64), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("initial_cash", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("available_cash", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_paper_accounts_account_key", "paper_accounts", ["account_key"], unique=True)
        op.create_index("ix_paper_accounts_id", "paper_accounts", ["id"], unique=False)

    if "paper_orders" not in existing_tables:
        op.create_table(
            "paper_orders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("side", sa.String(length=8), nullable=False),
            sa.Column("order_type", sa.String(length=16), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_paper_orders_account_id", "paper_orders", ["account_id"], unique=False)
        op.create_index("ix_paper_orders_id", "paper_orders", ["id"], unique=False)
        op.create_index("ix_paper_orders_symbol", "paper_orders", ["symbol"], unique=False)

    if "paper_positions" not in existing_tables:
        op.create_table(
            "paper_positions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("average_cost", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("account_id", "symbol", name="uq_paper_positions_account_symbol"),
        )
        op.create_index("ix_paper_positions_account_id", "paper_positions", ["account_id"], unique=False)
        op.create_index("ix_paper_positions_id", "paper_positions", ["id"], unique=False)
        op.create_index("ix_paper_positions_symbol", "paper_positions", ["symbol"], unique=False)

    if "paper_executions" not in existing_tables:
        op.create_table(
            "paper_executions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("side", sa.String(length=8), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("price", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"]),
            sa.ForeignKeyConstraint(["order_id"], ["paper_orders.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_paper_executions_account_id", "paper_executions", ["account_id"], unique=False)
        op.create_index("ix_paper_executions_id", "paper_executions", ["id"], unique=False)
        op.create_index("ix_paper_executions_order_id", "paper_executions", ["order_id"], unique=False)
        op.create_index("ix_paper_executions_symbol", "paper_executions", ["symbol"], unique=False)


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "paper_executions" in existing_tables:
        op.drop_index("ix_paper_executions_symbol", table_name="paper_executions")
        op.drop_index("ix_paper_executions_order_id", table_name="paper_executions")
        op.drop_index("ix_paper_executions_id", table_name="paper_executions")
        op.drop_index("ix_paper_executions_account_id", table_name="paper_executions")
        op.drop_table("paper_executions")

    if "paper_positions" in existing_tables:
        op.drop_index("ix_paper_positions_symbol", table_name="paper_positions")
        op.drop_index("ix_paper_positions_id", table_name="paper_positions")
        op.drop_index("ix_paper_positions_account_id", table_name="paper_positions")
        op.drop_table("paper_positions")

    if "paper_orders" in existing_tables:
        op.drop_index("ix_paper_orders_symbol", table_name="paper_orders")
        op.drop_index("ix_paper_orders_id", table_name="paper_orders")
        op.drop_index("ix_paper_orders_account_id", table_name="paper_orders")
        op.drop_table("paper_orders")

    if "paper_accounts" in existing_tables:
        op.drop_index("ix_paper_accounts_id", table_name="paper_accounts")
        op.drop_index("ix_paper_accounts_account_key", table_name="paper_accounts")
        op.drop_table("paper_accounts")
