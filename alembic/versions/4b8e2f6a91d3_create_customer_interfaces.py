"""Create customer interfaces without changing existing business tables.

Revision ID: 4b8e2f6a91d3
Revises: c93a7d125e60
"""

from alembic import op
import sqlalchemy as sa


revision = "4b8e2f6a91d3"
down_revision = "c93a7d125e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create interface ownership, display columns, constraints, and indexes."""
    op.create_table(
        "customer_interfaces",
        sa.Column("customer_interface_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("interface_code", sa.String(100), nullable=False),
        sa.Column("interface_name", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "interface_code ~ '[^[:space:]]'",
            name=op.f("ck_customer_interfaces_interface_code_not_blank"),
        ),
        sa.CheckConstraint(
            "interface_name ~ '[^[:space:]]'",
            name=op.f("ck_customer_interfaces_interface_name_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.customer_id"], ondelete="RESTRICT",
            name=op.f("fk_customer_interfaces_customer_id_customers"),
        ),
        sa.PrimaryKeyConstraint(
            "customer_interface_id", name=op.f("pk_customer_interfaces"),
        ),
    )
    op.create_index(
        op.f("ix_customer_interfaces_customer_id"),
        "customer_interfaces", ["customer_id"], unique=False,
    )
    op.create_index(
        "ux_customer_interfaces_interface_code_ci", "customer_interfaces",
        [sa.text("lower(interface_code)")], unique=True,
    )
    # updated_at onupdate belongs to SQLAlchemy; no database trigger is created.


def downgrade() -> None:
    """Remove only this revision's indexes and table, in reverse order."""
    op.drop_index(
        "ux_customer_interfaces_interface_code_ci", table_name="customer_interfaces",
    )
    op.drop_index(
        op.f("ix_customer_interfaces_customer_id"), table_name="customer_interfaces",
    )
    op.drop_table("customer_interfaces")
