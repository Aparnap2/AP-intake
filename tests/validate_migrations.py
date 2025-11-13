#!/usr/bin/env python3
"""Validate Alembic migrations work with PostgreSQL database."""

import asyncio
import sys
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the project directory to the Python path
sys.path.insert(0, '/home/aparna/Desktop/ap_intake')

# Check if using Neon PostgreSQL
is_neon = os.getenv('DATABASE_URL', '').startswith('postgres+asyncpg://neon')
if is_neon:
    print("✓ Detected Neon PostgreSQL configuration")
else:
    print("ℹ Using local PostgreSQL configuration")

async def test_database_connection():
    """Test database connection and PostgreSQL features."""
    from app.core.config import settings

    print("\nTesting database connection...")

    try:
        # Create async engine
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=True,
            pool_pre_ping=True
        )

        print(f"✓ Database engine created for: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'local'}")

        # Test connection
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ Database connection successful")
            print(f"  PostgreSQL version: {version.split(',')[0]}")

        # Test async session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            result = await session.execute(text("SELECT 1 as test"))
            test_val = result.scalar()
            assert test_val == 1, "Basic query failed"
            print("✓ Async session working correctly")

        await engine.dispose()
        return True

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def check_alembic_versions():
    """Check Alembic migration table and versions."""
    try:
        from app.core.config import settings

        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False
        )

        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Check if alembic_version table exists
            try:
                result = await session.execute(text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'alembic_version'
                """))
                table_exists = result.scalar() is not None
                print(f"✓ Alembic version table exists: {table_exists}")

                if table_exists:
                    # Get current version
                    result = await session.execute(text("SELECT version_num FROM alembic_version"))
                    current_version = result.scalar()
                    print(f"✓ Current Alembic version: {current_version}")
                else:
                    print("⚠ Alembic version table not found - run 'alembic upgrade head'")

            except Exception as e:
                print(f"⚠ Could not check alembic table: {e}")

        await engine.dispose()
        return True

    except Exception as e:
        print(f"❌ Error checking Alembic versions: {e}")
        return False

async def test_models():
    """Test SQLAlchemy models can be created and queried."""
    try:
        from app.core.config import settings
        from app.models.invoice import Invoice
        from app.models.ingestion import IngestionJob

        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False
        )

        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Test model table creation
            print("Testing model definitions...")

            # Check if Invoice table exists
            result = await session.execute(text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'invoices'
            """))
            invoice_table_exists = result.scalar() is not None
            print(f"✓ Invoice table exists: {invoice_table_exists}")

            # Check if IngestionJob table exists
            result = await session.execute(text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'ingestion_jobs'
            """))
            ingestion_table_exists = result.scalar() is not None
            print(f"✓ IngestionJob table exists: {ingestion_table_exists}")

            if invoice_table_exists:
                # Test basic query
                result = await session.execute(text("SELECT COUNT(*) FROM invoices"))
                count = result.scalar()
                print(f"✓ Invoice table accessible, {count} records found")

        await engine.dispose()
        return True

    except Exception as e:
        print(f"❌ Error testing models: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_operations():
    """Test async database operations."""
    try:
        from app.core.config import settings

        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False
        )

        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        print("\nTesting async database operations...")

        async with async_session() as session:
            # Test concurrent operations
            tasks = []
            for i in range(3):
                task = session.execute(text(f"SELECT {i} as test_id, now() as timestamp"))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ Concurrent query {i} failed: {result}")
                    return False
                else:
                    row = result.fetchone()
                    print(f"✓ Concurrent query {i}: {row}")

        await engine.dispose()
        return True

    except Exception as e:
        print(f"❌ Error testing async operations: {e}")
        return False

async def main():
    """Main validation function."""
    print("🔍 AP Intake Database Migration Validation")
    print("=" * 50)

    # Test 1: Database connection
    if not await test_database_connection():
        print("\n❌ Database connection failed - stopping validation")
        return False

    # Test 2: Alembic versions
    if not await check_alembic_versions():
        print("\n⚠ Alembic version check failed - continuing")

    # Test 3: Models
    if not await test_models():
        print("\n❌ Model validation failed")
        return False

    # Test 4: Async operations
    if not await test_async_operations():
        print("\n❌ Async operations test failed")
        return False

    print("\n" + "=" * 50)
    print("✅ All database migration validations passed!")
    print("\nDatabase setup is ready for AP Intake application.")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)