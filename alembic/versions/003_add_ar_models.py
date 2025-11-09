"""Add AR invoice and customer models

Revision ID: 003_add_ar_models
Revises: 001_add_ingestion_system
Create Date: 2024-01-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_ar_models'
down_revision: Union[str, None] = '001_add_ingestion_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create AR invoice and customer tables."""

    # Create customers table
    op.create_table('customers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('credit_limit', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('payment_terms_days', sa.String(length=10), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.CheckConstraint('credit_limit >= 0', name='check_customer_credit_limit_positive'),
        sa.CheckConstraint('currency ~ \'^[A-Z]{3}$\'', name='check_customer_currency_format'),
        sa.CheckConstraint("CASE WHEN email IS NOT NULL THEN email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$' ELSE true END", name='check_customer_email_format'),
        sa.CheckConstraint("name <> ''", name='check_customer_name_not_empty'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('tax_id')
    )
    op.create_index(op.f('ix_customer_active_name'), 'customers', ['active', 'name'], unique=False)
    op.create_index(op.f('ix_customer_active'), 'customers', ['active'], unique=False)
    op.create_index(op.f('ix_customer_name'), 'customers', ['name'], unique=False)
    op.create_index(op.f('ix_customer_tax_id'), 'customers', ['tax_id'], unique=False)

    # Create ar_invoices table
    op.create_table('ar_invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_number', sa.String(length=100), nullable=False),
        sa.Column('invoice_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('outstanding_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'WRITE_OFF', 'DISPUTED', name='paymentstatus'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('collection_priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'URGENT', name='collectionpriority'), nullable=False),
        sa.Column('last_collection_attempt', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collection_notes', sa.Text(), nullable=True),
        sa.Column('early_payment_discount_percent', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('early_payment_discount_days', sa.String(length=10), nullable=True),
        sa.Column('expected_payment_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('working_capital_impact', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.CheckConstraint('currency ~ \'^[A-Z]{3}$\'', name='check_ar_currency_format'),
        sa.CheckConstraint('due_date >= invoice_date', name='check_ar_due_date_after_invoice'),
        sa.CheckConstraint('paid_amount >= 0', name='check_ar_paid_amount_positive'),
        sa.CheckConstraint('outstanding_amount >= 0', name='check_ar_outstanding_amount_positive'),
        sa.CheckConstraint('total_amount = subtotal + tax_amount', name='check_ar_amount_math'),
        sa.CheckConstraint('total_amount >= 0', name='check_ar_total_amount_positive'),
        sa.CheckConstraint("invoice_number <> ''", name='check_ar_invoice_number_not_empty'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number')
    )
    op.create_index(op.f('ix_ar_invoice_collection_priority'), 'ar_invoices', ['collection_priority'], unique=False)
    op.create_index(op.f('ix_ar_invoice_customer_id'), 'ar_invoices', ['customer_id'], unique=False)
    op.create_index(op.f('ix_ar_invoice_customer_status'), 'ar_invoices', ['customer_id', 'status'], unique=False)
    op.create_index(op.f('ix_ar_invoice_dates'), 'ar_invoices', ['invoice_date', 'due_date', 'status'], unique=False)
    op.create_index(op.f('ix_ar_invoice_due_date'), 'ar_invoices', ['due_date'], unique=False)
    op.create_index(op.f('ix_ar_invoice_invoice_number'), 'ar_invoices', ['invoice_number'], unique=True)
    op.create_index(op.f('ix_ar_invoice_status'), 'ar_invoices', ['status'], unique=False)


def downgrade() -> None:
    """Drop AR invoice and customer tables."""

    # Drop ar_invoices table
    op.drop_index(op.f('ix_ar_invoice_status'), table_name='ar_invoices')
    op.drop_index(op.f('ix_ar_invoice_invoice_number'), table_name='ar_invoices')
    op.drop_index(op.f('ix_ar_invoice_due_date'), table_name='ar_invoices')
    op.drop_index(op.f('ix_ar_invoice_dates'), table_name='ar_invoices')
    op.drop_index(op.f('ix_ar_invoice_customer_status'), table_name='ar_invoices')
    op.drop_index(op.f('ix_ar_invoice_customer_id'), table_name='ar_invoices')
    op.drop_index(op.f('ix_ar_invoice_collection_priority'), table_name='ar_invoices')
    op.drop_table('ar_invoices')

    # Drop customers table
    op.drop_index(op.f('ix_customer_tax_id'), table_name='customers')
    op.drop_index(op.f('ix_customer_name'), table_name='customers')
    op.drop_index(op.f('ix_customer_active'), table_name='customers')
    op.drop_index(op.f('ix_customer_active_name'), table_name='customers')
    op.drop_table('customers')