"""Make vendor_id nullable in invoices table

Revision ID: a1b2c3d4e5f7
Revises: 95e18dd68f0f
Create Date: 2025-11-07 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '95e18dd68f0f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make vendor_id nullable in invoices table
    op.alter_column('invoices', 'vendor_id',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade() -> None:
    # Make vendor_id not nullable again (backwards incompatible)
    op.alter_column('invoices', 'vendor_id',
                    existing_type=sa.UUID(),
                    nullable=False)