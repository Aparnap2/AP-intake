"""
Performance monitoring and load testing API endpoints.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from app.api.api_v1.deps import get_current_user
from app.services.load_test_service import (
    load_test_service,
    LoadTestType,
    LoadTestConfig
)
from app.services.performance_profiling_service import (
    performance_profiling_service
)
from app.services.database_performance_service import (
    database_performance_service
)
from app.services.prometheus_service import prometheus_service
from app.services.metrics_service import metrics_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview", summary="Get Performance Overview")
async def get_performance_overview(
    time_range_hours: int = Query(default=24, ge=1, le=168),
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive performance overview."""
    try:
        # Get performance trends
        performance_trends = await performance_profiling_service.analyze_performance_trends(time_range_hours)

        # Get database health
        db_health = await database_performance_service.generate_database_health_report()

        # Get load test history
        load_test_history = await load_test_service.get_test_history(limit=10)

        # Get SLO metrics
        slo_dashboard = await metrics_service.get_slo_dashboard_data(time_range_hours)

        overview = {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "performance_trends": performance_trends,
            "database_health": db_health,
            "recent_load_tests": [
                {
                    "test_id": test.test_id,
                    "test_type": test.test_type.value,
                    "status": test.status.value,
                    "duration_seconds": test.calculate_duration(),
                    "requests_per_second": test.requests_per_second,
                    "performance_passed": test.performance_passed
                }
                for test in load_test_history
            ],
            "slo_status": slo_dashboard.get("summary", {}),
            "system_health": {
                "status": "healthy" if db_health.get("health_score", 0) >= 80 else "warning",
                "score": db_health.get("health_score", 0),
                "alerts": db_health.get("alerts", [])
            }
        }

        return overview

    except Exception as e:
        logger.error(f"Failed to get performance overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load-test/start", summary="Start Load Test")
async def start_load_test(
    test_type: LoadTestType,
    background_tasks: BackgroundTasks,
    custom_config: Optional[Dict[str, Any]] = None,
    current_user: dict = Depends(get_current_user)
):
    """Start a load test with specified type."""
    try:
        # Create custom config if provided
        config = None
        if custom_config:
            config = LoadTestConfig(
                test_type=test_type,
                **custom_config
            )

        # Start load test in background
        test_id = await load_test_service.run_load_test(test_type, config)

        return {
            "message": "Load test started",
            "test_id": test_id,
            "test_type": test_type.value,
            "status": "running"
        }

    except Exception as e:
        logger.error(f"Failed to start load test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/load-test/{test_id}", summary="Get Load Test Results")
