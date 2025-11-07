"""Add QuickBooks integration tables

Revision ID: 797c75afebae
Revises: b1a2c3d4e5f6
Create Date: 2025-11-06 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '797c75afebae'
down_revision = 'b1a2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    """Create QuickBooks integration tables."""

    # Create quickbooks_connections table
    op.create_table(
        'quickbooks_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('realm_id', sa.String(length=50), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'CONNECTED', 'DISCONNECTED', 'ERROR', 'EXPIRED', name='quickbooksconnectionstatus'), nullable=False),
        sa.Column('user_info', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('company_info', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('default_expense_account_id', sa.String(length=50), nullable=True),
        sa.Column('auto_export_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('webhook_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['base_uuid_mixin.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_quickbooks_connections_realm_status', 'quickbooks_connections', ['realm_id', 'status'], unique=False)
    op.create_index('idx_quickbooks_connections_token_expiry', 'quickbooks_connections', ['token_expires_at', 'status'], unique=False)
    op.create_index('idx_quickbooks_connections_user_status', 'quickbooks_connections', ['user_id', 'status'], unique=False)
    op.create_index('uq_user_realm', 'quickbooks_connections', ['user_id', 'realm_id'], unique=True)

    # Create quickbooks_exports table
    op.create_table(
        'quickbooks_exports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quickbooks_bill_id', sa.String(length=50), nullable=True),
        sa.Column('export_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('dry_run', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('request_payload', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('response_payload', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['connection_id'], ['quickbooks_connections.id'], ),
        sa.ForeignKeyConstraint(['id'], ['base_uuid_mixin.id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_quickbooks_exports_connection_status', 'quickbooks_exports', ['connection_id', 'status'], unique=False)
    op.create_index('idx_quickbooks_exports_export_type_status', 'quickbooks_exports', ['export_type', 'status'], unique=False)
    op.create_index('idx_quickbooks_exports_invoice_export', 'quickbooks_exports', ['invoice_id', 'status'], unique=False)
    op.create_index('idx_quickbooks_exports_quickbooks_bill', 'quickbooks_exports', ['quickbooks_bill_id'], unique=False)
    op.create_index('idx_quickbooks_exports_retry_queue', 'quickbooks_exports', ['next_retry_at', 'status'], unique=False)

    # Create quickbooks_webhooks table
    op.create_table(
        'quickbooks_webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('webhook_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=50), nullable=False),
        sa.Column('operation', sa.String(length=20), nullable=False),
        sa.Column('raw_payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('processed_payload', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['id'], ['base_uuid_mixin.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_quickbooks_webhooks_entity_operation', 'quickbooks_webhooks', ['entity_type', 'entity_id', 'operation'], unique=False)
    op.create_index('idx_quickbooks_webhooks_status_created', 'quickbooks_webhooks', ['status', 'created_at'], unique=False)
    op.create_index('idx_quickbooks_webhooks_webhook_event', 'quickbooks_webhooks', ['webhook_id', 'event_type'], unique=False)

    # Create quickbooks_vendor_mappings table
    op.create_table(
        'quickbooks_vendor_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('local_vendor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quickbooks_vendor_id', sa.String(length=50), nullable=False),
        sa.Column('quickbooks_vendor_name', sa.String(length=255), nullable=False),
        sa.Column('auto_sync_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('local_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('quickbooks_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['connection_id'], ['quickbooks_connections.id'], ),
        sa.ForeignKeyConstraint(['id'], ['base_uuid_mixin.id'], ),
        sa.ForeignKeyConstraint(['local_vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_quickbooks_vendor_mappings_local_vendor', 'quickbooks_vendor_mappings', ['local_vendor_id'], unique=False)
    op.create_index('idx_quickbooks_vendor_mappings_qb_vendor_name', 'quickbooks_vendor_mappings', ['quickbooks_vendor_name'], unique=False)
    op.create_index('uq_connection_local_vendor', 'quickbooks_vendor_mappings', ['connection_id', 'local_vendor_id'], unique=True)
    op.create_index('uq_connection_qb_vendor', 'quickbooks_vendor_mappings', ['connection_id', 'quickbooks_vendor_id'], unique=True)

    # Create quickbooks_account_mappings table
    op.create_table(
        'quickbooks_account_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quickbooks_account_id', sa.String(length=50), nullable=False),
        sa.Column('quickbooks_account_name', sa.String(length=255), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=False),
        sa.Column('account_subtype', sa.String(length=50), nullable=True),
        sa.Column('is_default_expense', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_default_cogs', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('quickbooks_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['connection_id'], ['quickbooks_connections.id'], ),
        sa.ForeignKeyConstraint(['id'], ['base_uuid_mixin.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_quickbooks_account_mappings_account_name', 'quickbooks_account_mappings', ['quickbooks_account_name'], unique=False)
    op.create_index('idx_quickbooks_account_mappings_account_type', 'quickbooks_account_mappings', ['account_type', 'is_default_expense'], unique=False)
    op.create_index('uq_connection_qb_account', 'quickbooks_account_mappings', ['connection_id', 'quickbooks_account_id'], unique=True)


def downgrade():
    """Drop QuickBooks integration tables."""

    # Drop tables in reverse order of creation
    op.drop_index('uq_connection_qb_account', 'quickbooks_account_mappings')
    op.drop_index('idx_quickbooks_account_mappings_account_type', 'quickbooks_account_mappings')
    op.drop_index('idx_quickbooks_account_mappings_account_name', 'quickbooks_account_mappings')
    op.drop_table('quickbooks_account_mappings')

    op.drop_index('uq_connection_qb_vendor', 'quickbooks_vendor_mappings')
    op.drop_index('uq_connection_local_vendor', 'quickbooks_vendor_mappings')
    op.drop_index('idx_quickbooks_vendor_mappings_qb_vendor_name', 'quickbooks_vendor_mappings')
    op.drop_index('idx_quickbooks_vendor_mappings_local_vendor', 'quickbooks_vendor_mappings')
    op.drop_table('quickbooks_vendor_mappings')

    op.drop_index('idx_quickbooks_webhooks_webhook_event', 'quickbooks_webhooks')
    op.drop_index('idx_quickbooks_webhooks_status_created', 'quickbooks_webhooks')
    op.drop_index('idx_quickbooks_webhooks_entity_operation', 'quickbooks_webhooks')
    op.drop_table('quickbooks_webhooks')

    op.drop_index('idx_quickbooks_exports_retry_queue', 'quickbooks_exports')
    op.drop_index('idx_quickbooks_exports_quickbooks_bill', 'quickbooks_exports')
    op.drop_index('idx_quickbooks_exports_invoice_export', 'quickbooks_exports')
    op.drop_index('idx_quickbooks_exports_export_type_status', 'quickbooks_exports')
    op.drop_index('idx_quickbooks_exports_connection_status', 'quickbooks_exports')
    op.drop_table('quickbooks_exports')

    op.drop_index('uq_user_realm', 'quickbooks_connections')
    op.drop_index('idx_quickbooks_connections_user_status', 'quickbooks_connections')
    op.drop_index('idx_quickbooks_connections_token_expiry', 'quickbooks_connections')
    op.drop_index('idx_quickbooks_connections_realm_status', 'quickbooks_connections')
    op.drop_table('quickbooks_connections')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS quickbooksconnectionstatus')