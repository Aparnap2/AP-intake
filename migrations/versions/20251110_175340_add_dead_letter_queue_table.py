"""Add dead_letter_queue table for DLQ functionality

Revision ID: 20251110_175340
Revises: add_idempotency_and_staging_tables
Create Date: 2025-11-10 17:53:40.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251110_175340'
down_revision = 'add_idempotency_and_staging_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create dead_letter_queue table and indexes."""
    # Create enum types
    op.execute("CREATE TYPE dlqstatus AS ENUM ('pending', 'processing', 'redriving', 'completed', 'failed_permanently', 'archived')")
    op.execute("CREATE TYPE dlqcategory AS ENUM ('processing_error', 'validation_error', 'network_error', 'database_error', 'timeout_error', 'business_rule_error', 'system_error', 'unknown_error')")
    op.execute("CREATE TYPE dlqpriority AS ENUM ('low', 'normal', 'high', 'critical')")

    # Create dead_letter_queue table
    op.create_table('dead_letter_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', sa.String(length=255), nullable=False),
        sa.Column('task_name', sa.String(length=255), nullable=False),
        sa.Column('task_args', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('task_kwargs', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('original_task_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_type', sa.String(length=100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('error_stack_trace', sa.Text(), nullable=True),
        sa.Column('error_category', sa.Enum('processing_error', 'validation_error', 'network_error', 'database_error', 'timeout_error', 'business_rule_error', 'system_error', 'unknown_error', name='dlqcategory'), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dlq_status', sa.Enum('pending', 'processing', 'redriving', 'completed', 'failed_permanently', 'archived', name='dlqstatus'), nullable=False),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'critical', name='dlqpriority'), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('worker_name', sa.String(length=255), nullable=True),
        sa.Column('queue_name', sa.String(length=100), nullable=True),
        sa.Column('execution_time', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('redrive_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('manual_intervention', sa.Boolean(), nullable=False, default=False),
        sa.Column('intervention_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id')
    )

    # Create indexes
    op.create_index(op.f('ix_dead_letter_queue_id'), 'dead_letter_queue', ['id'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_task_id'), 'dead_letter_queue', ['task_id'], unique=True)
    op.create_index(op.f('ix_dead_letter_queue_task_name'), 'dead_letter_queue', ['task_name'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_error_category'), 'dead_letter_queue', ['error_category'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_retry_count'), 'dead_letter_queue', ['retry_count'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_next_retry_at'), 'dead_letter_queue', ['next_retry_at'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_dlq_status'), 'dead_letter_queue', ['dlq_status'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_priority'), 'dead_letter_queue', ['priority'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_idempotency_key'), 'dead_letter_queue', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_invoice_id'), 'dead_letter_queue', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_queue_name'), 'dead_letter_queue', ['queue_name'], unique=False)
    op.create_index(op.f('ix_dead_letter_queue_created_at'), 'dead_letter_queue', ['created_at'], unique=False)

    # Create composite indexes for performance
    op.create_index('idx_dlq_status_priority', 'dead_letter_queue', ['dlq_status', 'priority'], unique=False)
    op.create_index('idx_dlq_next_retry', 'dead_letter_queue', ['next_retry_at'], unique=False)
    op.create_index('idx_dlq_task_name_status', 'dead_letter_queue', ['task_name', 'dlq_status'], unique=False)
    op.create_index('idx_dlq_category_status', 'dead_letter_queue', ['error_category', 'dlq_status'], unique=False)

    # Add relationship to invoices table
    op.execute("""
        ALTER TABLE invoices
        ADD COLUMN IF NOT EXISTS dlq_entries TEXT DEFAULT NULL;

        COMMENT ON COLUMN invoices.dlq_entries IS 'JSON array of related DLQ entry IDs';
    """)


def downgrade():
    """Remove dead_letter_queue table and related indexes."""
    # Remove composite indexes
    op.drop_index('idx_dlq_category_status', table_name='dead_letter_queue')
    op.drop_index('idx_dlq_task_name_status', table_name='dead_letter_queue')
    op.drop_index('idx_dlq_next_retry', table_name='dead_letter_queue')
    op.drop_index('idx_dlq_status_priority', table_name='dead_letter_queue')

    # Remove single column indexes
    op.drop_index(op.f('ix_dead_letter_queue_created_at'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_queue_name'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_invoice_id'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_idempotency_key'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_priority'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_dlq_status'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_next_retry_at'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_retry_count'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_error_category'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_task_name'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_task_id'), table_name='dead_letter_queue')
    op.drop_index(op.f('ix_dead_letter_queue_id'), table_name='dead_letter_queue')

    # Drop the table
    op.drop_table('dead_letter_queue')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS dlqpriority")
    op.execute("DROP TYPE IF EXISTS dlqcategory")
    op.execute("DROP TYPE IF EXISTS dlqstatus")

    # Remove column from invoices table
    op.execute("""
        ALTER TABLE invoices
        DROP COLUMN IF EXISTS dlq_entries;
    """)