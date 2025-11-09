"""Add metrics and SLO tables

Revision ID: add_metrics_slo_tables
Revises: initial_schema
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_metrics_slo_tables'
down_revision = 'initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Create enums
    op.execute("CREATE TYPE slitype AS ENUM ('time_to_ready', 'validation_pass_rate', 'duplicate_recall', 'approval_latency', 'processing_success_rate', 'extraction_accuracy', 'exception_resolution_time')")
    op.execute("CREATE TYPE sloperiod AS ENUM ('hourly', 'daily', 'weekly', 'monthly', 'quarterly')")
    op.execute("CREATE TYPE alertseverity AS ENUM ('info', 'warning', 'critical')")

    # Create slo_definitions table
    op.create_table('slo_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('sli_type', sa.Enum('time_to_ready', 'validation_pass_rate', 'duplicate_recall', 'approval_latency', 'processing_success_rate', 'extraction_accuracy', 'exception_resolution_time', name='slitype'), nullable=False),
        sa.Column('target_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('target_value', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('target_unit', sa.String(length=20), nullable=True),
        sa.Column('error_budget_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('alerting_threshold_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('measurement_period', sa.Enum('hourly', 'daily', 'weekly', 'monthly', 'quarterly', name='sloperiod'), nullable=False),
        sa.Column('burn_rate_alert_threshold', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('slos_owner', sa.String(length=100), nullable=True),
        sa.Column('notification_channels', sa.JSON(), nullable=True),
        sa.Constraint('check_target_percentage_range', sa.CheckConstraint('target_percentage > 0 AND target_percentage <= 100', name='check_target_percentage_range')),
        sa.Constraint('check_error_budget_range', sa.CheckConstraint('error_budget_percentage >= 0 AND error_budget_percentage <= 100', name='check_error_budget_range')),
        sa.Constraint('check_alert_threshold_range', sa.CheckConstraint('alerting_threshold_percentage >= 0 AND alerting_threshold_percentage <= 100', name='check_alert_threshold_range')),
        sa.ForeignKeyConstraint(['id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_slo_type_active', 'slo_definitions', ['sli_type', 'is_active'], unique=False)
    op.create_index('idx_slo_period_active', 'slo_definitions', ['measurement_period', 'is_active'], unique=False)
    op.create_index(op.f('ix_slo_definitions_name'), 'slo_definitions', ['name'], unique=True)

    # Create sli_measurements table
    op.create_table('sli_measurements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('slo_definition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('measurement_period', sa.Enum('hourly', 'daily', 'weekly', 'monthly', 'quarterly', name='sloperiod'), nullable=False),
        sa.Column('actual_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('target_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('achieved_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('good_events_count', sa.Integer(), nullable=False),
        sa.Column('total_events_count', sa.Integer(), nullable=False),
        sa.Column('error_budget_consumed', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('measurement_metadata', sa.JSON(), nullable=True),
        sa.Column('data_quality_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Constraint('check_achieved_percentage_range', sa.CheckConstraint('achieved_percentage >= 0 AND achieved_percentage <= 100', name='check_achieved_percentage_range')),
        sa.Constraint('check_error_budget_consumed_range', sa.CheckConstraint('error_budget_consumed >= 0 AND error_budget_consumed <= 100', name='check_error_budget_consumed_range')),
        sa.Constraint('check_total_events_positive', sa.CheckConstraint('total_events_count > 0', name='check_total_events_positive')),
        sa.ForeignKeyConstraint(['slo_definition_id'], ['slo_definitions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_measurement_slo_period', 'sli_measurements', ['slo_definition_id', 'period_start', 'period_end'], unique=False)
    op.create_index('idx_measurement_timeline', 'sli_measurements', ['period_start', 'period_end'], unique=False)
    op.create_index('idx_measurement_period_type', 'sli_measurements', ['measurement_period', 'period_start'], unique=False)

    # Create slo_alerts table
    op.create_table('slo_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('slo_definition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('measurement_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.Enum('info', 'warning', 'critical', name='alertseverity'), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('current_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('target_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('breached_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=False),
        sa.Column('notification_attempts', sa.Integer(), nullable=False),
        sa.Column('last_notification_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_metadata', sa.JSON(), nullable=True),
        sa.Constraint('check_notification_attempts_non_negative', sa.CheckConstraint('notification_attempts >= 0', name='check_notification_attempts_non_negative')),
        sa.ForeignKeyConstraint(['measurement_id'], ['sli_measurements.id'], ),
        sa.ForeignKeyConstraint(['slo_definition_id'], ['slo_definitions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_alert_slo_severity', 'slo_alerts', ['slo_definition_id', 'severity'], unique=False)
    op.create_index('idx_alert_type_created', 'slo_alerts', ['alert_type', 'created_at'], unique=False)
    op.create_index('idx_alert_resolved', 'slo_alerts', ['resolved_at', 'severity'], unique=False)

    # Create invoice_metrics table
    op.create_table('invoice_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('parsing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validation_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ready_for_approval_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('time_to_ready_seconds', sa.Float(), nullable=True),
        sa.Column('approval_latency_seconds', sa.Float(), nullable=True),
        sa.Column('total_processing_time_seconds', sa.Float(), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('validation_passed', sa.Boolean(), nullable=True),
        sa.Column('exception_count', sa.Integer(), nullable=False),
        sa.Column('duplicate_detected', sa.Boolean(), nullable=False),
        sa.Column('requires_human_review', sa.Boolean(), nullable=False),
        sa.Column('processing_step_count', sa.Integer(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('workflow_id', sa.String(length=100), nullable=True),
        sa.Column('processing_metadata', sa.JSON(), nullable=True),
        sa.Constraint('check_time_to_ready_non_negative', sa.CheckConstraint('time_to_ready_seconds >= 0', name='check_time_to_ready_non_negative')),
        sa.Constraint('check_approval_latency_non_negative', sa.CheckConstraint('approval_latency_seconds >= 0', name='check_approval_latency_non_negative')),
        sa.Constraint('check_total_processing_time_non_negative', sa.CheckConstraint('total_processing_time_seconds >= 0', name='check_total_processing_time_non_negative')),
        sa.Constraint('check_confidence_range', sa.CheckConstraint('extraction_confidence >= 0 AND extraction_confidence <= 1', name='check_confidence_range')),
        sa.Constraint('check_step_count_non_negative', sa.CheckConstraint('processing_step_count >= 0', name='check_step_count_non_negative')),
        sa.Constraint('check_retry_count_non_negative', sa.CheckConstraint('retry_count >= 0', name='check_retry_count_non_negative')),
        sa.Constraint('check_file_size_non_negative', sa.CheckConstraint('file_size_bytes >= 0', name='check_file_size_non_negative')),
        sa.Constraint('check_page_count_non_negative', sa.CheckConstraint('page_count >= 0', name='check_page_count_non_negative')),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_metrics_invoice_timeline', 'invoice_metrics', ['invoice_id', 'received_at'], unique=False)
    op.create_index('idx_metrics_ready_time', 'invoice_metrics', ['ready_for_approval_at', 'time_to_ready_seconds'], unique=False)
    op.create_index('idx_metrics_approval_time', 'invoice_metrics', ['approved_at', 'approval_latency_seconds'], unique=False)
    op.create_index('idx_metrics_validation_status', 'invoice_metrics', ['validation_passed', 'exception_count'], unique=False)
    op.create_index('idx_metrics_duplicate_detection', 'invoice_metrics', ['duplicate_detected', 'received_at'], unique=False)
    op.create_index('idx_metrics_processing_efficiency', 'invoice_metrics', ['processing_step_count', 'total_processing_time_seconds'], unique=False)

    # Create system_metrics table
    op.create_table('system_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_category', sa.String(length=50), nullable=False),
        sa.Column('measurement_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('value', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('dimensions', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_system_metric_name_time', 'system_metrics', ['metric_name', 'measurement_timestamp'], unique=False)
    op.create_index('idx_system_metric_category_time', 'system_metrics', ['metric_category', 'measurement_timestamp'], unique=False)
    op.create_index('idx_system_metric_source', 'system_metrics', ['data_source', 'measurement_timestamp'], unique=False)

    # Create metrics_configuration table
    op.create_table('metrics_configuration',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('config_key', sa.String(length=100), nullable=False),
        sa.Column('config_category', sa.String(length=50), nullable=False),
        sa.Column('config_value', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.String(length=100), nullable=True),
        sa.Constraint('check_version_positive', sa.CheckConstraint('version > 0', name='check_version_positive')),
        sa.ForeignKeyConstraint(['id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_metrics_config_category_active', 'metrics_configuration', ['config_category', 'is_active'], unique=False)
    op.create_index(op.f('ix_metrics_configuration_config_key'), 'metrics_configuration', ['config_key'], unique=True)


def downgrade():
    # Drop tables in reverse order of creation
    op.drop_table('metrics_configuration')
    op.drop_table('system_metrics')
    op.drop_table('invoice_metrics')
    op.drop_table('slo_alerts')
    op.drop_table('sli_measurements')
    op.drop_table('slo_definitions')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS sloperiod")
    op.execute("DROP TYPE IF EXISTS slitype")