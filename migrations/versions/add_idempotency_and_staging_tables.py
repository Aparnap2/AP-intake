"""Add idempotency and staging tables

Revision ID: add_idempotency_and_staging_tables
Revises: f1a2b3c4d5e6
Create Date: 2025-01-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_idempotency_and_staging_tables'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create idempotency_records table
    op.create_table('idempotency_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('operation_type', sa.Enum('INVOICE_UPLOAD', 'INVOICE_PROCESS', 'EXPORT_STAGE', 'EXPORT_POST', 'EXCEPTION_RESOLVE', 'BATCH_OPERATION', name='idempotencyoperationtype'), nullable=False),
        sa.Column('operation_status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED', name='idempotencystatus'), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ingestion_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('operation_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('execution_count', sa.Integer(), nullable=False),
        sa.Column('max_executions', sa.Integer(), nullable=False),
        sa.Column('first_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ttl_seconds', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(['ingestion_job_id'], ['ingestion_jobs.id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_idempotency_key'),
        sa.CheckConstraint('execution_count >= 0', name='check_execution_count_non_negative'),
        sa.CheckConstraint("idempotency_key <> ''", name='check_idempotency_key_not_empty'),
        sa.CheckConstraint('max_executions >= 1', name='check_max_executions_positive'),
        sa.CheckConstraint('ttl_seconds IS NULL OR ttl_seconds > 0', name='check_ttl_seconds_positive')
    )
    op.create_index('idx_idempotency_expires_status', 'idempotency_records', ['expires_at', 'operation_status'], unique=False)
    op.create_index('idx_idempotency_invoice_status', 'idempotency_records', ['invoice_id', 'operation_status'], unique=False)
    op.create_index('idx_idempotency_key_status', 'idempotency_records', ['idempotency_key', 'operation_status'], unique=False)
    op.create_index('idx_idempotency_operation_created', 'idempotency_records', ['operation_type', 'created_at'], unique=False)
    op.create_index('idx_idempotency_user_operation', 'idempotency_records', ['user_id', 'operation_type'], unique=False)
    op.create_index('idx_idempotency_execution_tracking', 'idempotency_records', ['execution_count', 'last_attempt_at'], unique=False)

    # Create idempotency_conflicts table
    op.create_table('idempotency_conflicts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('idempotency_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conflict_key', sa.String(length=255), nullable=False),
        sa.Column('conflict_type', sa.String(length=50), nullable=False),
        sa.Column('conflict_reason', sa.Text(), nullable=False),
        sa.Column('conflicting_operation_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('resolution_action', sa.String(length=50), nullable=True),
        sa.Column('resolved_by', sa.String(length=255), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['idempotency_record_id'], ['idempotency_records.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('check_conflict_key_not_empty', "conflict_key <> ''"),
        sa.CheckConstraint('check_conflict_reason_not_null', 'conflict_reason IS NOT NULL')
    )
    op.create_index('idx_conflict_created_at', 'idempotency_conflicts', ['created_at'], unique=False)
    op.create_index('idx_conflict_key_type', 'idempotency_conflicts', ['conflict_key', 'conflict_type'], unique=False)
    op.create_index('idx_conflict_record_id', 'idempotency_conflicts', ['idempotency_record_id'], unique=False)
    op.create_index('idx_conflict_resolved_at', 'idempotency_conflicts', ['resolved_at'], unique=False)

    # Create idempotency_metrics table
    op.create_table('idempotency_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metric_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('operation_type', sa.Enum('INVOICE_UPLOAD', 'INVOICE_PROCESS', 'EXPORT_STAGE', 'EXPORT_POST', 'EXCEPTION_RESOLVE', 'BATCH_OPERATION', name='idempotencyoperationtype'), nullable=True),
        sa.Column('total_operations', sa.Integer(), nullable=False),
        sa.Column('successful_operations', sa.Integer(), nullable=False),
        sa.Column('failed_operations', sa.Integer(), nullable=False),
        sa.Column('duplicate_prevented', sa.Integer(), nullable=False),
        sa.Column('conflicts_detected', sa.Integer(), nullable=False),
        sa.Column('avg_execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('max_execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('cache_hit_rate', sa.Integer(), nullable=True),
        sa.Column('error_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('check_avg_execution_time_non_negative', 'avg_execution_time_ms >= 0'),
        sa.CheckConstraint('check_cache_hit_rate_range', 'cache_hit_rate IS NULL OR (cache_hit_rate >= 0 AND cache_hit_rate <= 100)'),
        sa.CheckConstraint('check_conflicts_detected_non_negative', 'conflicts_detected >= 0'),
        sa.CheckConstraint('check_duplicate_prevented_non_negative', 'duplicate_prevented >= 0'),
        sa.CheckConstraint('check_failed_operations_non_negative', 'failed_operations >= 0'),
        sa.CheckConstraint('check_max_execution_time_non_negative', 'max_execution_time_ms >= 0'),
        sa.CheckConstraint('check_successful_operations_non_negative', 'successful_operations >= 0'),
        sa.CheckConstraint('check_total_operations_non_negative', 'total_operations >= 0')
    )
    op.create_index('idx_idempotency_metrics_date', 'idempotency_metrics', ['metric_date'], unique=False)
    op.create_index('idx_idempotency_metrics_date_operation', 'idempotency_metrics', ['metric_date', 'operation_type'], unique=False)

    # Create staged_exports table
    op.create_table('staged_exports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('staging_status', sa.Enum('PREPARED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'POSTED', 'FAILED', 'CANCELLED', 'ROLLED_BACK', name='stagingstatus'), nullable=False),
        sa.Column('export_format', sa.Enum('CSV', 'JSON', 'XML', 'EDI', 'X12', name='exportformat'), nullable=False),
        sa.Column('destination_system', sa.String(length=255), nullable=False),
        sa.Column('prepared_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('approved_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('posted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('original_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('prepared_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('posted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejected_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prepared_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('diff_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('field_changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('export_job_id', sa.String(length=100), nullable=True),
        sa.Column('external_reference', sa.String(length=255), nullable=True),
        sa.Column('export_filename', sa.String(length=255), nullable=True),
        sa.Column('export_file_path', sa.Text(), nullable=True),
        sa.Column('export_file_size', sa.Integer(), nullable=True),
        sa.Column('validation_errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('business_unit', sa.String(length=100), nullable=True),
        sa.Column('cost_center', sa.String(length=50), nullable=True),
        sa.Column('compliance_flags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('audit_notes', sa.Text(), nullable=True),
        sa.Column('reviewer_comments', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('check_avg_quality_score_range', 'quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)'),
        sa.CheckConstraint('check_destination_system_not_empty', "destination_system <> ''"),
        sa.CheckConstraint('check_export_file_size_non_negative', 'export_file_size >= 0'),
        sa.CheckConstraint('check_max_retries_non_negative', 'max_retries >= 0'),
        sa.CheckConstraint('check_priority_range', 'priority >= 1 AND priority <= 10'),
        sa.CheckConstraint('check_retry_count_non_negative', 'retry_count >= 0')
    )
    op.create_index('idx_staging_approved_at', 'staged_exports', ['approved_at'], unique=False)
    op.create_index('idx_staging_batch_status', 'staged_exports', ['batch_id', 'staging_status'], unique=False)
    op.create_index('idx_staging_business_unit', 'staged_exports', ['business_unit', 'staging_status'], unique=False)
    op.create_index('idx_staging_cost_center', 'staged_exports', ['cost_center', 'staging_status'], unique=False)
    op.create_index('idx_staging_destination_status', 'staged_exports', ['destination_system', 'staging_status'], unique=False)
    op.create_index('idx_staging_export_job', 'staged_exports', ['export_job_id'], unique=False)
    op.create_index('idx_staging_external_ref', 'staged_exports', ['external_reference'], unique=False)
    op.create_index('idx_staging_invoice_status', 'staged_exports', ['invoice_id', 'staging_status'], unique=False)
    op.create_index('idx_staging_prepared_at', 'staged_exports', ['prepared_at'], unique=False)
    op.create_index('idx_staging_quality_score', 'staged_exports', ['quality_score', 'staging_status'], unique=False)
    op.create_index('idx_staging_status_priority', 'staged_exports', ['staging_status', 'priority'], unique=False)

    # Create staging_approval_chains table
    op.create_table('staging_approval_chains',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('staged_export_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('approver_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('approval_level', sa.Integer(), nullable=False),
        sa.Column('approval_status', sa.String(length=20), nullable=False),
        sa.Column('approval_decision', sa.String(length=20), nullable=True),
        sa.Column('approval_comments', sa.Text(), nullable=True),
        sa.Column('business_justification', sa.Text(), nullable=True),
        sa.Column('risk_assessment', sa.String(length=50), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['staged_export_id'], ['staged_exports.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('check_approval_decision_valid', "approval_decision IN ('approve', 'reject', 'request_changes')"),
        sa.CheckConstraint('check_approval_level_positive', 'approval_level >= 1'),
        sa.CheckConstraint('check_approval_status_valid', "approval_status IN ('pending', 'approved', 'rejected', 'expired')"),
        sa.CheckConstraint('check_risk_assessment_valid', 'risk_assessment IS NULL OR risk_assessment IN (\'low\', \'medium\', \'high\')')
    )
    op.create_index('idx_approval_chain_approver', 'staging_approval_chains', ['approver_id', 'approval_status'], unique=False)
    op.create_index('idx_approval_chain_export_level', 'staging_approval_chains', ['staged_export_id', 'approval_level'], unique=False)
    op.create_index('idx_approval_chain_risk', 'staging_approval_chains', ['risk_assessment', 'approval_status'], unique=False)
    op.create_index('idx_approval_chain_status', 'staging_approval_chains', ['approval_status', 'expires_at'], unique=False)

    # Create staging_audit_trails table
    op.create_table('staging_audit_trails',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('staged_export_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('action_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_reason', sa.Text(), nullable=True),
        sa.Column('previous_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('data_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('business_event', sa.String(length=100), nullable=True),
        sa.Column('impact_assessment', sa.String(length=50), nullable=True),
        sa.Column('compliance_impact', postgresql.ARRAY(sa.String()), nullable=True),
        sa.ForeignKeyConstraint(['staged_export_id'], ['staged_exports.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('check_action_not_empty', "action <> ''"),
        sa.CheckConstraint('check_impact_assessment_valid', 'impact_assessment IS NULL OR impact_assessment IN (\'low\', \'medium\', \'high\')')
    )
    op.create_index('idx_audit_trail_action_by_date', 'staging_audit_trails', ['action_by', 'created_at'], unique=False)
    op.create_index('idx_audit_trail_business_event', 'staging_audit_trails', ['business_event', 'created_at'], unique=False)
    op.create_index('idx_audit_trail_created_at', 'staging_audit_trails', ['created_at'], unique=False)
    op.create_index('idx_audit_trail_export_action', 'staging_audit_trails', ['staged_export_id', 'action'], unique=False)
    op.create_index('idx_audit_trail_impact', 'staging_audit_trails', ['impact_assessment', 'created_at'], unique=False)

    # Create staging_batches table
    op.create_table('staging_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('batch_name', sa.String(length=255), nullable=False),
        sa.Column('batch_description', sa.Text(), nullable=True),
        sa.Column('batch_type', sa.String(length=50), nullable=False),
        sa.Column('batch_status', sa.String(length=20), nullable=False),
        sa.Column('total_exports', sa.Integer(), nullable=False),
        sa.Column('prepared_exports', sa.Integer(), nullable=False),
        sa.Column('approved_exports', sa.Integer(), nullable=False),
        sa.Column('posted_exports', sa.Integer(), nullable=False),
        sa.Column('failed_exports', sa.Integer(), nullable=False),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_completion_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('avg_quality_score', sa.Integer(), nullable=True),
        sa.Column('total_validation_errors', sa.Integer(), nullable=False),
        sa.Column('total_validation_warnings', sa.Integer(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('check_avg_quality_score_range', 'avg_quality_score IS NULL OR (avg_quality_score >= 0 AND avg_quality_score <= 100)'),
        sa.CheckConstraint('check_batch_name_not_empty', "batch_name <> ''"),
        sa.CheckConstraint('check_failed_exports_non_negative', 'failed_exports >= 0'),
        sa.CheckConstraint('check_posted_exports_non_negative', 'posted_exports >= 0'),
        sa.CheckConstraint('check_prepared_exports_non_negative', 'prepared_exports >= 0'),
        sa.CheckConstraint('check_approved_exports_non_negative', 'approved_exports >= 0'),
        sa.CheckConstraint('check_total_exports_non_negative', 'total_exports >= 0'),
        sa.CheckConstraint('check_total_validation_errors_non_negative', 'total_validation_errors >= 0'),
        sa.CheckConstraint('check_total_validation_warnings_non_negative', 'total_validation_warnings >= 0')
    )
    op.create_index('idx_staging_batch_completion', 'staging_batches', ['processing_completed_at'], unique=False)
    op.create_index('idx_staging_batch_created_by', 'staging_batches', ['created_by', 'created_at'], unique=False)
    op.create_index('idx_staging_batch_status', 'staging_batches', ['batch_status', 'created_at'], unique=False)
    op.create_index('idx_staging_batch_type_status', 'staging_batches', ['batch_type', 'batch_status'], unique=False)

    # Update existing invoices table to add relationship with idempotency_records
    op.add_column('invoices', sa.Column('idempotency_records', sa.String(), nullable=True))

    # Update existing ingestion_jobs table to add relationship with idempotency_records
    op.add_column('ingestion_jobs', sa.Column('idempotency_records', sa.String(), nullable=True))


def downgrade() -> None:
    # Drop new tables in reverse order
    op.drop_table('staging_batches')
    op.drop_table('staging_audit_trails')
    op.drop_table('staging_approval_chains')
    op.drop_table('staged_exports')
    op.drop_table('idempotency_metrics')
    op.drop_table('idempotency_conflicts')
    op.drop_table('idempotency_records')

    # Remove columns from existing tables
    op.drop_column('ingestion_jobs', 'idempotency_records')
    op.drop_column('invoices', 'idempotency_records')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS idempotencyoperationtype')
    op.execute('DROP TYPE IF EXISTS idempotencystatus')
    op.execute('DROP TYPE IF EXISTS stagingstatus')
    op.execute('DROP TYPE IF EXISTS exportformat')