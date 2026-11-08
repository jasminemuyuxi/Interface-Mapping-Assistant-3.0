"""Define systems without loading database configuration."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class System(Base):
    """Represent persisted systems; workflow behavior belongs to services."""

    __tablename__ = 'systems'
    __table_args__ = (
        CheckConstraint("system_code ~ '^[A-Z0-9_-]{1,50}$'", name='system_code_format'),
        CheckConstraint("system_name ~ '[^[:space:]]'", name='system_name_not_blank'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='status_allowed'),
    )

    system_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    system_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    system_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
