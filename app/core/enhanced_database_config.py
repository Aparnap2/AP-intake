"""
Enhanced database configuration for production performance optimization.
"""

import os
from typing import Dict, Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings


class DatabaseConfigManager:
    """Manages enhanced database configuration for production environments."""

    # Environment-specific configurations
    ENVIRONMENT_CONFIGS = {
        'development': {
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
            'echo': True,
        },
        'staging': {
            'pool_size': 15,
            'max_overflow': 25,
            'pool_timeout': 20,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
            'echo': False,
        },
        'production': {
            'pool_size': 25,
            'max_overflow': 50,
            'pool_timeout': 15,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
            'echo': False,
        }
    }

    @classmethod
    def get_config(cls, environment: str = None) -> Dict[str, Any]:
        """Get database configuration for the current environment."""
        env = environment or settings.ENVIRONMENT.lower()
        config = cls.ENVIRONMENT_CONFIGS.get(env, cls.ENVIRONMENT_CONFIGS['development'])

        # Override with any explicit settings
        return {
            'pool_size': getattr(settings, 'DATABASE_POOL_SIZE', config['pool_size']),
            'max_overflow': getattr(settings, 'DATABASE_MAX_OVERFLOW', config['max_overflow']),
            'pool_timeout': getattr(settings, 'DATABASE_POOL_TIMEOUT', config['pool_timeout']),
            'pool_recycle': getattr(settings, 'DATABASE_POOL_RECYCLE', config['pool_recycle']),
            'pool_pre_ping': getattr(settings, 'DATABASE_POOL_PRE_PING', config['pool_pre_ping']),
            'echo': settings.DEBUG if hasattr(settings, 'DEBUG') else config['echo'],
        }

    @classmethod
    def create_optimized_async_engine(cls, database_url: str = None):
        """Create optimized async database engine."""
        db_url = database_url or settings.DATABASE_URL
        config = cls.get_config()

        # Enhanced connection arguments for asyncpg
        connect_args = {
            "command_timeout": 60,
            "server_settings": {
                "application_name": "ap_intake_api",
                "jit": "off",  # Disable JIT for OLTP workloads
                "timezone": "UTC",
            }
        }

        # Add SSL configuration if in production
        if settings.ENVIRONMENT.lower() == 'production':
            connect_args["ssl"] = True
            connect_args["sslcert"] = os.getenv("PG_SSLCERT")
            connect_args["sslkey"] = os.getenv("PG_SSLKEY")
            connect_args["sslrootcert"] = os.getenv("PG_SSLROOTCERT")

        engine = create_async_engine(
            db_url,
            **config,
            connect_args=connect_args
        )

        # Set up connection pool monitoring
        cls._setup_pool_monitoring(engine)

        return engine

    @staticmethod
    def _setup_pool_monitoring(engine):
        """Set up connection pool monitoring and logging."""
        import logging

        logger = logging.getLogger(__name__)

        @event.listens_for(engine.sync_engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            logger.debug(f"New database connection established: {dbapi_connection.info}")

        @event.listens_for(engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            pool_status = connection_record.connection.pool
            logger.debug(f"Connection checked out. Pool size: {pool_status.size()}, "
                        f"Checked out: {pool_status.checkedout()}")

        @event.listens_for(engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            logger.debug("Connection returned to pool")

        @event.listens_for(engine.sync_engine, "invalidate")
        def receive_invalidate(dbapi_connection, connection_record, exception):
            logger.warning(f"Database connection invalidated: {exception}")

    @classmethod
    def create_optimized_session_factory(cls, engine):
        """Create optimized async session factory."""
        return async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )


class DatabasePerformanceMonitor:
    """Monitor and optimize database performance."""

    def __init__(self, engine):
        self.engine = engine

    async def get_pool_statistics(self) -> Dict[str, Any]:
        """Get current connection pool statistics."""
        pool = self.engine.pool

        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
            "total_connections": pool.size() + pool.overflow(),
            "utilization_percent": (pool.checkedout() / (pool.size() + pool.overflow())) * 100
        }

    async def get_connection_health(self) -> Dict[str, Any]:
        """Test database connection health."""
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(
                    "SELECT version(), now(), current_database()"
                )
                row = result.fetchone()

                return {
                    "status": "healthy",
                    "database_version": row[0].split(',')[0],
                    "server_time": row[1].isoformat(),
                    "database_name": row[2],
                    "timestamp": row[1].isoformat()
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": None
            }

    async def benchmark_query(self, query: str, params: Dict = None) -> Dict[str, Any]:
        """Benchmark query performance."""
        import time

        start_time = time.time()

        try:
            async with self.engine.begin() as conn:
                if params:
                    result = await conn.execute(query, params)
                else:
                    result = await conn.execute(query)

                rows = result.fetchall()
                execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

                return {
                    "status": "success",
                    "execution_time_ms": round(execution_time, 2),
                    "rows_returned": len(rows),
                    "query": query,
                    "timestamp": time.time()
                }
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return {
                "status": "error",
                "execution_time_ms": round(execution_time, 2),
                "error": str(e),
                "query": query,
                "timestamp": time.time()
            }


# Global instances for easy access
_async_engine = None
_async_session_factory = None


def get_async_engine():
    """Get or create optimized async engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = DatabaseConfigManager.create_optimized_async_engine()
    return _async_engine


def get_async_session_factory():
    """Get or create optimized async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = DatabaseConfigManager.create_optimized_session_factory(engine)
    return _async_session_factory


async def get_async_db():
    """Dependency to get optimized async database session."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Database performance monitoring utilities
async def monitor_database_health():
    """Monitor database health and return metrics."""
    engine = get_async_engine()
    monitor = DatabasePerformanceMonitor(engine)

    pool_stats = await monitor.get_pool_statistics()
    conn_health = await monitor.get_connection_health()

    return {
        "pool_statistics": pool_stats,
        "connection_health": conn_health,
        "timestamp": conn_health.get("timestamp")
    }


async def benchmark_database_performance():
    """Run performance benchmarks on critical queries."""
    engine = get_async_engine()
    monitor = DatabasePerformanceMonitor(engine)

    # Benchmark critical queries
    benchmarks = [
        ("SELECT COUNT(*) FROM invoices", {}, "Invoice count query"),
        ("SELECT COUNT(*) FROM invoices WHERE status = 'received'", {}, "Active invoices query"),
        ("SELECT COUNT(*) FROM exceptions WHERE resolved_at IS NULL", {}, "Pending exceptions query"),
    ]

    results = []
    for query, params, description in benchmarks:
        result = await monitor.benchmark_query(query, params)
        result["description"] = description
        results.append(result)

    return results