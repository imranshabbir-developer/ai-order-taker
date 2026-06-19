"""Add payment_charges, sms_messages, caller_phone; seed restaurant rows."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_payment_sms_caller"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "call_sessions",
        sa.Column("caller_phone", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "payment_charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("charge_id", sa.String(length=64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("last_four", sa.String(length=4), nullable=True),
        sa.Column("token", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("charge_id"),
    )
    op.create_index("ix_payment_charges_order_id", "payment_charges", ["order_id"])

    op.create_table(
        "sms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sms_id", sa.String(length=64), nullable=False),
        sa.Column("restaurant_id", sa.String(length=128), nullable=False),
        sa.Column("to_phone", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sms_id"),
    )
    op.create_index("ix_sms_messages_order_id", "sms_messages", ["order_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO restaurants (id, name) VALUES
                ('hot_bagels_2nd_street', 'Hot Bagels 2nd street'),
                ('demo_cafe', 'Demo Cafe')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_sms_messages_order_id", table_name="sms_messages")
    op.drop_table("sms_messages")
    op.drop_index("ix_payment_charges_order_id", table_name="payment_charges")
    op.drop_table("payment_charges")
    op.drop_column("call_sessions", "caller_phone")
