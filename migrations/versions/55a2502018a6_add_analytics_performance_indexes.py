"""Add analytics performance indexes

Revision ID: 55a2502018a6
Revises: e9428b9dd556
Create Date: 2025-11-06 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '55a2502018a6'
down_revision = 'e9428b9dd556'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for analytics queries"""

    # Invoice table indexes for analytics
    op.create_index(
        'idx_invoice_created_status',
        'invoices',
        ['created_at', 'status']
    )

    op.create_index(
        'idx_invoice_vendor_created',
        'invoices',
        ['vendor_id', 'created_at']
    )

    op.create_index(
        'idx_invoice_workflow_created',
        'invoices',
        ['workflow_state', 'created_at']
    )

    # Invoice extraction indexes
    op.create_index(
        'idx_extraction_created_confidence',
        'invoice_extractions',
        ['created_at', 'parser_version']
    )

    # Validation indexes
    op.create_index(
        'idx_validation_passed_created',
        'validations',
        ['passed', 'created_at']
    )

    op.create_index(
        'idx_validation_rules_created',
        'validations',
        ['rules_version', 'created_at']
    )

    # Exception indexes for analytics
    op.create_index(
        'idx_exception_reason_resolved',
        'exceptions',
        ['reason_code', 'resolved_at']
    )

    op.create_index(
        'idx_exception_resolver_time',
        'exceptions',
        ['resolved_by', 'resolved_at', 'created_at']
    )

    # Export indexes
    op.create_index(
        'idx_export_format_status_created',
        'staged_exports',
        ['format', 'status', 'created_at']
    )

    op.create_index(
        'idx_export_destination_created',
        'staged_exports',
        ['destination', 'created_at']
    )

    # QuickBooks integration indexes for analytics
    op.create_index(
        'idx_qb_exports_created_status',
        'quickbooks_exports',
        ['created_at', 'status']
    )

    op.create_index(
        'idx_qb_exports_type_created',
        'quickbooks_exports',
        ['export_type', 'created_at']
    )

    op.create_index(
        'idx_qb_connections_created',
        'quickbooks_connections',
        ['created_at', 'status']
    )

    op.create_index(
        'idx_qb_webhooks_status_created',
        'quickbooks_webhooks',
        ['status', 'created_at']
    )

    # Create partial indexes for common analytics queries
    # Unresolved exceptions
    op.create_index(
        'idx_exception_unresolved',
        'exceptions',
        ['created_at', 'reason_code'],
        postgresql_where=sa.text('resolved_at IS NULL')
    )

    # Recent completed invoices
    op.create_index(
        'idx_invoice_recent_done',
        'invoices',
        ['created_at', 'updated_at'],
        postgresql_where=sa.text("status = 'DONE'")
    )

    # High confidence extractions
    op.execute("""
        CREATE INDEX idx_extraction_high_confidence
        ON invoice_extractions (created_at)
        WHERE (confidence_json->>'overall')::float >= 0.9
    """)

    # Failed validations
    op.create_index(
        'idx_validation_failed',
        'validations',
        ['created_at', 'rules_version'],
        postgresql_where=sa.text('passed = false')
    )

    # Active QuickBooks connections
    op.create_index(
        'idx_qb_connections_active',
        'quickbooks_connections',
        ['user_id', 'last_sync_at'],
        postgresql_where=sa.text("status = 'CONNECTED'")
    )


def downgrade():
    """Remove analytics performance indexes"""

    # Drop partial indexes first
    op.drop_index('idx_qb_connections_active', 'quickbooks_connections')
    op.drop_index('idx_validation_failed', 'validations')
    op.drop_index('idx_extraction_high_confidence', table_name='invoice_extractions')
    op.drop_index('idx_invoice_recent_done', 'invoices')
    op.drop_index('idx_exception_unresolved', 'exceptions')

    # Drop QuickBooks integration indexes
    op.drop_index('idx_qb_webhooks_status_created', 'quickbooks_webhooks')
    op.drop_index('idx_qb_connections_created', 'quickbooks_connections')
    op.drop_index('idx_qb_exports_type_created', 'quickbooks_exports')
    op.drop_index('idx_qb_exports_created_status', 'quickbooks_exports')

    # Drop regular indexes
    op.drop_index('idx_export_destination_created', 'staged_exports')
    op.drop_index('idx_export_format_status_created', 'staged_exports')
    op.drop_index('idx_exception_resolver_time', 'exceptions')
    op.drop_index('idx_exception_reason_resolved', 'exceptions')
    op.drop_index('idx_validation_rules_created', 'validations')
    op.drop_index('idx_validation_passed_created', 'validations')
    op.drop_index('idx_extraction_created_confidence', 'invoice_extractions')
    op.drop_index('idx_invoice_workflow_created', 'invoices')
    op.drop_index('idx_invoice_vendor_created', 'invoices')
    op.drop_index('idx_invoice_created_status', 'invoices')