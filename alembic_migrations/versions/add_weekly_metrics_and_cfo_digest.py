"""Add weekly metrics and CFO digest tables

Revision ID: add_weekly_metrics_and_cfo_digest
Revises: add_metrics_slo_tables
Create Date: 2025-11-10 17:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_weekly_metrics_and_cfo_digest'
down_revision = 'add_metrics_slo_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create weekly metrics aggregation and CFO digest tables."""

    # Create weekly_metrics table
    op.create_table(
        'weekly_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('week_start_date', sa.Date(), nullable=False),
        sa.Column('week_end_date', sa.Date(), nullable=False),
        sa.Column('invoices_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('auto_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('manual_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('exceptions_created', sa.Integer(), nullable=False, default=0),
        sa.Column('exceptions_resolved', sa.Integer(), nullable=False, default=0),
        sa.Column('duplicates_detected', sa.Integer(), nullable=False, default=0),
        sa.Column('avg_processing_time_hours', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('total_invoice_amount', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('auto_processing_rate', sa.Numeric(precision=5, scale=2), nullable=False, default=0),
        sa.Column('pass_rate_structural', sa.Numeric(precision=5, scale=2), nullable=False, default=0),
        sa.Column('pass_rate_math', sa.Numeric(precision=5, scale=2), nullable=False, default=0),
        sa.Column('p50_time_to_ready_minutes', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('p95_time_to_ready_minutes', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('p99_time_to_ready_minutes', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('duplicate_recall_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('exception_resolution_time_p50_hours', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('api_response_time_p95_ms', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('system_availability_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('cost_per_invoice', sa.Numeric(precision=10, scale=2), nullable=False, default=0),
        sa.Column('total_cost', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('roi_percentage', sa.Numeric(precision=5, scale=2), nullable=False, default=0),
        sa.Column('working_capital_optimization', sa.JSON(), nullable=True),
        sa.Column('performance_summary', sa.Text(), nullable=True),
        sa.Column('quality_metrics', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('week_start_date', name='uq_weekly_metrics_week_start'),
        sa.CheckConstraint('invoices_processed >= 0', name='ck_weekly_metrics_invoices_processed_non_negative'),
        sa.CheckConstraint('auto_processed >= 0', name='ck_weekly_metrics_auto_processed_non_negative'),
        sa.CheckConstraint('manual_processed >= 0', name='ck_weekly_metrics_manual_processed_non_negative'),
        sa.CheckConstraint('exceptions_created >= 0', name='ck_weekly_metrics_exceptions_created_non_negative'),
        sa.CheckConstraint('exceptions_resolved >= 0', name='ck_weekly_metrics_exceptions_resolved_non_negative'),
        sa.CheckConstraint('duplicates_detected >= 0', name='ck_weekly_metrics_duplicates_detected_non_negative'),
        sa.CheckConstraint('avg_processing_time_hours >= 0', name='ck_weekly_metrics_avg_processing_time_non_negative'),
        sa.CheckConstraint('auto_processing_rate >= 0 AND auto_processing_rate <= 100', name='ck_weekly_metrics_auto_processing_rate_range'),
        sa.CheckConstraint('pass_rate_structural >= 0 AND pass_rate_structural <= 100', name='ck_weekly_metrics_pass_rate_structural_range'),
        sa.CheckConstraint('pass_rate_math >= 0 AND pass_rate_math <= 100', name='ck_weekly_metrics_pass_rate_math_range'),
        sa.CheckConstraint('cost_per_invoice >= 0', name='ck_weekly_metrics_cost_per_invoice_non_negative'),
        sa.CheckConstraint('total_cost >= 0', name='ck_weekly_metrics_total_cost_non_negative')
    )

    # Create indexes for weekly_metrics
    op.create_index('idx_weekly_metrics_week_start', 'weekly_metrics', ['week_start_date'])
    op.create_index('idx_weekly_metrics_created_at', 'weekly_metrics', ['created_at'])
    op.create_index('idx_weekly_metrics_auto_processing_rate', 'weekly_metrics', ['auto_processing_rate'])
    op.create_index('idx_weekly_metrics_cost_per_invoice', 'weekly_metrics', ['cost_per_invoice'])

    # Create cfo_digests table
    op.create_table(
        'cfo_digests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('digest_date', sa.Date(), nullable=False),
        sa.Column('week_start_date', sa.Date(), nullable=False),
        sa.Column('week_end_date', sa.Date(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='draft'),
        sa.Column('executive_summary', sa.JSON(), nullable=False),
        sa.Column('key_metrics', sa.JSON(), nullable=False),
        sa.Column('working_capital_metrics', sa.JSON(), nullable=False),
        sa.Column('action_items', sa.JSON(), nullable=False),
        sa.Column('metrics_summary', sa.JSON(), nullable=False),
        sa.Column('digest_content', sa.Text(), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_status', sa.String(length=50), nullable=False, default='pending'),
        sa.Column('recipients', sa.JSON(), nullable=True),
        sa.Column('total_invoices_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('total_exceptions', sa.Integer(), nullable=False, default=0),
        sa.Column('cost_per_invoice', sa.Numeric(precision=10, scale=2), nullable=False, default=0),
        sa.Column('roi_percentage', sa.Numeric(precision=5, scale=2), nullable=False, default=0),
        sa.Column('generated_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('week_start_date', name='uq_cfo_digests_week_start'),
        sa.CheckConstraint('total_invoices_processed >= 0', name='ck_cfo_digests_total_invoices_non_negative'),
        sa.CheckConstraint('total_exceptions >= 0', name='ck_cfo_digests_total_exceptions_non_negative'),
        sa.CheckConstraint('cost_per_invoice >= 0', name='ck_cfo_digests_cost_per_invoice_non_negative'),
        sa.CheckConstraint('roi_percentage >= 0', name='ck_cfo_digests_roi_percentage_non_negative')
    )

    # Create indexes for cfo_digests
    op.create_index('idx_cfo_digests_digest_date', 'cfo_digests', ['digest_date'])
    op.create_index('idx_cfo_digests_week_start', 'cfo_digests', ['week_start_date'])
    op.create_index('idx_cfo_digests_status', 'cfo_digests', ['status'])
    op.create_index('idx_cfo_digests_email_sent', 'cfo_digests', ['email_sent'])
    op.create_index('idx_cfo_digests_created_at', 'cfo_digests', ['created_at'])
    op.create_index('idx_cfo_digests_delivery_status', 'cfo_digests', ['delivery_status'])

    # Create cfo_digest_schedule table for configuration
    op.create_table(
        'cfo_digest_schedule',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('delivery_day', sa.String(length=20), nullable=False, default='monday'),
        sa.Column('delivery_time', sa.String(length=10), nullable=False, default='09:00'),
        sa.Column('recipients', sa.JSON(), nullable=False),
        sa.Column('priority_threshold', sa.String(length=20), nullable=False, default='medium'),
        sa.Column('business_impact_threshold', sa.String(length=20), nullable=False, default='moderate'),
        sa.Column('include_working_capital_analysis', sa.Boolean(), nullable=False, default=True),
        sa.Column('include_action_items', sa.Boolean(), nullable=False, default=True),
        sa.Column('include_evidence_links', sa.Boolean(), nullable=False, default=True),
        sa.Column('timezone', sa.String(length=50), nullable=False, default='UTC'),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_delivery_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('delivery_day IN (\'monday\', \'tuesday\', \'wednesday\', \'thursday\', \'friday\', \'saturday\', \'sunday\')', name='ck_cfo_digest_schedule_delivery_day_valid'),
        sa.CheckConstraint('priority_threshold IN (\'critical\', \'high\', \'medium\', \'low\')', name='ck_cfo_digest_schedule_priority_threshold_valid'),
        sa.CheckConstraint('business_impact_threshold IN (\'critical\', \'high\', \'moderate\', \'low\')', name='ck_cfo_digest_schedule_business_impact_threshold_valid')
    )

    # Create index for cfo_digest_schedule
    op.create_index('idx_cfo_digest_schedule_is_active', 'cfo_digest_schedule', ['is_active'])
    op.create_index('idx_cfo_digest_schedule_next_delivery', 'cfo_digest_schedule', ['next_delivery_at'])

    # Create performance_trends table for historical analysis
    op.create_table(
        'performance_trends',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_category', sa.String(length=50), nullable=False),
        sa.Column('date_value', sa.Date(), nullable=False),
        sa.Column('value', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('target_value', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('attainment_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('trend_direction', sa.String(length=20), nullable=True),
        sa.Column('trend_strength', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('moving_average_7d', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('moving_average_30d', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('percentile_25', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('percentile_75', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('standard_deviation', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('anomaly_detected', sa.Boolean(), nullable=False, default=False),
        sa.Column('anomaly_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('forecast_value', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('forecast_confidence', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('dimensions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('metric_name', 'date_value', name='uq_performance_trends_metric_date'),
        sa.CheckConstraint('attainment_percentage >= 0 AND attainment_percentage <= 100', name='ck_performance_trends_attainment_percentage_range'),
        sa.CheckConstraint('trend_strength >= -1 AND trend_strength <= 1', name='ck_performance_trends_trend_strength_range'),
        sa.CheckConstraint('anomaly_score >= 0 AND anomaly_score <= 100', name='ck_performance_trends_anomaly_score_range'),
        sa.CheckConstraint('forecast_confidence >= 0 AND forecast_confidence <= 1', name='ck_performance_trends_forecast_confidence_range')
    )

    # Create indexes for performance_trends
    op.create_index('idx_performance_trends_metric_date', 'performance_trends', ['metric_name', 'date_value'])
    op.create_index('idx_performance_trends_category_date', 'performance_trends', ['metric_category', 'date_value'])
    op.create_index('idx_performance_trends_anomaly', 'performance_trends', ['anomaly_detected'])
    op.create_index('idx_performance_trends_created_at', 'performance_trends', ['created_at'])

    # Insert default schedule configuration
    op.execute("""
        INSERT INTO cfo_digest_schedule (
            id,
            is_active,
            delivery_day,
            delivery_time,
            recipients,
            priority_threshold,
            business_impact_threshold,
            include_working_capital_analysis,
            include_action_items,
            include_evidence_links,
            timezone,
            created_by
        ) VALUES (
            gen_random_uuid(),
            true,
            'monday',
            '09:00',
            '["cfo@company.com", "finance-team@company.com", "ap-manager@company.com"]',
            'medium',
            'moderate',
            true,
            true,
            true,
            'UTC',
            'system'
        )
    """)


def downgrade():
    """Drop weekly metrics and CFO digest tables."""

    # Drop tables in reverse order of creation
    op.drop_table('performance_trends')
    op.drop_table('cfo_digest_schedule')
    op.drop_table('cfo_digests')
    op.drop_table('weekly_metrics')