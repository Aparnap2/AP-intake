"""Add ingestion system tables

Revision ID: 001_add_ingestion_system
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_add_ingestion_system'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ingestion_jobs table
    op.create_table('ingestion_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('file_extension', sa.String(length=10), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('file_hash_sha256', sa.String(length=64), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('storage_backend', sa.String(length=50), nullable=False),
        sa.Column('signed_url', sa.Text(), nullable=True),
        sa.Column('signed_url_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'DUPLICATE_DETECTED', 'REQUIRE_REVIEW', name='ingestionstatus'), nullable=False),
        sa.Column('extracted_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('processing_priority', sa.Integer(), nullable=False),
        sa.Column('deduplication_strategy', sa.Enum('FILE_HASH', 'BUSINESS_RULES', 'TEMPORAL', 'FUZZY_MATCHING', 'COMPOSITE', name='deduplicationstrategy'), nullable=False),
        sa.Column('duplicate_group_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_reference', sa.String(length=500), nullable=True),
        sa.Column('uploaded_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_hash_sha256', name='uq_ingestion_file_hash')
    )
    op.create_index(op.f('ix_ingestion_jobs_created_at'), 'ingestion_jobs', ['created_at'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_duplicate_group_id'), 'ingestion_jobs', ['duplicate_group_id'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_error_code'), 'ingestion_jobs', ['error_code'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_file_hash_sha256'), 'ingestion_jobs', ['file_hash_sha256'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_original_filename'), 'ingestion_jobs', ['original_filename'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_processing_started_at'), 'ingestion_jobs', ['processing_started_at'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_processing_started_at_1'), 'ingestion_jobs', ['processing_started_at'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_status'), 'ingestion_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_status_1'), 'ingestion_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_vendor_id'), 'ingestion_jobs', ['vendor_id'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_vendor_id_1'), 'ingestion_jobs', ['vendor_id'], unique=False)

    # Create duplicate_records table
    op.create_table('duplicate_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ingestion_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('detection_strategy', sa.Enum('FILE_HASH', 'BUSINESS_RULES', 'TEMPORAL', 'FUZZY_MATCHING', 'COMPOSITE', name='deduplicationstrategy'), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('match_criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('comparison_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resolution_action', sa.Enum('AUTO_IGNORE', 'AUTO_MERGE', 'MANUAL_REVIEW', 'REPLACE_EXISTING', 'ARCHIVE_EXISTING', name='duplicateresolution'), nullable=True),
        sa.Column('resolved_by', sa.String(length=255), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('requires_human_review', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['ingestion_job_id'], ['ingestion_jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_duplicate_records_confidence_score'), 'duplicate_records', ['confidence_score'], unique=False)
    op.create_index(op.f('ix_duplicate_records_detection_strategy'), 'duplicate_records', ['detection_strategy'], unique=False)
    op.create_index(op.f('ix_duplicate_records_ingestion_job_id'), 'duplicate_records', ['ingestion_job_id'], unique=False)
    op.create_index(op.f('ix_duplicate_records_original_invoice_id'), 'duplicate_records', ['original_invoice_id'], unique=False)
    op.create_index(op.f('ix_duplicate_records_requires_human_review'), 'duplicate_records', ['requires_human_review'], unique=False)
    op.create_index(op.f('ix_duplicate_records_resolution_action'), 'duplicate_records', ['resolution_action'], unique=False)
    op.create_index(op.f('ix_duplicate_records_status'), 'duplicate_records', ['status'], unique=False)

    # Create signed_urls table
    op.create_table('signed_urls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text='now()'), nullable=False),
        sa.Column('ingestion_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url_token', sa.String(length=255), nullable=False),
        sa.Column('signed_url', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('access_count', sa.Integer(), nullable=False),
        sa.Column('max_access_count', sa.Integer(), nullable=False),
        sa.Column('allowed_ip_addresses', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_for', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['ingestion_job_id'], ['ingestion_jobs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url_token', name='uq_signed_urls_url_token')
    )
    op.create_index(op.f('ix_signed_urls_expires_at'), 'signed_urls', ['expires_at'], unique=False)
    op.create_index(op.f('ix_signed_urls_ingestion_job_id'), 'signed_urls', ['ingestion_job_id'], unique=False)
    op.create_index(op.f('ix_signed_urls_is_active'), 'signed_urls', ['is_active'], unique=False)
    op.create_index(op.f('ix_signed_urls_url_token'), 'signed_urls', ['url_token'], unique=False)

    # Create deduplication_rules table
    op.create_table('deduplication_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategy', sa.Enum('FILE_HASH', 'BUSINESS_RULES', 'TEMPORAL', 'FUZZY_MATCHING', 'COMPOSITE', name='deduplicationstrategy'), nullable=False),
        sa.Column('configuration', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('vendor_filter', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('file_type_filter', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('date_range_filter', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('match_count', sa.Integer(), nullable=False),
        sa.Column('false_positive_count', sa.Integer(), nullable=False),
        sa.Column('last_matched_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_deduplication_rules_name')
    )
    op.create_index(op.f('ix_deduplication_rules_is_active'), 'deduplication_rules', ['is_active'], unique=False)
    op.create_index(op.f('ix_deduplication_rules_last_matched_at'), 'deduplication_rules', ['last_matched_at'], unique=False)
    op.create_index(op.f('ix_deduplication_rules_match_count'), 'deduplication_rules', ['match_count'], unique=False)
    op.create_index(op.f('ix_deduplication_rules_name'), 'deduplication_rules', ['name'], unique=False)
    op.create_index(op.f('ix_deduplication_rules_priority'), 'deduplication_rules', ['priority'], unique=False)
    op.create_index(op.f('ix_deduplication_rules_strategy'), 'deduplication_rules', ['strategy'], unique=False)

    # Create ingestion_metrics table
    op.create_table('ingestion_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metric_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('total_ingestion_jobs', sa.Integer(), nullable=False),
        sa.Column('completed_ingestions', sa.Integer(), nullable=False),
        sa.Column('failed_ingestions', sa.Integer(), nullable=False),
        sa.Column('duplicate_detected', sa.Integer(), nullable=False),
        sa.Column('avg_processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('total_file_size_mb', sa.Integer(), nullable=False),
        sa.Column('duplicates_by_strategy', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingestion_metrics_metric_date'), 'ingestion_metrics', ['metric_date'], unique=False)
    op.create_index(op.f('ix_ingestion_metrics_metric_date_1'), 'ingestion_metrics', ['metric_date'], unique=False)
    op.create_index(op.f('ix_ingestion_metrics_vendor_id'), 'ingestion_metrics', ['vendor_id'], unique=False)

    # Add default deduplication rules
    op.execute("""
        INSERT INTO deduplication_rules (id, name, description, strategy, configuration, is_active, priority, match_count, false_positive_count)
        VALUES
            (gen_random_uuid(), 'Exact File Hash', 'Detect duplicates using exact SHA-256 file hash matching', 'FILE_HASH', '{"confidence_threshold": 1.0}', true, 10, 0, 0),
            (gen_random_uuid(), 'Business Rules', 'Detect duplicates based on vendor + amount + date combination', 'BUSINESS_RULES', '{"date_tolerance_days": 3, "amount_tolerance": 0.01, "confidence_threshold": 0.8}', true, 8, 0, 0),
            (gen_random_uuid(), 'Temporal Window', 'Detect duplicates within 24-hour time windows', 'TEMPORAL', '{"window_hours": 24, "confidence_threshold": 0.6}', true, 6, 0, 0),
            (gen_random_uuid(), 'Fuzzy Content Matching', 'Detect duplicates using text similarity analysis', 'FUZZY_MATCHING', '{"similarity_threshold": 0.85, "days_back": 30, "max_comparisons": 50}', true, 4, 0, 0),
            (gen_random_uuid(), 'Composite Strategy', 'Combine multiple strategies for comprehensive duplicate detection', 'COMPOSITE', '{"strategies": ["FILE_HASH", "BUSINESS_RULES", "TEMPORAL"], "strategy_weights": {"FILE_HASH": 1.0, "BUSINESS_RULES": 0.8, "TEMPORAL": 0.6}, "confidence_threshold": 0.7}', true, 9, 0, 0);
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('ingestion_metrics')
    op.drop_table('deduplication_rules')
    op.drop_table('signed_urls')
    op.drop_table('duplicate_records')
    op.drop_table('ingestion_jobs')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS ingestionstatus')
    op.execute('DROP TYPE IF EXISTS deduplicationstrategy')
    op.execute('DROP TYPE IF EXISTS duplicateresolution')