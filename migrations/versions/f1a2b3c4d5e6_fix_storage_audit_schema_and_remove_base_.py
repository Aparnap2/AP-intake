"""Fix storage audit schema and remove base_uuid_mixin constraints

Revision ID: f1a2b3c4d5e6
Revises: 55a2502018a6
Create Date: 2025-11-07 10:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = '55a2502018a6'
branch_labels = None
depends_on = None


def upgrade():
    """Fix schema issues"""

    # Add missing audit_metadata column to storage_audit table
    op.add_column('storage_audit', sa.Column('audit_metadata', sa.Text(), nullable=True))

    # Drop foreign key constraints that reference base_uuid_mixin since we're using mixins directly
    op.drop_constraint('invoices_id_fkey', 'invoices', type_='foreignkey')
    op.drop_constraint('vendors_id_fkey', 'vendors', type_='foreignkey')
    op.drop_constraint('purchase_orders_id_fkey', 'purchase_orders', type_='foreignkey')
    op.drop_constraint('goods_receipt_notes_id_fkey', 'goods_receipt_notes', type_='foreignkey')
    op.drop_constraint('invoice_extractions_id_fkey', 'invoice_extractions', type_='foreignkey')
    op.drop_constraint('validations_id_fkey', 'validations', type_='foreignkey')
    op.drop_constraint('exceptions_id_fkey', 'exceptions', type_='foreignkey')
    op.drop_constraint('staged_exports_id_fkey', 'staged_exports', type_='foreignkey')

    # Drop the base_uuid_mixin table as it's not needed
    op.drop_table('base_uuid_mixin')


def downgrade():
    """Revert schema changes"""

    # Recreate base_uuid_mixin table
    op.create_table('base_uuid_mixin',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Add back foreign key constraints
    op.create_foreign_key('invoices_id_fkey', 'invoices', 'base_uuid_mixin', ['id'], ['id'])
    op.create_foreign_key('vendors_id_fkey', 'vendors', 'base_uuid_mixin', ['id'], ['id'])
    op.create_foreign_key('purchase_orders_id_fkey', 'purchase_orders', 'base_uuid_mixin', ['id'], ['id'])
    op.create_foreign_key('goods_receipt_notes_id_fkey', 'goods_receipt_notes', 'base_uuid_mixin', ['id'], ['id'])
    op.create_foreign_key('invoice_extractions_id_fkey', 'invoice_extractions', 'base_uuid_mixin', ['id'], ['id'])
    op.create_foreign_key('validations_id_fkey', 'validations', 'base_uuid_mixin', ['id'], ['id'])
    op.create_foreign_key('exceptions_id_fkey', 'exceptions', 'base_uuid_mixin', ['id'], ['id'])
    op.create_foreign_key('staged_exports_id_fkey', 'staged_exports', 'base_uuid_mixin', ['id'], ['id'])

    # Remove audit_metadata column
    op.drop_column('storage_audit', 'audit_metadata')