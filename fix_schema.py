#!/usr/bin/env python3
"""
Script to fix database schema issues directly.
"""

import asyncio
import logging
from sqlalchemy import text
from app.db.session import get_async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_schema():
    """Apply schema fixes directly."""
    engine = get_async_engine()

    # SQL commands to fix the schema
    sql_commands = [
        # Add missing audit_metadata column
        "ALTER TABLE storage_audit ADD COLUMN IF NOT EXISTS audit_metadata TEXT;",

        # Drop foreign key constraints
        "ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_id_fkey;",
        "ALTER TABLE vendors DROP CONSTRAINT IF EXISTS vendors_id_fkey;",
        "ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS purchase_orders_id_fkey;",
        "ALTER TABLE goods_receipt_notes DROP CONSTRAINT IF EXISTS goods_receipt_notes_id_fkey;",
        "ALTER TABLE invoice_extractions DROP CONSTRAINT IF EXISTS invoice_extractions_id_fkey;",
        "ALTER TABLE validations DROP CONSTRAINT IF EXISTS validations_id_fkey;",
        "ALTER TABLE exceptions DROP CONSTRAINT IF EXISTS exceptions_id_fkey;",
        "ALTER TABLE staged_exports DROP CONSTRAINT IF EXISTS staged_exports_id_fkey;",

        # Drop base_uuid_mixin table
        "DROP TABLE IF EXISTS base_uuid_mixin CASCADE;",
    ]

    async with engine.begin() as conn:
        for i, sql in enumerate(sql_commands):
            try:
                logger.info(f"Executing command {i+1}/{len(sql_commands)}: {sql[:50]}...")
                await conn.execute(text(sql))
                logger.info(f"Successfully executed command {i+1}")
            except Exception as e:
                logger.error(f"Error executing command {i+1}: {e}")

    logger.info("Schema fixes completed!")


if __name__ == "__main__":
    asyncio.run(fix_schema())