async def get_load_test_results(
    test_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get results for a specific load test."""
    try:
        test_result = await load_test_service.get_test_results(test_id)
        if not test_result:
            raise HTTPException(status_code=404, detail="Load test not found")

        return {
            "test_id": test_result.test_id,
            "test_type": test_result.test_type.value,
            "status": test_result.status.value,
            "start_time": test_result.start_time.isoformat(),
            "end_time": test_result.end_time.isoformat() if test_result.end_time else None,
            "duration_seconds": test_result.calculate_duration(),
            "total_requests": test_result.total_requests,
            "successful_requests": test_result.successful_requests,
            "failed_requests": test_result.failed_requests,
            "failure_rate": test_result.failure_rate,
            "requests_per_second": test_result.requests_per_second,
            "avg_response_time": test_result.avg_response_time,
            "p95_response_time": test_result.p95_response_time,
            "p99_response_time": test_result.p99_response_time,
            "concurrent_users": test_result.concurrent_users,
            "cpu_usage_avg": test_result.cpu_usage_avg,
            "memory_usage_avg": test_result.memory_usage_avg,
            "performance_passed": test_result.performance_passed,
            "validation_errors": test_result.validation_errors,
            "endpoint_stats": test_result.endpoint_stats,
            "error_summary": test_result.error_summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get load test results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/load-test/{test_id}/report", summary="Get Load Test Report")
async def get_load_test_report(
    test_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive load test report."""
    try:
        report = await load_test_service.generate_performance_report(test_id)
        return report

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate load test report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/load-test/active", summary="Get Active Load Tests")
async def get_active_load_tests(current_user: dict = Depends(get_current_user)):
    """Get list of currently active load tests."""
    try:
        active_tests = await load_test_service.get_active_tests()
        return [
            {
                "test_id": test.test_id,
                "test_type": test.test_type.value,
                "start_time": test.start_time.isoformat(),
                "duration_seconds": test.calculate_duration(),
                "concurrent_users": test.concurrent_users
            }
            for test in active_tests
        ]

    except Exception as e:
        logger.error(f"Failed to get active load tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load-test/{test_id}/cancel", summary="Cancel Load Test")
async def cancel_load_test(
    test_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a running load test."""
    try:
        success = await load_test_service.cancel_test(test_id)
        if not success:
            raise HTTPException(status_code=404, detail="Test not found or not running")

        return {"message": "Load test cancelled", "test_id": test_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel load test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiling/summary", summary="Get Profiling Summary")
async def get_profiling_summary(
    session_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get profiling summary."""
    try:
        summary = await performance_profiling_service.get_profile_summary(session_id)
        return summary

    except Exception as e:
        logger.error(f"Failed to get profiling summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiling/trends", summary="Get Performance Trends")
async def get_performance_trends(
    hours: int = Query(default=24, ge=1, le=168),
    current_user: dict = Depends(get_current_user)
):
    """Get performance trends analysis."""
    try:
        trends = await performance_profiling_service.analyze_performance_trends(hours)
        return trends

    except Exception as e:
        logger.error(f"Failed to get performance trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/health", summary="Get Database Health")
async def get_database_health(current_user: dict = Depends(get_current_user)):
    """Get comprehensive database health report."""
    try:
        health_report = await database_performance_service.generate_database_health_report()
        return health_report

    except Exception as e:
        logger.error(f"Failed to get database health report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/slow-queries", summary="Get Slow Queries")
async def get_slow_queries(
    limit: int = Query(default=50, ge=1, le=500),
    time_window_hours: int = Query(default=24, ge=1, le=168),
    current_user: dict = Depends(get_current_user)
):
    """Get recent slow queries."""
    try:
        slow_queries = await database_performance_service.get_slow_queries(limit, time_window_hours)
        return {
            "time_window_hours": time_window_hours,
            "limit": limit,
            "slow_queries": slow_queries
        }

    except Exception as e:
        logger.error(f"Failed to get slow queries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/query-performance", summary="Get Query Performance")
async def get_query_performance(
    time_window_hours: int = Query(default=1, ge=1, le=24),
    current_user: dict = Depends(get_current_user)
):
    """Get query performance summary."""
    try:
        performance = await database_performance_service.get_query_performance_summary(time_window_hours)
        return performance

    except Exception as e:
        logger.error(f"Failed to get query performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/query-patterns", summary="Get Query Patterns Analysis")
async def get_query_patterns_analysis(current_user: dict = Depends(get_current_user)):
    """Get query patterns analysis and optimization opportunities."""
    try:
        analysis = await database_performance_service.analyze_query_patterns()
        return analysis

    except Exception as e:
        logger.error(f"Failed to get query patterns analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/prometheus", summary="Get Prometheus Metrics")
async def get_prometheus_metrics(current_user: dict = Depends(get_current_user)):
    """Get current Prometheus metrics."""
    try:
        response = prometheus_service.get_metrics_response()
        return response

    except Exception as e:
        logger.error(f"Failed to get Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/system", summary="Get System Metrics")
async def get_system_metrics(
    time_range_hours: int = Query(default=1, ge=1, le=24),
    current_user: dict = Depends(get_current_user)
):
    """Get system performance metrics."""
    try:
        # Collect current database metrics
        db_metrics = await database_performance_service.collect_database_metrics()

        # Get KPI summary
        kpi_summary = await metrics_service.get_kpi_summary(time_range_hours)

        # Combine system metrics
        system_metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "database": {
                "active_connections": db_metrics.active_connections,
                "idle_connections": db_metrics.idle_connections,
                "total_connections": db_metrics.total_connections,
                "queries_per_second": db_metrics.queries_per_second,
                "avg_query_time_ms": db_metrics.avg_query_time_ms,
                "slow_queries_per_second": db_metrics.slow_queries_per_second,
                "cache_hit_ratio": db_metrics.cache_hit_ratio,
                "database_size_mb": db_metrics.database_size_mb
            },
            "kpi_summary": kpi_summary
        }

        return system_metrics

    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimization/recommendations", summary="Get Optimization Recommendations")
async def get_optimization_recommendations(
    current_user: dict = Depends(get_current_user)
):
    """Get performance optimization recommendations."""
    try:
        # Get recent profiling data
        performance_trends = await performance_profiling_service.analyze_performance_trends(24)

        # Extract recommendations from trends
        recommendations = performance_trends.get("recommendations", [])

        # Add database recommendations
        try:
            db_health = await database_performance_service.generate_database_health_report()
            db_recommendations = db_health.get("recommendations", [])
            recommendations.extend(db_recommendations)
        except Exception as e:
            logger.warning(f"Failed to get database recommendations: {e}")

        # Categorize and prioritize recommendations
        categorized = {
            "high_priority": [],
            "medium_priority": [],
            "low_priority": []
        }

        for rec in recommendations:
            if isinstance(rec, str):
                # Convert string recommendations to dict format
                rec = {
                    "category": "general",
                    "priority": "medium",
                    "title": rec,
                    "description": rec,
                    "estimated_improvement": "TBD",
                    "implementation_effort": "TBD"
                }

            priority = rec.get("priority", "medium")
            if priority in ["high", "critical"]:
                categorized["high_priority"].append(rec)
            elif priority in ["medium", "warning"]:
                categorized["medium_priority"].append(rec)
            else:
                categorized["low_priority"].append(rec)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_recommendations": len(recommendations),
            "categories": categorized
        }

    except Exception as e:
        logger.error(f"Failed to get optimization recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", summary="Get Performance Alerts")
