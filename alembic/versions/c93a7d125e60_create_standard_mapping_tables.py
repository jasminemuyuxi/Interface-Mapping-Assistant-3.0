"""Create six standard mapping tables and seed system codes.

Revision ID: c93a7d125e60
Revises: 7f6ed0bcb03c
"""

from alembic import op
import sqlalchemy as sa

revision = "c93a7d125e60"
down_revision = "7f6ed0bcb03c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create registry structures; service workflows are outside this migration."""
    op.create_table('systems',
        sa.Column('system_id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('system_code', sa.String(50), nullable=False),
        sa.Column('system_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_systems_status_allowed')),
        sa.CheckConstraint("system_code ~ '^[A-Z0-9_-]{1,50}$'", name=op.f('ck_systems_system_code_format')),
        sa.CheckConstraint("system_name ~ '[^[:space:]]'", name=op.f('ck_systems_system_name_not_blank')),
        sa.PrimaryKeyConstraint('system_id', name=op.f('pk_systems')),
        sa.UniqueConstraint('system_code', name=op.f('uq_systems_system_code')),
    )
    op.create_table('standard_interfaces',
        sa.Column('standard_interface_id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('standard_code', sa.String(100), nullable=False),
        sa.Column('interface_name', sa.String(200), nullable=False),
        sa.Column('source_system_id', sa.BigInteger(), nullable=False),
        sa.Column('target_system_id', sa.BigInteger(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('source_system_id <> target_system_id', name=op.f('ck_standard_interfaces_different_systems')),
        sa.CheckConstraint("interface_name ~ '[^[:space:]]'", name=op.f('ck_standard_interfaces_interface_name_not_blank')),
        sa.CheckConstraint("standard_code ~ '^[A-Z0-9_-]{1,100}$'", name=op.f('ck_standard_interfaces_standard_code_format')),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_standard_interfaces_status_allowed')),
        sa.ForeignKeyConstraint(['source_system_id'], ['systems.system_id'], ondelete="RESTRICT", name=op.f('fk_standard_interfaces_source_system_id_systems')),
        sa.ForeignKeyConstraint(['target_system_id'], ['systems.system_id'], ondelete="RESTRICT", name=op.f('fk_standard_interfaces_target_system_id_systems')),
        sa.PrimaryKeyConstraint('standard_interface_id', name=op.f('pk_standard_interfaces')),
        sa.UniqueConstraint('standard_code', name=op.f('uq_standard_interfaces_standard_code')),
    )
    op.create_index(op.f('ix_standard_interfaces_source_system_id'), 'standard_interfaces', ['source_system_id'], unique=False)
    op.create_index(op.f('ix_standard_interfaces_target_system_id'), 'standard_interfaces', ['target_system_id'], unique=False)
    op.create_table('standard_interface_versions',
        sa.Column('standard_interface_version_id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('standard_interface_id', sa.BigInteger(), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('version_label', sa.String(100), nullable=True),
        sa.Column('original_interface_code', sa.String(200), nullable=True),
        sa.Column('message_type', sa.String(20), nullable=True),
        sa.Column('source_reference', sa.Text(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('workflow_status', sa.String(20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("message_type IN ('REQUEST', 'RESPONSE', 'EVENT')", name=op.f('ck_standard_interface_versions_message_type_allowed')),
        sa.CheckConstraint("(workflow_status = 'DRAFT' AND published_at IS NULL) OR (workflow_status IN ('PUBLISHED', 'RETIRED') AND published_at IS NOT NULL)", name=op.f('ck_standard_interface_versions_publication_time')),
        sa.CheckConstraint('version_no > 0', name=op.f('ck_standard_interface_versions_version_no_positive')),
        sa.CheckConstraint("workflow_status IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name=op.f('ck_standard_interface_versions_workflow_status_allowed')),
        sa.ForeignKeyConstraint(['standard_interface_id'], ['standard_interfaces.standard_interface_id'], ondelete="RESTRICT", name=op.f('fk_standard_interface_versions_interface')),
        sa.PrimaryKeyConstraint('standard_interface_version_id', name=op.f('pk_standard_interface_versions')),
        sa.UniqueConstraint('standard_interface_id', 'version_no', name=op.f('uq_standard_interface_versions_interface_version')),
    )
    op.create_table('standard_mapping_records',
        sa.Column('mapping_record_id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('standard_interface_version_id', sa.BigInteger(), nullable=False),
        sa.Column('mapping_key', sa.String(100), nullable=False),
        sa.Column('sequence_no', sa.Integer(), nullable=False),
        sa.Column('business_name', sa.String(200), nullable=True),
        sa.Column('verification_status', sa.String(20), nullable=False, server_default=sa.text("'UNVERIFIED'")),
        sa.Column('source_reference', sa.Text(), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("mapping_key ~ '[^[:space:]]'", name=op.f('ck_standard_mapping_records_mapping_key_not_blank')),
        sa.CheckConstraint('sequence_no > 0', name=op.f('ck_standard_mapping_records_sequence_no_positive')),
        sa.CheckConstraint("verification_status IN ('UNVERIFIED', 'VERIFIED')", name=op.f('ck_standard_mapping_records_verification_status_allowed')),
        sa.ForeignKeyConstraint(['standard_interface_version_id'], ['standard_interface_versions.standard_interface_version_id'], ondelete="RESTRICT", name=op.f('fk_standard_mapping_records_version')),
        sa.PrimaryKeyConstraint('mapping_record_id', name=op.f('pk_standard_mapping_records')),
        sa.UniqueConstraint('standard_interface_version_id', 'mapping_key', name=op.f('uq_standard_mapping_records_version_key')),
        sa.UniqueConstraint('standard_interface_version_id', 'sequence_no', name=op.f('uq_standard_mapping_records_version_sequence')),
    )
    op.create_table('standard_mapping_fields',
        sa.Column('mapping_field_id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('mapping_record_id', sa.BigInteger(), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('field_order', sa.Integer(), nullable=False),
        sa.Column('definition_status', sa.String(20), nullable=False),
        sa.Column('field_name', sa.String(200), nullable=True),
        sa.Column('field_path', sa.Text(), nullable=True),
        sa.Column('table_name', sa.String(200), nullable=True),
        sa.Column('data_type', sa.String(100), nullable=True),
        sa.Column('data_size', sa.String(100), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('is_primary_key', sa.Boolean(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("(definition_status = 'KNOWN' AND field_name IS NOT NULL AND field_name ~ '[^[:space:]]') OR (definition_status <> 'KNOWN' AND field_name IS NULL AND field_path IS NULL AND table_name IS NULL AND data_type IS NULL AND data_size IS NULL AND is_required IS NULL AND is_primary_key IS NULL)", name=op.f('ck_standard_mapping_fields_definition_content')),
        sa.CheckConstraint("definition_status IN ('KNOWN', 'UNKNOWN', 'NOT_APPLICABLE', 'NOT_ENTERED')", name=op.f('ck_standard_mapping_fields_definition_status_allowed')),
        sa.CheckConstraint('field_order > 0', name=op.f('ck_standard_mapping_fields_field_order_positive')),
        sa.CheckConstraint("side IN ('SOURCE', 'TARGET')", name=op.f('ck_standard_mapping_fields_side_allowed')),
        sa.ForeignKeyConstraint(['mapping_record_id'], ['standard_mapping_records.mapping_record_id'], ondelete="RESTRICT", name=op.f('fk_standard_mapping_fields_record')),
        sa.PrimaryKeyConstraint('mapping_field_id', name=op.f('pk_standard_mapping_fields')),
        sa.UniqueConstraint('mapping_record_id', 'side', 'field_order', name=op.f('uq_standard_mapping_fields_record_side_order')),
    )
    op.create_table('standard_mapping_rules',
        sa.Column('mapping_rule_id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('mapping_record_id', sa.BigInteger(), nullable=False),
        sa.Column('rule_order', sa.Integer(), nullable=False),
        sa.Column('rule_type', sa.String(20), nullable=False),
        sa.Column('rule_text', sa.Text(), nullable=False),
        sa.Column('business_description', sa.Text(), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('rule_order > 0', name=op.f('ck_standard_mapping_rules_rule_order_positive')),
        sa.CheckConstraint("rule_text ~ '[^[:space:]]'", name=op.f('ck_standard_mapping_rules_rule_text_not_blank')),
        sa.CheckConstraint("rule_type IN ('DIRECT', 'TRANSFORM', 'CONDITIONAL', 'DEFAULT', 'OTHER')", name=op.f('ck_standard_mapping_rules_rule_type_allowed')),
        sa.ForeignKeyConstraint(['mapping_record_id'], ['standard_mapping_records.mapping_record_id'], ondelete="RESTRICT", name=op.f('fk_standard_mapping_rules_record')),
        sa.PrimaryKeyConstraint('mapping_rule_id', name=op.f('pk_standard_mapping_rules')),
        sa.UniqueConstraint('mapping_record_id', 'rule_order', name=op.f('uq_standard_mapping_rules_record_order')),
    )
    systems = sa.table(
        "systems", sa.column("system_code", sa.String(50)),
        sa.column("system_name", sa.String(200)),
        sa.column("status", sa.String(20)),
    )
    op.bulk_insert(systems, [
        {"system_code": 'EDI', "system_name": 'CJ EDI', "status": "ACTIVE"},
        {"system_code": 'OMS', "system_name": 'LoIS OMS', "status": "ACTIVE"},
        {"system_code": 'WMS', "system_name": 'LoIS WMS', "status": "ACTIVE"},
        {"system_code": 'TMS', "system_name": 'CJ TMS', "status": "ACTIVE"},
    ])


def downgrade() -> None:
    """Remove this batch in reverse dependency order."""
    op.drop_table('standard_mapping_rules')
    op.drop_table('standard_mapping_fields')
    op.drop_table('standard_mapping_records')
    op.drop_table('standard_interface_versions')
    op.drop_index(op.f('ix_standard_interfaces_source_system_id'), table_name='standard_interfaces')
    op.drop_index(op.f('ix_standard_interfaces_target_system_id'), table_name='standard_interfaces')
    op.drop_table('standard_interfaces')
    op.drop_table('systems')
