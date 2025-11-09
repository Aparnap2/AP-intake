#!/usr/bin/env python3
"""
Database optimization script for PostgreSQL performance improvements.
Run this script to apply performance optimizations to the AP Intake database.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.session import engine, SessionLocal
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Database optimization utilities."""

    def __init__(self):
        self.engine = engine
        self.session_factory = SessionLocal

    def execute_sql(self, sql: str, description: str = None) -> bool:
        """Execute SQL statement safely."""
        try:
            with self.session_factory() as session:
                session.execute(text(sql))
                session.commit()
                if description:
                    logger.info(f"✓ {description}")
                return True
        except Exception as e:
            logger.error(f"✗ Failed to execute {description or 'SQL'}: {e}")
            return False

    def create_performance_indexes(self):
        """Create indexes for performance optimization."""
        logger.info("Creating performance indexes...")

        indexes = [
            # File hash lookup optimization
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoices_file_hash_created "
             "ON invoices(file_hash, created_at);",
             "File hash lookup index"),

            # Workflow state filtering
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoices_workflow_status_created "
             "ON invoices(workflow_state, status, created_at);",
             "Workflow state filtering index"),

            # Exception resolution tracking
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exceptions_resolved_created "
             "ON exceptions(resolved_at DESC, created_at DESC) WHERE resolved_at IS NOT NULL;",
             "Exception resolution tracking index"),

            # Vendor performance analytics
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoices_vendor_created_status "
             "ON invoices(vendor_id, created_at DESC, status);",
             "Vendor performance analytics index"),

            # Extraction confidence analysis
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_extractions_created_confidence "
             "ON invoice_extractions(created_at DESC) WHERE confidence_json IS NOT NULL;",
             "Extraction confidence analysis index"),

            # Validation performance
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_validations_passed_created "
             "ON validations(passed, created_at DESC);",
             "Validation performance index"),

            # Export job optimization
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_staged_exports_status_created "
             "ON staged_exports(status, created_at DESC);",
             "Export job optimization index"),
        ]

        success_count = 0
        for sql, description in indexes:
            if self.execute_sql(sql, description):
                success_count += 1

        logger.info(f"Created {success_count}/{len(indexes)} performance indexes")

    def enable_performance_extensions(self):
        """Enable PostgreSQL performance extensions."""
        logger.info("Enabling performance extensions...")

        extensions = [
            ("CREATE EXTENSION IF NOT EXISTS pg_stat_statements;", "pg_stat_statements for query monitoring"),
            ("CREATE EXTENSION IF NOT EXISTS pg_trgm;", "pg_trgm for text similarity search"),
            ("CREATE EXTENSION IF NOT EXISTS btree_gin;", "btree_gin for composite indexes"),
            ("CREATE EXTENSION IF NOT EXISTS btree_gist;", "btree_gist for advanced indexing"),
        ]

        success_count = 0
        for sql, description in extensions:
            if self.execute_sql(sql, description):
                success_count += 1

        logger.info(f"Enabled {success_count}/{len(extensions)} performance extensions")

    def update_table_statistics(self):
        """Update table statistics for better query planning."""
        logger.info("Updating table statistics...")

        tables = [
            "invoices",
            "invoice_extractions",
            "validations",
            "exceptions",
            "staged_exports",
            "vendors",
            "purchase_orders",
            "goods_receipt_notes"
        ]

        success_count = 0
        for table in tables:
            sql = f"ANALYZE {table};"
            if self.execute_sql(sql, f"Analyzed {table}"):
                success_count += 1

        logger.info(f"Updated statistics for {success_count}/{len(tables)} tables")

    def optimize_table_maintenance(self):
        """Configure table maintenance settings."""
        logger.info("Optimizing table maintenance settings...")

        maintenance_settings = [
            # Autovacuum tuning for invoice tables (high write activity)
            ("ALTER TABLE invoices SET (autovacuum_vacuum_scale_factor = 0.1, "
             "autovacuum_analyze_scale_factor = 0.05);",
             "Optimized autovacuum for invoices"),

            ("ALTER TABLE invoice_extractions SET (autovacuum_vacuum_scale_factor = 0.1, "
             "autovacuum_analyze_scale_factor = 0.05);",
             "Optimized autovacuum for invoice_extractions"),

            ("ALTER TABLE validations SET (autovacuum_vacuum_scale_factor = 0.1, "
             "autovacuum_analyze_scale_factor = 0.05);",
             "Optimized autovacuum for validations"),

            # Fillfactor settings for tables with frequent updates
            ("ALTER TABLE invoices SET (fillfactor = 90);", "Set fillfactor for invoices"),
            ("ALTER TABLE exceptions SET (fillfactor = 90);", "Set fillfactor for exceptions"),
        ]

        success_count = 0
        for sql, description in maintenance_settings:
            if self.execute_sql(sql, description):
                success_count += 1

        logger.info(f"Applied {success_count}/{len(maintenance_settings)} maintenance settings")

    def create_performance_views(self):
        """Create performance monitoring views."""
        logger.info("Creating performance monitoring views...")

        views = [
            # Slow queries view
            ("""CREATE OR REPLACE VIEW slow_queries AS
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    rows,
                    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                FROM pg_stat_statements
                WHERE mean_exec_time > 100
                ORDER BY mean_exec_time DESC;""",
             "Slow queries monitoring view"),

            # Table sizes view
            ("""CREATE OR REPLACE VIEW table_sizes AS
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) -
                                   pg_relation_size(schemaname||'.'||tablename)) as index_size
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;""",
             "Table sizes monitoring view"),

            # Unused indexes view
            ("""CREATE OR REPLACE VIEW unused_indexes AS
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read,
                    idx_tup_fetch,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes
                WHERE idx_tup_read = 0
                ORDER BY schemaname, tablename, indexname;""",
             "Unused indexes monitoring view"),
        ]

        success_count = 0
        for sql, description in views:
            if self.execute_sql(sql, description):
                success_count += 1

        logger.info(f"Created {success_count}/{len(views)} performance views")

    def configure_query_monitoring(self):
        """Configure query performance monitoring."""
        logger.info("Configuring query monitoring...")

        monitoring_config = [
            # Reset statistics for clean monitoring
            ("SELECT pg_stat_statements_reset();", "Reset query statistics"),

            # Configure logging for slow queries
            ("ALTER SYSTEM SET log_min_duration_statement = 1000;", "Log queries > 1 second"),
            ("ALTER SYSTEM SET log_checkpoints = on;", "Enable checkpoint logging"),
            ("ALTER SYSTEM SET log_connections = on;", "Enable connection logging"),
            ("ALTER SYSTEM SET log_disconnections = on;", "Enable disconnection logging"),
            ("ALTER SYSTEM SET log_lock_waits = on;", "Enable lock wait logging"),

            # Reload configuration
            ("SELECT pg_reload_conf();", "Reload PostgreSQL configuration"),
        ]

        success_count = 0
        for sql, description in monitoring_config:
            if self.execute_sql(sql, description):
                success_count += 1

        logger.info(f"Applied {success_count}/{len(monitoring_config)} monitoring settings")

    def run_vacuum_analyze(self):
        """Run VACUUM ANALYZE on critical tables."""
        logger.info("Running VACUUM ANALYZE on critical tables...")

        critical_tables = [
            "invoices",
            "invoice_extractions",
            "validations",
            "exceptions"
        ]

        success_count = 0
        for table in critical_tables:
            sql = f"VACUUM ANALYZE {table};"
            if self.execute_sql(sql, f"Vacuumed and analyzed {table}"):
                success_count += 1

        logger.info(f"Vacuumed and analyzed {success_count}/{len(critical_tables)} tables")

    def check_optimization_results(self):
        """Check the results of optimization."""
        logger.info("Checking optimization results...")

        try:
            with self.session_factory() as session:
                # Check index creation
                result = session.execute(text("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                    FROM pg_indexes
                    JOIN pg_stat_user_indexes USING (schemaname, tablename, indexname)
                    WHERE schemaname = 'public'
                    ORDER BY indexname;
                """))

                indexes = result.fetchall()
                logger.info(f"Total indexes: {len(indexes)}")

                # Check table statistics
                result = session.execute(text("""
                    SELECT
                        tablename,
                        n_live_tup as live_tuples,
                        n_dead_tup as dead_tuples,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_stat_user_tables
                    ORDER BY live_tuples DESC;
                """))

                table_stats = result.fetchall()
                logger.info(f"Table statistics updated for {len(table_stats)} tables")

                # Check extension status
                result = session.execute(text("""
                    SELECT extname, extversion
                    FROM pg_extension
                    WHERE extname IN ('pg_stat_statements', 'pg_trgm', 'btree_gin', 'btree_gist');
                """))

                extensions = result.fetchall()
                logger.info(f"Enabled extensions: {[ext[0] for ext in extensions]}")

                return True

        except Exception as e:
            logger.error(f"Error checking optimization results: {e}")
            return False

    def run_full_optimization(self):
        """Run complete database optimization."""
        logger.info("Starting full database optimization...")

        steps = [
            ("enable_performance_extensions", "Enabling performance extensions"),
            ("create_performance_indexes", "Creating performance indexes"),
            ("optimize_table_maintenance", "Optimizing table maintenance"),
            ("update_table_statistics", "Updating table statistics"),
            ("create_performance_views", "Creating performance views"),
            ("configure_query_monitoring", "Configuring query monitoring"),
            ("run_vacuum_analyze", "Running VACUUM ANALYZE"),
            ("check_optimization_results", "Checking optimization results"),
        ]

        success_count = 0
        for step_method, step_name in steps:
            logger.info(f"\n{'='*60}")
            logger.info(f"Step: {step_name}")
            logger.info('='*60)

            try:
                method = getattr(self, step_method)
                if method():
                    success_count += 1
                    logger.info(f"✓ Completed: {step_name}")
                else:
                    logger.error(f"✗ Failed: {step_name}")
            except Exception as e:
                logger.error(f"✗ Error in {step_name}: {e}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Optimization Summary: {success_count}/{len(steps)} steps completed")
        logger.info('='*60)

        return success_count == len(steps)


def main():
    """Main optimization function."""
    logger.info("AP Intake Database Optimization Script")
    logger.info("=" * 50)

    optimizer = DatabaseOptimizer()

    try:
        # Check database connection
        with optimizer.session_factory() as session:
            result = session.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"Connected to PostgreSQL: {version.split(',')[0]}")

        # Run optimization
        success = optimizer.run_full_optimization()

        if success:
            logger.info("\n🎉 Database optimization completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Monitor query performance using the slow_queries view")
            logger.info("2. Check index usage with the unused_indexes view")
            logger.info("3. Monitor table sizes with the table_sizes view")
            logger.info("4. Set up regular maintenance scripts")
        else:
            logger.error("\n❌ Database optimization completed with errors")
            logger.error("Please review the logs above and fix any issues")

    except Exception as e:
        logger.error(f"Fatal error during optimization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()