async def get_performance_alerts(
    severity: Optional[str] = Query(default=None, regex="^(critical|warning|info)$"),
    hours: int = Query(default=24, ge=1, le=168),
    current_user: dict = Depends(get_current_user)
):
    """Get performance alerts."""
    try:
        alerts = []

        # Get database health alerts
        db_health = await database_performance_service.generate_database_health_report()
        db_alerts = db_health.get("alerts", [])

        # Filter by severity if specified
        if severity:
            db_alerts = [alert for alert in db_alerts if alert.get("severity") == severity]

        alerts.extend(db_alerts)

        # Get SLO alerts
        try:
            slo_dashboard = await metrics_service.get_slo_dashboard_data(hours)
            slo_alerts = slo_dashboard.get("alerts", [])
            alerts.extend(slo_alerts)
        except Exception as e:
            logger.warning(f"Failed to get SLO alerts: {e}")

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "time_range_hours": hours,
            "severity_filter": severity,
            "total_alerts": len(alerts),
            "alerts": alerts
        }

    except Exception as e:
        logger.error(f"Failed to get performance alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintenance/cleanup", summary="Performance Maintenance Cleanup")
async def perform_maintenance_cleanup(
    data: Dict[str, Any] = None,
    current_user: dict = Depends(get_current_user)
):
    """Perform maintenance cleanup of performance data."""
    try:
        cleanup_config = data or {
            "profiling_history_hours": 24,
            "query_metrics_hours": 24,
            "load_test_days": 7
        }

        # Clean up profiling history
        if "profiling_history_hours" in cleanup_config:
            performance_profiling_service.clear_profile_history(
                cleanup_config["profiling_history_hours"]
            )

        # Clean up database performance metrics
        if "query_metrics_hours" in cleanup_config:
            database_performance_service.clear_metrics_history(
                cleanup_config["query_metrics_hours"]
            )

        return {
            "message": "Performance maintenance cleanup completed",
            "cleanup_config": cleanup_config,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to perform maintenance cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", summary="Get Performance Dashboard Data")
async def get_performance_dashboard(
    time_range_hours: int = Query(default=24, ge=1, le=168),
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive performance dashboard data."""
    try:
        # Get performance overview
        overview = await get_performance_overview(time_range_hours, current_user)

        # Get optimization recommendations
        recommendations = await get_optimization_recommendations(current_user)

        # Get active alerts
        alerts_data = await get_performance_alerts(hours=time_range_hours, current_user=current_user)

        # Combine into dashboard format
        dashboard = {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "overview": overview,
            "recommendations": recommendations,
            "alerts": alerts_data,
            "quick_stats": {
                "system_health_score": overview.get("system_health", {}).get("score", 0),
                "active_load_tests": len(overview.get("recent_load_tests", [])),
                "critical_alerts": len([a for a in alerts_data.get("alerts", []) if a.get("severity") == "critical"]),
                "optimization_opportunities": recommendations.get("total_recommendations", 0)
            }
        }

        return dashboard

    except Exception as e:
        logger.error(f"Failed to get performance dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))