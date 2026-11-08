"""Define standard_mapping_rules without loading database configuration."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class StandardMappingRule(Base):
    """Represent persisted standard_mapping_rules; workflow behavior belongs to services."""

    __tablename__ = 'standard_mapping_rules'
    __table_args__ = (
        CheckConstraint('rule_order > 0', name='rule_order_positive'),
        CheckConstraint("rule_type IN ('DIRECT', 'TRANSFORM', 'CONDITIONAL', 'DEFAULT', 'OTHER')", name='rule_type_allowed'),
        CheckConstraint("rule_text ~ '[^[:space:]]'", name='rule_text_not_blank'),
        UniqueConstraint('mapping_record_id', 'rule_order', name='uq_standard_mapping_rules_record_order'),
    )

    mapping_rule_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    mapping_record_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('standard_mapping_records.mapping_record_id', ondelete='RESTRICT', name='fk_standard_mapping_rules_record'), nullable=False)
    rule_order: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
