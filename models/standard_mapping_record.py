"""Define standard_mapping_records without loading database configuration."""

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


class StandardMappingRecord(Base):
    """Represent persisted standard_mapping_records; workflow behavior belongs to services."""

    __tablename__ = 'standard_mapping_records'
    __table_args__ = (
        CheckConstraint("mapping_key ~ '[^[:space:]]'", name='mapping_key_not_blank'),
        CheckConstraint('sequence_no > 0', name='sequence_no_positive'),
        CheckConstraint("verification_status IN ('UNVERIFIED', 'VERIFIED')", name='verification_status_allowed'),
        UniqueConstraint('standard_interface_version_id', 'mapping_key', name='uq_standard_mapping_records_version_key'),
        UniqueConstraint('standard_interface_version_id', 'sequence_no', name='uq_standard_mapping_records_version_sequence'),
    )

    mapping_record_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    standard_interface_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('standard_interface_versions.standard_interface_version_id', ondelete='RESTRICT', name='fk_standard_mapping_records_version'), nullable=False)
    mapping_key: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'UNVERIFIED'"))
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
