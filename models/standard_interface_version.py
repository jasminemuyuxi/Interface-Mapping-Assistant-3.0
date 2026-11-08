"""Define standard_interface_versions without loading database configuration."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class StandardInterfaceVersion(Base):
    """Represent persisted standard_interface_versions; workflow behavior belongs to services."""

    __tablename__ = 'standard_interface_versions'
    __table_args__ = (
        CheckConstraint('version_no > 0', name='version_no_positive'),
        CheckConstraint("message_type IN ('REQUEST', 'RESPONSE', 'EVENT')", name='message_type_allowed'),
        CheckConstraint("workflow_status IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name='workflow_status_allowed'),
        CheckConstraint("(workflow_status = 'DRAFT' AND published_at IS NULL) OR (workflow_status IN ('PUBLISHED', 'RETIRED') AND published_at IS NOT NULL)", name='publication_time'),
        UniqueConstraint('standard_interface_id', 'version_no', name='uq_standard_interface_versions_interface_version'),
    )

    standard_interface_version_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    standard_interface_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('standard_interfaces.standard_interface_id', ondelete='RESTRICT', name='fk_standard_interface_versions_interface'), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_interface_code: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'DRAFT'"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
