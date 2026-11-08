"""Define customer-interface metadata without loading database configuration."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CustomerInterface(Base):
    """Represent interface ownership and display values.

    Trimming, ACTIVE-customer checks, authorization, and session revocation
    belong to future services. Unicode comparison requires database validation.
    ORM onupdate is not a database trigger or complete audit history.
    """

    __tablename__ = "customer_interfaces"
    __table_args__ = (
        CheckConstraint(
            "interface_code ~ '[^[:space:]]'", name="interface_code_not_blank"
        ),
        CheckConstraint(
            "interface_name ~ '[^[:space:]]'", name="interface_name_not_blank"
        ),
        Index(None, "customer_id"),
    )

    customer_interface_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    interface_code: Mapped[str] = mapped_column(String(100), nullable=False)
    interface_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ += (
        Index(
            "ux_customer_interfaces_interface_code_ci",
            func.lower(interface_code),
            unique=True,
        ),
    )
