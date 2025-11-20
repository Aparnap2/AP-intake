"""add_audit_metadata_column

Revision ID: 95e18dd68f0f
Revises: 55a2502018a6
Create Date: 2025-11-07 11:07:24.671047

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95e18dd68f0f'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add audit_metadata column to storage_audit table if it doesn't exist
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'storage_audit' AND column_name = 'audit_metadata'
    """))

    if not result.fetchone():
        op.add_column('storage_audit', sa.Column('audit_metadata', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove audit_metadata column from storage_audit table
    op.drop_column('storage_audit', 'audit_metadata')