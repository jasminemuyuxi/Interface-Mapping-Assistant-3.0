"""Define standard_interfaces without loading database configuration."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class StandardInterface(Base):
    """Represent persisted standard_interfaces; workflow behavior belongs to services."""

    __tablename__ = 'standard_interfaces'
    __table_args__ = (
        CheckConstraint("standard_code ~ '^[A-Z0-9_-]{1,100}$'", name='standard_code_format'),
        CheckConstraint("interface_name ~ '[^[:space:]]'", name='interface_name_not_blank'),
        CheckConstraint('source_system_id <> target_system_id', name='different_systems'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='status_allowed'),
        Index(None, 'source_system_id'),
        Index(None, 'target_system_id'),
    )

    standard_interface_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    standard_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    interface_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_system_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('systems.system_id', ondelete='RESTRICT'), nullable=False)
    target_system_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('systems.system_id', ondelete='RESTRICT'), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
