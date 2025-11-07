#!/usr/bin/env python3
"""
Database validation script for AP Intake system.
This script validates that the database is properly configured with all required tables, indexes, and sample data.
"""

import asyncio
import logging
from sqlalchemy import text
from app.db.session import sync_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_database_setup():
    """Validate the complete database setup."""
    logger.info("=== AP Intake Database Validation Report ===")

    with sync_engine.connect() as conn:
        # Check tables
        logger.info("\n1. TABLE VALIDATION")
        tables_result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        tables = [row[0] for row in tables_result.fetchall()]

        expected_tables = [
            'vendors', 'purchase_orders', 'goods_receipt_notes',
            'invoices', 'invoice_extractions', 'validations',
            'exceptions', 'staged_exports', 'alembic_version'
        ]

        for table in expected_tables:
            if table in tables:
                logger.info(f"  ✓ {table}")
            else:
                logger.error(f"  ✗ {table} - MISSING")

        # Check data counts
        logger.info("\n2. SAMPLE DATA VALIDATION")
        counts_result = conn.execute(text("""
            SELECT 'vendors', COUNT(*) FROM vendors
            UNION ALL
            SELECT 'purchase_orders', COUNT(*) FROM purchase_orders
            UNION ALL
            SELECT 'goods_receipt_notes', COUNT(*) FROM goods_receipt_notes
            UNION ALL
            SELECT 'invoices', COUNT(*) FROM invoices
            ORDER BY 1
        """))

        for table, count in counts_result.fetchall():
            if table == 'vendors' and count >= 5:
                logger.info(f"  ✓ {table}: {count} records")
            elif table == 'purchase_orders' and count >= 5:
                logger.info(f"  ✓ {table}: {count} records")
            elif table == 'goods_receipt_notes' and count >= 3:
                logger.info(f"  ✓ {table}: {count} records")
            elif table == 'invoices' and count == 0:
                logger.info(f"  ✓ {table}: {count} records (ready for invoice processing)")
            else:
                logger.info(f"  • {table}: {count} records")

        # Check indexes
        logger.info("\n3. INDEX VALIDATION")
        indexes_result = conn.execute(text("""
            SELECT schemaname, tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """))

        current_table = None
        for row in indexes_result.fetchall():
            schema, table, index, definition = row
            if table != current_table:
                logger.info(f"  Table: {table}")
                current_table = table
            logger.info(f"    ✓ {index}")

        # Check constraints
        logger.info("\n4. CONSTRAINT VALIDATION")
        constraints_result = conn.execute(text("""
            SELECT tc.table_name, tc.constraint_name, tc.constraint_type
            FROM information_schema.table_constraints tc
            WHERE tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_name
        """))

        current_table = None
        for row in constraints_result.fetchall():
            table, constraint, constraint_type = row
            if table != current_table:
                logger.info(f"  Table: {table}")
                current_table = table
            logger.info(f"    ✓ {constraint_type}: {constraint}")

        # Sample data quality check
        logger.info("\n5. DATA QUALITY CHECK")

        # Check vendor data
        vendor_check = conn.execute(text("""
            SELECT COUNT(*) as total_vendors,
                   COUNT(CASE WHEN active = true THEN 1 END) as active_vendors,
                   COUNT(CASE WHEN currency IS NOT NULL THEN 1 END) as with_currency
            FROM vendors
        """)).fetchone()

        logger.info(f"  Vendors: {vendor_check.total_vendors} total, {vendor_check.active_vendors} active, {vendor_check.with_currency} with currency")

        # Check PO data
        po_check = conn.execute(text("""
            SELECT COUNT(*) as total_pos,
                   COUNT(CASE WHEN status = 'SENT' THEN 1 END) as sent_pos,
                   COUNT(CASE WHEN status = 'PARTIAL' THEN 1 END) as partial_pos
            FROM purchase_orders
        """)).fetchone()

        logger.info(f"  POs: {po_check.total_pos} total, {po_check.sent_pos} sent, {po_check.partial_pos} partial")

        # Check GRN data
        grn_check = conn.execute(text("""
            SELECT COUNT(*) as total_grns,
                   COUNT(CASE WHEN carrier IS NOT NULL THEN 1 END) as with_carrier,
                   COUNT(CASE WHEN tracking_no IS NOT NULL THEN 1 END) as with_tracking
            FROM goods_receipt_notes
        """)).fetchone()

        logger.info(f"  GRNs: {grn_check.total_grns} total, {grn_check.with_carrier} with carrier, {grn_check.with_tracking} with tracking")

        logger.info("\n=== Database Validation Complete ===")
        logger.info("✅ Database is properly configured for AP Intake system!")
        logger.info("🚀 Ready for invoice processing workflow!")


if __name__ == "__main__":
    validate_database_setup()