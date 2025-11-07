"""Create export models

Revision ID: 001_create_export_models
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_create_export_models'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create export_templates table
    op.create_table(
        'export_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('format', sa.Enum('CSV', 'JSON', 'XML', 'EXCEL', 'PDF', name='exportformat'), nullable=False),
        sa.Column('field_mappings', sa.JSON(), nullable=False),
        sa.Column('header_config', sa.JSON(), nullable=True),
        sa.Column('footer_config', sa.JSON(), nullable=True),
        sa.Column('compression', sa.Boolean(), nullable=False),
        sa.Column('encryption', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_template_name_format', 'export_templates', ['name', 'format'], unique=False)
    op.create_index('idx_template_active_updated', 'export_templates', ['is_active', 'updated_at'], unique=False)
    op.create_constraint('uq_template_name_format', 'export_templates', 'unique', ['name', 'format'])

    # Create export_jobs table
    op.create_table(
        'export_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('format', sa.Enum('CSV', 'JSON', 'XML', 'EXCEL', 'PDF', name='exportformat'), nullable=False),
        sa.Column('destination', sa.Enum('DOWNLOAD', 'FILE_STORAGE', 'API_ENDPOINT', 'EMAIL', 'FTP', name='exportdestination'), nullable=False),
        sa.Column('destination_config', sa.JSON(), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('invoice_ids', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PREPARING', 'VALIDATING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED', name='exportstatus'), nullable=False),
        sa.Column('total_records', sa.Integer(), nullable=True),
        sa.Column('processed_records', sa.Integer(), nullable=False),
        sa.Column('failed_records', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_completion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('batch_size', sa.Integer(), nullable=False),
        sa.Column('notify_on_completion', sa.Boolean(), nullable=False),
        sa.Column('notification_config', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['export_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_job_status_created', 'export_jobs', ['status', 'created_at'], unique=False)
    op.create_index('idx_job_user_status', 'export_jobs', ['user_id', 'status'], unique=False)
    op.create_index('idx_job_template_status', 'export_jobs', ['template_id', 'status'], unique=False)
    op.create_index('idx_job_priority_status', 'export_jobs', ['priority', 'status'], unique=False)
    op.create_index('idx_job_created_at', 'export_jobs', ['created_at'], unique=False)
    op.create_index('idx_job_started_at', 'export_jobs', ['started_at'], unique=False)
    op.create_index('idx_job_completed_at', 'export_jobs', ['completed_at'], unique=False)
    op.create_index('idx_job_user_id', 'export_jobs', ['user_id'], unique=False)

    # Create export_audit_logs table
    op.create_table(
        'export_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('export_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('memory_usage_mb', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['export_job_id'], ['export_jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_job_timestamp', 'export_audit_logs', ['export_job_id', 'created_at'], unique=False)
    op.create_index('idx_audit_event_type', 'export_audit_logs', ['event_type', 'created_at'], unique=False)
    op.create_index('idx_audit_user_timestamp', 'export_audit_logs', ['user_id', 'created_at'], unique=False)

    # Create export_metrics table
    op.create_table(
        'export_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('export_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_records', sa.Integer(), nullable=False),
        sa.Column('successful_records', sa.Integer(), nullable=False),
        sa.Column('failed_records', sa.Integer(), nullable=False),
        sa.Column('skipped_records', sa.Integer(), nullable=False),
        sa.Column('processing_time_seconds', sa.Integer(), nullable=False),
        sa.Column('validation_time_seconds', sa.Integer(), nullable=True),
        sa.Column('transformation_time_seconds', sa.Integer(), nullable=True),
        sa.Column('upload_time_seconds', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('compressed_size_bytes', sa.Integer(), nullable=True),
        sa.Column('compression_ratio', sa.Integer(), nullable=True),
        sa.Column('records_per_second', sa.Integer(), nullable=False),
        sa.Column('peak_memory_usage_mb', sa.Integer(), nullable=True),
        sa.Column('average_record_size_bytes', sa.Integer(), nullable=True),
        sa.Column('validation_errors', sa.Integer(), nullable=False),
        sa.Column('transformation_errors', sa.Integer(), nullable=False),
        sa.Column('upload_errors', sa.Integer(), nullable=False),
        sa.Column('cpu_usage_percent', sa.Integer(), nullable=True),
        sa.Column('disk_io_mb', sa.Integer(), nullable=True),
        sa.Column('network_io_mb', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['export_job_id'], ['export_jobs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('export_job_id')
    )

    # Create export_validation_rules table
    op.create_table(
        'export_validation_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('field_path', sa.String(length=500), nullable=False),
        sa.Column('rule_type', sa.String(length=100), nullable=False),
        sa.Column('rule_config', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.String(length=500), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['export_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_validation_template', 'export_validation_rules', ['template_id', 'is_active'], unique=False)
    op.create_index('idx_validation_field_type', 'export_validation_rules', ['field_path', 'rule_type'], unique=False)
    op.create_index('idx_validation_rule_name', 'export_validation_rules', ['name'], unique=False)
    op.create_constraint('uq_validation_rule_name_template', 'export_validation_rules', 'unique', ['name', 'template_id'])

    # Create export_schedules table
    op.create_table(
        'export_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('destination_config', sa.JSON(), nullable=False),
        sa.Column('notification_config', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_runs', sa.Integer(), nullable=False),
        sa.Column('successful_runs', sa.Integer(), nullable=False),
        sa.Column('failed_runs', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['export_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_schedule_next_run', 'export_schedules', ['next_run_at', 'is_active'], unique=False)
    op.create_index('idx_schedule_template', 'export_schedules', ['template_id', 'is_active'], unique=False)
    op.create_constraint('uq_schedule_name', 'export_schedules', 'unique', ['name'])


def downgrade() -> None:
    op.drop_table('export_schedules')
    op.drop_constraint('uq_validation_rule_name_template', 'export_validation_rules', type_='unique')
    op.drop_index('idx_validation_field_type', table_name='export_validation_rules')
    op.drop_index('idx_validation_template', table_name='export_validation_rules')
    op.drop_index('idx_validation_rule_name', table_name='export_validation_rules')
    op.drop_table('export_validation_rules')
    op.drop_constraint('uq_schedule_name', 'export_schedules', type_='unique')
    op.drop_table('export_metrics')
    op.drop_index('idx_audit_user_timestamp', table_name='export_audit_logs')
    op.drop_index('idx_audit_event_type', table_name='export_audit_logs')
    op.drop_index('idx_audit_job_timestamp', table_name='export_audit_logs')
    op.drop_table('export_audit_logs')
    op.drop_index('idx_job_user_id', table_name='export_jobs')
    op.drop_index('idx_job_completed_at', table_name='export_jobs')
    op.drop_index('idx_job_started_at', table_name='export_jobs')
    op.drop_index('idx_job_created_at', table_name='export_jobs')
    op.drop_index('idx_job_priority_status', table_name='export_jobs')
    op.drop_index('idx_job_template_status', table_name='export_jobs')
    op.drop_index('idx_job_user_status', table_name='export_jobs')
    op.drop_index('idx_job_status_created', table_name='export_jobs')
    op.drop_table('export_jobs')
    op.drop_constraint('uq_template_name_format', 'export_templates', type_='unique')
    op.drop_index('idx_template_active_updated', table_name='export_templates')
    op.drop_index('idx_template_name_format', table_name='export_templates')
    op.drop_table('export_templates')