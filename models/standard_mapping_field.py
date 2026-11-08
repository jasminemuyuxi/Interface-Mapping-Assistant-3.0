"""Define standard_mapping_fields without loading database configuration."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class StandardMappingField(Base):
    """Represent persisted standard_mapping_fields; workflow behavior belongs to services."""

    __tablename__ = 'standard_mapping_fields'
    __table_args__ = (
        CheckConstraint("side IN ('SOURCE', 'TARGET')", name='side_allowed'),
        CheckConstraint('field_order > 0', name='field_order_positive'),
        CheckConstraint("definition_status IN ('KNOWN', 'UNKNOWN', 'NOT_APPLICABLE', 'NOT_ENTERED')", name='definition_status_allowed'),
        CheckConstraint("(definition_status = 'KNOWN' AND field_name IS NOT NULL AND field_name ~ '[^[:space:]]') OR (definition_status <> 'KNOWN' AND field_name IS NULL AND field_path IS NULL AND table_name IS NULL AND data_type IS NULL AND data_size IS NULL AND is_required IS NULL AND is_primary_key IS NULL)", name='definition_content'),
        UniqueConstraint('mapping_record_id', 'side', 'field_order', name='uq_standard_mapping_fields_record_side_order'),
    )

    mapping_field_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    mapping_record_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('standard_mapping_records.mapping_record_id', ondelete='RESTRICT', name='fk_standard_mapping_fields_record'), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    field_order: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_status: Mapped[str] = mapped_column(String(20), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    field_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_primary_key: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
