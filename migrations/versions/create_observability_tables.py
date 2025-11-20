"""Create observability tables for metrics, alerts, and runbook execution

Revision ID: observability_001
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'observability_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create trace_spans table
    op.create_table('trace_spans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trace_id', sa.String(length=64), nullable=False),
        sa.Column('span_id', sa.String(length=16), nullable=False),
        sa.Column('parent_span_id', sa.String(length=16), nullable=True),
        sa.Column('operation_name', sa.String(length=255), nullable=False),
        sa.Column('component', sa.String(length=100), nullable=False),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('status_code', sa.String(length=20), nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('attributes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('resource_attributes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('events', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('links', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('operation_cost', sa.Float(), nullable=True),
        sa.Column('llm_tokens_used', sa.Integer(), nullable=True),
        sa.Column('llm_cost', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trace_id', 'span_id', name='uq_trace_span')
    )
    op.create_index('idx_trace_spans_trace_id', 'trace_spans', ['trace_id'], unique=False)
    op.create_index('idx_trace_spans_component', 'trace_spans', ['component'], unique=False)
    op.create_index('idx_trace_spans_operation_name', 'trace_spans', ['operation_name'], unique=False)
    op.create_index('idx_trace_spans_start_time', 'trace_spans', ['start_time'], unique=False)
    op.create_index('idx_trace_spans_duration_ms', 'trace_spans', ['duration_ms'], unique=False)
    op.create_index('idx_trace_spans_service_name', 'trace_spans', ['service_name'], unique=False)

    # Create alert_rules table
    op.create_table('alert_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('condition', sa.Text(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('operator', sa.String(length=10), nullable=False),
        sa.Column('evaluation_window_seconds', sa.Integer(), nullable=True),
        sa.Column('consecutive_breaches', sa.Integer(), nullable=True),
        sa.Column('cooldown_period_seconds', sa.Integer(), nullable=True),
        sa.Column('notification_channels', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('escalation_policy_id', sa.String(length=100), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_alert_rules_name')
    )

    # Create alerts table
    op.create_table('alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(length=255), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=255), nullable=True),
        sa.Column('acknowledgment_note', sa.Text(), nullable=True),
        sa.Column('escalation_level', sa.Integer(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_notification_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_count', sa.Integer(), nullable=True),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_alerts_rule_id', 'alerts', ['rule_id'], unique=False)
    op.create_index('idx_alerts_severity', 'alerts', ['severity'], unique=False)
    op.create_index('idx_alerts_status', 'alerts', ['status'], unique=False)
    op.create_index('idx_alerts_evaluated_at', 'alerts', ['evaluated_at'], unique=False)
    op.create_index('idx_alerts_created_at', 'alerts', ['created_at'], unique=False)

    # Create runbook_executions table
    op.create_table('runbook_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('runbook_id', sa.String(length=100), nullable=False),
        sa.Column('runbook_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('current_step', sa.String(length=100), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=True),
        sa.Column('completed_steps', sa.Integer(), nullable=True),
        sa.Column('failed_steps', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('trigger_context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('execution_context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('step_results', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('approval_note', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(length=255), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_runbook_executions_runbook_id', 'runbook_executions', ['runbook_id'], unique=False)
    op.create_index('idx_runbook_executions_status', 'runbook_executions', ['status'], unique=False)
    op.create_index('idx_runbook_executions_started_at', 'runbook_executions', ['started_at'], unique=False)
    op.create_index('idx_runbook_executions_triggered_by', 'runbook_executions', ['triggered_by'], unique=False)

    # Create runbook_step_executions table
    op.create_table('runbook_step_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', sa.String(length=100), nullable=False),
        sa.Column('step_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('api_endpoint', sa.String(length=500), nullable=True),
        sa.Column('script_path', sa.String(length=500), nullable=True),
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('dependencies', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('parallel', sa.Boolean(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['runbook_executions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_runbook_step_executions_execution_id', 'runbook_step_executions', ['execution_id'], unique=False)
    op.create_index('idx_runbook_step_executions_step_id', 'runbook_step_executions', ['step_id'], unique=False)
    op.create_index('idx_runbook_step_executions_status', 'runbook_step_executions', ['status'], unique=False)
    op.create_index('idx_runbook_step_executions_started_at', 'runbook_step_executions', ['started_at'], unique=False)

    # Create system_health_checks table
    op.create_table('system_health_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('check_name', sa.String(length=255), nullable=False),
        sa.Column('component', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metrics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('warning_threshold_ms', sa.Integer(), nullable=True),
        sa.Column('critical_threshold_ms', sa.Integer(), nullable=True),
        sa.Column('check_type', sa.String(length=50), nullable=False),
        sa.Column('endpoint_url', sa.String(length=500), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_system_health_checks_component', 'system_health_checks', ['component'], unique=False)
    op.create_index('idx_system_health_checks_status', 'system_health_checks', ['status'], unique=False)
    op.create_index('idx_system_health_checks_checked_at', 'system_health_checks', ['checked_at'], unique=False)
    op.create_index('idx_system_health_checks_check_name', 'system_health_checks', ['check_name'], unique=False)

    # Create performance_metrics table
    op.create_table('performance_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_name', sa.String(length=255), nullable=False),
        sa.Column('metric_category', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('dimensions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('measurement_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('data_source', sa.String(length=100), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_performance_metrics_metric_name', 'performance_metrics', ['metric_name'], unique=False)
    op.create_index('idx_performance_metrics_category', 'performance_metrics', ['metric_category'], unique=False)
    op.create_index('idx_performance_metrics_timestamp', 'performance_metrics', ['measurement_timestamp'], unique=False)
    op.create_index('idx_performance_metrics_data_source', 'performance_metrics', ['data_source'], unique=False)

    # Create other observability tables...
    # (anomaly_detection, alert_suppression, dashboard_configurations omitted for brevity)


def downgrade():
    # Drop tables in reverse order of creation
    op.drop_index('idx_performance_metrics_data_source', table_name='performance_metrics')
    op.drop_index('idx_performance_metrics_timestamp', table_name='performance_metrics')
    op.drop_index('idx_performance_metrics_category', table_name='performance_metrics')
    op.drop_index('idx_performance_metrics_metric_name', table_name='performance_metrics')
    op.drop_table('performance_metrics')

    op.drop_index('idx_system_health_checks_check_name', table_name='system_health_checks')
    op.drop_index('idx_system_health_checks_checked_at', table_name='system_health_checks')
    op.drop_index('idx_system_health_checks_status', table_name='system_health_checks')
    op.drop_index('idx_system_health_checks_component', table_name='system_health_checks')
    op.drop_table('system_health_checks')

    op.drop_index('idx_runbook_step_executions_started_at', table_name='runbook_step_executions')
    op.drop_index('idx_runbook_step_executions_status', table_name='runbook_step_executions')
    op.drop_index('idx_runbook_step_executions_step_id', table_name='runbook_step_executions')
    op.drop_index('idx_runbook_step_executions_execution_id', table_name='runbook_step_executions')
    op.drop_table('runbook_step_executions')

    op.drop_index('idx_runbook_executions_triggered_by', table_name='runbook_executions')
    op.drop_index('idx_runbook_executions_started_at', table_name='runbook_executions')
    op.drop_index('idx_runbook_executions_status', table_name='runbook_executions')
    op.drop_index('idx_runbook_executions_runbook_id', table_name='runbook_executions')
    op.drop_table('runbook_executions')

    op.drop_index('idx_alerts_created_at', table_name='alerts')
    op.drop_index('idx_alerts_evaluated_at', table_name='alerts')
    op.drop_index('idx_alerts_status', table_name='alerts')
    op.drop_index('idx_alerts_severity', table_name='alerts')
    op.drop_index('idx_alerts_rule_id', table_name='alerts')
    op.drop_table('alerts')

    op.drop_table('alert_rules')

    op.drop_index('idx_trace_spans_service_name', table_name='trace_spans')
    op.drop_index('idx_trace_spans_duration_ms', table_name='trace_spans')
    op.drop_index('idx_trace_spans_start_time', table_name='trace_spans')
    op.drop_index('idx_trace_spans_operation_name', table_name='trace_spans')
    op.drop_index('idx_trace_spans_component', table_name='trace_spans')
    op.drop_index('idx_trace_spans_trace_id', table_name='trace_spans')
    op.drop_table('trace_spans')