"""Define the customer registry model without database connections."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Customer(Base):
    """Represent a customer profile for one business country or region.

    Optional text normalization belongs to the future write service.
    The country check validates format only, not country code membership.
    Timestamp updates through onupdate apply to SQLAlchemy-issued updates;
    no database trigger is defined here.
    """

    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "customer_code ~ '^[A-Z0-9_-]{1,50}$'",
            name="customer_code_format",
        ),
        CheckConstraint(
            "customer_name_en ~ '[^[:space:]]'",
            name="customer_name_en_not_blank",
        ),
        CheckConstraint(
            "country_code ~ '^[A-Z]{2}$'",
            name="country_code_format",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_allowed",
        ),
        Index(None, "country_code"),
    )

    customer_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    customer_code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    customer_name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_name_local: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    contracting_entity_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ACTIVE'")
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
