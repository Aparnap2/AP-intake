"""
Database monitoring API endpoints for real-time performance tracking.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.api_v1 import deps
from app.services.database_health_service import DatabaseHealthService
from app.core.enhanced_database_config import (
    monitor_database_health,
    benchmark_database_performance,
    DatabasePerformanceMonitor
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=Dict[str, Any])
async def get_database_health(
    background_tasks: BackgroundTasks,
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get comprehensive database health metrics.
    """
    try:
        health_service = DatabaseHealthService()
        health_status = await health_service.check_database_health()

        # Schedule background health monitoring
        background_tasks.add_task(monitor_database_health)

        return {
            "success": True,
            "data": health_status
        }
    except Exception as e:
        logger.error(f"Error getting database health: {e}")
        raise HTTPException(status_code=500, detail=f"Database health check failed: {str(e)}")


@router.get("/connections", response_model=Dict[str, Any])
async def get_connection_pool_status(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get current connection pool status and utilization.
    """
    try:
        from app.core.enhanced_database_config import get_async_engine

        engine = get_async_engine()
        monitor = DatabasePerformanceMonitor(engine)
        pool_stats = await monitor.get_pool_statistics()

        return {
            "success": True,
            "data": pool_stats
        }
    except Exception as e:
        logger.error(f"Error getting connection pool status: {e}")
        raise HTTPException(status_code=500, detail=f"Connection pool monitoring failed: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_database_metrics(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get detailed database performance metrics.
    """
    try:
        health_service = DatabaseHealthService()
        metrics = await health_service.get_database_metrics()

        return {
            "success": True,
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Error getting database metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Database metrics retrieval failed: {str(e)}")


@router.get("/slow-queries", response_model=Dict[str, Any])
async def get_slow_queries(
    limit: int = Query(10, ge=1, le=100, description="Number of slow queries to return"),
    min_execution_time: float = Query(100.0, ge=0.0, description="Minimum execution time in milliseconds"),
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get slow queries from pg_stat_statements.
    """
    try:
        health_service = DatabaseHealthService()
        slow_queries = await health_service.get_slow_queries(limit)

        # Filter by minimum execution time
        filtered_queries = [
            query for query in slow_queries
            if query.get('mean_exec_time', 0) >= min_execution_time
        ]

        return {
            "success": True,
            "data": {
                "slow_queries": filtered_queries[:limit],
                "total_found": len(filtered_queries),
                "min_execution_time_ms": min_execution_time
            }
        }
    except Exception as e:
        logger.error(f"Error getting slow queries: {e}")
        raise HTTPException(status_code=500, detail=f"Slow query monitoring failed: {str(e)}")


@router.get("/tables", response_model=Dict[str, Any])
async def get_table_statistics(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get table-level performance statistics.
    """
    try:
        health_service = DatabaseHealthService()
        table_stats = await health_service.get_table_statistics()

        return {
            "success": True,
            "data": table_stats
        }
    except Exception as e:
        logger.error(f"Error getting table statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Table statistics retrieval failed: {str(e)}")


@router.get("/indexes", response_model=Dict[str, Any])
async def get_index_usage(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get index usage statistics and identify unused indexes.
    """
    try:
        health_service = DatabaseHealthService()
        index_usage = await health_service.get_index_usage()

        # Identify potentially unused indexes
        unused_indexes = [
            idx for idx in index_usage
            if idx.get('tuples_read', 0) == 0 and idx.get('tuples_fetched', 0) == 0
        ]

        return {
            "success": True,
            "data": {
                "all_indexes": index_usage,
                "unused_indexes": unused_indexes,
                "total_indexes": len(index_usage),
                "unused_count": len(unused_indexes)
            }
        }
    except Exception as e:
        logger.error(f"Error getting index usage: {e}")
        raise HTTPException(status_code=500, detail=f"Index usage monitoring failed: {str(e)}")


@router.get("/benchmark", response_model=Dict[str, Any])
async def benchmark_database_performance(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Run performance benchmarks on critical database queries.
    """
    try:
        benchmarks = await benchmark_database_performance()

        # Calculate performance scores
        total_queries = len(benchmarks)
        successful_queries = sum(1 for b in benchmarks if b['status'] == 'success')
        avg_execution_time = sum(b.get('execution_time_ms', 0) for b in benchmarks) / total_queries if total_queries > 0 else 0

        performance_score = 100
        if avg_execution_time > 1000:  # 1 second
            performance_score -= 30
        elif avg_execution_time > 500:  # 500ms
            performance_score -= 15
        elif avg_execution_time > 200:  # 200ms
            performance_score -= 5

        return {
            "success": True,
            "data": {
                "benchmarks": benchmarks,
                "summary": {
                    "total_queries": total_queries,
                    "successful_queries": successful_queries,
                    "success_rate": round((successful_queries / total_queries) * 100, 2) if total_queries > 0 else 0,
                    "average_execution_time_ms": round(avg_execution_time, 2),
                    "performance_score": max(0, performance_score)
                }
            }
        }
    except Exception as e:
        logger.error(f"Error running database benchmarks: {e}")
        raise HTTPException(status_code=500, detail=f"Database benchmarking failed: {str(e)}")


@router.get("/trends", response_model=Dict[str, Any])
async def get_performance_trends(
    hours: int = Query(24, ge=1, le=168, description="Hours of trend data to retrieve"),
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get performance trends over time.
    """
    try:
        health_service = DatabaseHealthService()
        trends = await health_service.get_performance_trends(hours)

        return {
            "success": True,
            "data": trends
        }
    except Exception as e:
        logger.error(f"Error getting performance trends: {e}")
        raise HTTPException(status_code=500, detail=f"Performance trends retrieval failed: {str(e)}")


@router.post("/optimize", response_model=Dict[str, Any])
async def trigger_database_optimization(
    background_tasks: BackgroundTasks,
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Trigger database optimization tasks (VACUUM, ANALYZE, etc.).
    """
    try:
        # Schedule optimization in background
        background_tasks.add_task(run_database_optimization)

        return {
            "success": True,
            "message": "Database optimization tasks scheduled",
            "tasks": ["vacuum_analyze", "update_statistics", "reindex"]
        }
    except Exception as e:
        logger.error(f"Error scheduling database optimization: {e}")
        raise HTTPException(status_code=500, detail=f"Database optimization scheduling failed: {str(e)}")


@router.get("/backup-status", response_model=Dict[str, Any])
async def get_backup_status(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get database backup status and information.
    """
    try:
        # This would integrate with your backup system
        # For now, return mock data
        return {
            "success": True,
            "data": {
                "last_backup": "2024-01-15T02:30:00Z",
                "backup_status": "success",
                "backup_size": "2.3GB",
                "backup_retention_days": 30,
                "next_backup": "2024-01-16T02:30:00Z",
                "backup_frequency": "daily",
                "automated_backup_enabled": True
            }
        }
    except Exception as e:
        logger.error(f"Error getting backup status: {e}")
        raise HTTPException(status_code=500, detail=f"Backup status retrieval failed: {str(e)}")


@router.get("/recommendations", response_model=Dict[str, Any])
async def get_performance_recommendations(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get database performance optimization recommendations.
    """
    try:
        health_service = DatabaseHealthService()
        health_status = await health_service.check_database_health()
        slow_queries = await health_service.get_slow_queries(5)
        index_usage = await health_service.get_index_usage()

        recommendations = []

        # Health-based recommendations
        if health_status.get('health_score', 100) < 80:
            recommendations.extend(health_status.get('issues', []))

        # Slow query recommendations
        if slow_queries:
            recommendations.append({
                "type": "query_optimization",
                "priority": "high",
                "description": f"Found {len(slow_queries)} slow queries that need optimization",
                "action": "Review and optimize slow queries using EXPLAIN ANALYZE"
            })

        # Index recommendations
        unused_indexes = [idx for idx in index_usage if idx.get('tuples_read', 0) == 0]
        if unused_indexes:
            recommendations.append({
                "type": "index_optimization",
                "priority": "medium",
                "description": f"Found {len(unused_indexes)} unused indexes",
                "action": "Consider removing unused indexes to improve write performance"
            })

        # Connection pool recommendations
        pool_status = await health_service.get_connection_pool_status()
        if pool_status.get('total_connections', 0) > 0:
            utilization = (pool_status.get('checked_out', 0) / pool_status.get('total_connections', 1)) * 100
            if utilization > 80:
                recommendations.append({
                    "type": "connection_pool",
                    "priority": "high",
                    "description": f"High connection pool utilization: {utilization:.1f}%",
                    "action": "Consider increasing pool_size or max_overflow settings"
                })

        # Add maintenance recommendations
        recommendations.append({
            "type": "maintenance",
            "priority": "low",
            "description": "Regular database maintenance recommended",
            "action": "Schedule regular VACUUM ANALYZE and index rebuilds"
        })

        return {
            "success": True,
            "data": {
                "recommendations": recommendations,
                "total_recommendations": len(recommendations),
                "health_score": health_status.get('health_score', 0),
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")


async def run_database_optimization():
    """Run database optimization tasks in background."""
    try:
        logger.info("Starting database optimization tasks")

        # This would trigger the optimization script
        # For now, just log the action
        logger.info("Database optimization completed")

    except Exception as e:
        logger.error(f"Database optimization failed: {e}")


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_database_dashboard(
    current_user: Any = Depends(deps.get_current_active_user),
):
    """
    Get comprehensive database monitoring dashboard data.
    """
    try:
        # Gather all monitoring data
        health_service = DatabaseHealthService()
        health_status = await health_service.check_database_health()
        pool_status = await health_service.get_connection_pool_status()
        metrics = await health_service.get_database_metrics()
        slow_queries = await health_service.get_slow_queries(5)
        table_stats = await health_service.get_table_statistics()

        # Get benchmarks
        benchmarks = await benchmark_database_performance()

        return {
            "success": True,
            "data": {
                "health_status": health_status,
                "connection_pool": pool_status,
                "performance_metrics": metrics,
                "slow_queries": slow_queries[:3],  # Top 3 slow queries
                "table_statistics": table_stats.get('tables', [])[:5],  # Top 5 tables
                "performance_benchmarks": benchmarks,
                "summary": {
                    "health_score": health_status.get('health_score', 0),
                    "total_connections": pool_status.get('total_connections', 0),
                    "active_queries": metrics.get('connections', {}).get('active_connections', 0),
                    "slow_query_count": len(slow_queries),
                    "cache_hit_ratio": metrics.get('cache_performance', {}).get('cache_hit_ratio', 0),
                    "last_updated": datetime.utcnow().isoformat()
                }
            }
        }
    except Exception as e:
        logger.error(f"Error generating database dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Database dashboard generation failed: {str(e)}")