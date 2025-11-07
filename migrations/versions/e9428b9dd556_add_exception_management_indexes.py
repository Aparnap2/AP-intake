"""Add exception management indexes

Revision ID: e9428b9dd556
Revises: 797c75afebae
Create Date: 2025-11-06 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e9428b9dd556'
down_revision = '797c75afebae'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for exception management."""

    # Enable pg_trgm extension for advanced text search (if not already enabled)
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception:
        # Extension might already exist or we don't have permissions
        pass

    # Exception table indexes
    op.create_index('idx_exception_invoice_status', 'exceptions', ['invoice_id', 'resolved_at'])
    op.create_index('idx_exception_reason_created', 'exceptions', ['reason_code', 'created_at'])
    op.create_index('idx_exception_resolved_by', 'exceptions', ['resolved_by', 'resolved_at'])
    op.create_index('idx_exception_created_at', 'exceptions', ['created_at'])
    op.create_index('idx_exception_resolved_at', 'exceptions', ['resolved_at'])

    # JSON field indexes for filtering (PostgreSQL optimized indexes)
    # For exact text equality matches, use B-tree indexes on extracted text
    op.execute("""
        CREATE INDEX idx_exception_category
        ON exceptions USING btree ((details_json->>'category'))
    """)

    op.execute("""
        CREATE INDEX idx_exception_severity
        ON exceptions USING btree ((details_json->>'severity'))
    """)

    op.execute("""
        CREATE INDEX idx_exception_status
        ON exceptions USING btree ((details_json->>'status'))
    """)

    # Note: GIN indexes on JSON type require jsonb_path_ops operator class with JSONB
    # For JSON type, we'll rely on the btree indexes above for JSON field queries

    # For advanced text search with trigrams (if pg_trgm is available)
    # This provides better performance for LIKE and ILIKE queries
    try:
        op.execute("""
            CREATE INDEX idx_exception_category_trgm
            ON exceptions USING gin ((details_json->>'category') gin_trgm_ops)
        """)
    except Exception:
        # Trigram indexes failed (likely extension not available), continue without them
        pass

    # Add constraints for data integrity
    op.create_check_constraint(
        'check_exception_reason_code_not_empty',
        'exceptions',
        "reason_code <> ''"
    )

    op.create_check_constraint(
        'check_exception_details_not_null',
        'exceptions',
        "details_json IS NOT NULL"
    )

    # Storage audit performance indexes
    op.create_index('idx_storage_audit_operation_status', 'storage_audit', ['operation', 'operation_status'])
    op.create_index('idx_storage_audit_user_session', 'storage_audit', ['user_id', 'session_id'])
    op.create_index('idx_storage_audit_file_hash_created', 'storage_audit', ['file_hash', 'created_at'])
    op.create_index('idx_storage_audit_created_at_desc', 'storage_audit', ['created_at'], unique=False, postgresql_using='btree')

    # File deduplication performance indexes
    op.create_index('idx_file_deduplication_reference_count', 'file_deduplication', ['reference_count'])
    op.create_index('idx_file_deduplication_first_seen', 'file_deduplication', ['first_seen'])
    op.create_index('idx_file_deduplication_is_compressed', 'file_deduplication', ['is_compressed'])


def downgrade():
    """Remove exception management indexes."""

    # Remove storage audit indexes
    op.drop_index('idx_file_deduplication_is_compressed', 'file_deduplication')
    op.drop_index('idx_file_deduplication_first_seen', 'file_deduplication')
    op.drop_index('idx_file_deduplication_reference_count', 'file_deduplication')
    op.drop_index('idx_storage_audit_created_at_desc', 'storage_audit')
    op.drop_index('idx_storage_audit_file_hash_created', 'storage_audit')
    op.drop_index('idx_storage_audit_user_session', 'storage_audit')
    op.drop_index('idx_storage_audit_operation_status', 'storage_audit')

    # Remove constraints
    op.drop_constraint('check_exception_details_not_null', 'exceptions')
    op.drop_constraint('check_exception_reason_code_not_empty', 'exceptions')

    # Remove indexes (handle optional trigram index gracefully)
    try:
        op.drop_index('idx_exception_category_trgm', 'exceptions')
    except Exception:
        # Index might not exist, continue
        pass

    op.drop_index('idx_exception_details_gin', 'exceptions')
    op.drop_index('idx_exception_status', 'exceptions')
    op.drop_index('idx_exception_severity', 'exceptions')
    op.drop_index('idx_exception_category', 'exceptions')
    op.drop_index('idx_exception_resolved_at', 'exceptions')
    op.drop_index('idx_exception_created_at', 'exceptions')
    op.drop_index('idx_exception_resolved_by', 'exceptions')
    op.drop_index('idx_exception_reason_created', 'exceptions')
    op.drop_index('idx_exception_invoice_status', 'exceptions')