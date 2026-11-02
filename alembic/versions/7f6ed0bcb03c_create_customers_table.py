"""create customers table

Revision ID: 7f6ed0bcb03c
Revises: 
Create Date: 2026-10-31 23:21:38.238568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = '7f6ed0bcb03c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the customer registry table and country lookup index."""
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("customer_code", sa.String(50), nullable=False),
        sa.Column("customer_name_en", sa.String(200), nullable=False),
        sa.Column("customer_name_local", sa.String(200), nullable=True),
        sa.Column("contracting_entity_name", sa.String(200), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column(
            "status", sa.String(20), server_default=sa.text("'ACTIVE'"), nullable=False
        ),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("customer_id", name=op.f("pk_customers")),
        sa.UniqueConstraint("customer_code", name=op.f("uq_customers_customer_code")),
        sa.CheckConstraint(
            "customer_code ~ '^[A-Z0-9_-]{1,50}$'",
            name=op.f("ck_customers_customer_code_format"),
        ),
        sa.CheckConstraint(
            "customer_name_en ~ '[^[:space:]]'",
            name=op.f("ck_customers_customer_name_en_not_blank"),
        ),
        sa.CheckConstraint(
            "country_code ~ '^[A-Z]{2}$'",
            name=op.f("ck_customers_country_code_format"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name=op.f("ck_customers_status_allowed"),
        ),
    )
    op.create_index(
        op.f("ix_customers_country_code"), "customers", ["country_code"], unique=False
    )
    # updated_at onupdate belongs to SQLAlchemy; no database trigger is created.


def downgrade() -> None:
    """Remove the country lookup index and customer registry table."""
    op.drop_index(op.f("ix_customers_country_code"), table_name="customers")
    op.drop_table("customers")
