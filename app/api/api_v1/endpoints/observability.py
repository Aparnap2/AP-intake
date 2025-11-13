"""
Observability API endpoints for metrics, alerts, and runbook management.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func

from app.api.api_v1.deps import get_async_session, get_current_user
from app.models.observability import (
    Alert, RunbookExecution, RunbookStepExecution, SystemHealthCheck,
    PerformanceMetric, AnomalyDetection, AlertSuppression
)
from app.models.user import User
from app.services.tracing_service import tracing_service
from app.services.runbook_service import runbook_service
from app.services.alert_service import alert_service, AlertSeverity, AlertStatus
from app.services.metrics_service import metrics_service
from app.services.prometheus_service import prometheus_service
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/metrics/summary")
async def get_metrics_summary(
    time_range_hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get comprehensive metrics summary."""
    try:
        async with tracing_service.trace_span(
            "observability.get_metrics_summary",
            tracing_service.SpanMetadata(
                component="observability",
                operation="get_metrics_summary",
                user_id=str(current_user.id),
                additional_attributes={"time_range_hours": time_range_hours}
            )
        ):
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=time_range_hours)

            # Get KPI summary from metrics service
            kpi_summary = await metrics_service.get_kpi_summary(days=time_range_hours // 24)

            # Get system health checks
            health_query = select(SystemHealthCheck).where(
                SystemHealthCheck.checked_at >= start_time
            ).order_by(desc(SystemHealthCheck.checked_at)).limit(100)

            health_result = await session.execute(health_query)
            health_checks = health_result.scalars().all()

            # Get recent performance metrics
            perf_query = select(PerformanceMetric).where(
                PerformanceMetric.measurement_timestamp >= start_time
            ).order_by(desc(PerformanceMetric.measurement_timestamp)).limit(500)

            perf_result = await session.execute(perf_query)
            performance_metrics = perf_result.scalars().all()

            # Get anomalies
            anomaly_query = select(AnomalyDetection).where(
                AnomalyDetection.detected_at >= start_time
            ).order_by(desc(AnomalyDetection.detected_at)).limit(50)

            anomaly_result = await session.execute(anomaly_query)
            anomalies = anomaly_result.scalars().all()

            # Process health check summary
            health_summary = {
                "total_checks": len(health_checks),
                "healthy": len([h for h in health_checks if h.status == "healthy"]),
                "degraded": len([h for h in health_checks if h.status == "degraded"]),
                "unhealthy": len([h for h in health_checks if h.status == "unhealthy"]),
                "average_response_time_ms": sum(h.response_time_ms or 0 for h in health_checks) // max(len(health_checks), 1),
                "component_breakdown": {}
            }

            for check in health_checks:
                component = check.component
                if component not in health_summary["component_breakdown"]:
                    health_summary["component_breakdown"][component] = {"healthy": 0, "degraded": 0, "unhealthy": 0}
                health_summary["component_breakdown"][component][check.status] += 1

            # Process performance metrics summary
            perf_summary = {}
            for metric in performance_metrics:
                category = metric.metric_category
                if category not in perf_summary:
                    perf_summary[category] = {
                        "count": 0,
                        "avg_value": 0.0,
                        "min_value": float('inf'),
                        "max_value": float('-inf'),
                        "metrics": []
                    }

                perf_summary[category]["count"] += 1
                perf_summary[category]["avg_value"] += metric.value
                perf_summary[category]["min_value"] = min(perf_summary[category]["min_value"], metric.value)
                perf_summary[category]["max_value"] = max(perf_summary[category]["max_value"], metric.value)

            # Calculate averages
            for category in perf_summary:
                if perf_summary[category]["count"] > 0:
                    perf_summary[category]["avg_value"] /= perf_summary[category]["count"]
                if perf_summary[category]["min_value"] == float('inf'):
                    perf_summary[category]["min_value"] = 0.0
                if perf_summary[category]["max_value"] == float('-inf'):
                    perf_summary[category]["max_value"] = 0.0

            # Process anomalies summary
            anomaly_summary = {
                "total_anomalies": len(anomalies),
                "severity_breakdown": {},
                "type_breakdown": {},
                "high_confidence_anomalies": len([a for a in anomalies if a.confidence_score > 0.8]),
                "active_anomalies": len([a for a in anomalies if a.status == "active"])
            }

            for anomaly in anomalies:
                # Severity breakdown
                severity = anomaly.severity
                anomaly_summary["severity_breakdown"][severity] = anomaly_summary["severity_breakdown"].get(severity, 0) + 1

                # Type breakdown
                anomaly_type = anomaly.anomaly_type
                anomaly_summary["type_breakdown"][anomaly_type] = anomaly_summary["type_breakdown"].get(anomaly_type, 0) + 1

            return {
                "time_range": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "hours": time_range_hours,
                },
                "kpi_summary": kpi_summary,
                "health_summary": health_summary,
                "performance_summary": perf_summary,
                "anomaly_summary": anomaly_summary,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slo/dashboard")
async def get_slo_dashboard(
    time_range_days: int = Query(7, ge=1, le=90),
    slo_types: Optional[List[str]] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get SLO dashboard data."""
    try:
        async with tracing_service.trace_span(
            "observability.get_slo_dashboard",
            tracing_service.SpanMetadata(
                component="observability",
                operation="get_slo_dashboard",
                user_id=str(current_user.id),
                additional_attributes={"time_range_days": time_range_days}
            )
        ):
            dashboard_data = await metrics_service.get_slo_dashboard_data(
                time_range_days=time_range_days,
                slo_types=slo_types
            )

            return dashboard_data

    except Exception as e:
        logger.error(f"Failed to get SLO dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(
    severity: Optional[AlertSeverity] = Query(None),
    status: Optional[AlertStatus] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get alerts with filtering and pagination."""
    try:
        # Build query
        query = select(Alert).order_by(desc(Alert.evaluated_at))

        # Apply filters
        if severity:
            query = query.where(Alert.severity == severity.value)
        if status:
            query = query.where(Alert.status == status.value)

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        alerts = result.scalars().all()

        # Get total count
        count_query = select(func.count(Alert.id))
        if severity:
            count_query = count_query.where(Alert.severity == severity.value)
        if status:
            count_query = count_query.where(Alert.status == status.value)

        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        return {
            "alerts": [
                {
                    "id": str(alert.id),
                    "name": alert.name,
                    "description": alert.description,
                    "severity": alert.severity,
                    "status": alert.status,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "evaluated_at": alert.evaluated_at.isoformat(),
                    "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                    "acknowledged_by": alert.acknowledged_by,
                    "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                    "resolved_by": alert.resolved_by,
                    "escalation_level": alert.escalation_level,
                    "context": alert.context,
                    "metadata": alert.metadata,
                }
                for alert in alerts
            ],
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(alerts) < total_count,
            }
        }

    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    note: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Acknowledge an alert."""
    try:
        async with tracing_service.trace_span(
            "observability.acknowledge_alert",
            tracing_service.SpanMetadata(
                component="observability",
                operation="acknowledge_alert",
                user_id=str(current_user.id),
                additional_attributes={"alert_id": alert_id}
            )
        ):
            success = await alert_service.acknowledge_alert(
                alert_id=alert_id,
                acknowledged_by=current_user.email,
                note=note
            )

            if not success:
                raise HTTPException(status_code=404, detail="Alert not found or cannot be acknowledged")

            return {"message": "Alert acknowledged successfully", "alert_id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_note: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Resolve an alert."""
    try:
        async with tracing_service.trace_span(
            "observability.resolve_alert",
            tracing_service.SpanMetadata(
                component="observability",
                operation="resolve_alert",
                user_id=str(current_user.id),
                additional_attributes={"alert_id": alert_id}
            )
        ):
            success = await alert_service.resolve_alert(
                alert_id=alert_id,
                resolution_note=resolution_note,
                resolved_by=current_user.email
            )

            if not success:
                raise HTTPException(status_code=404, detail="Alert not found or cannot be resolved")

            return {"message": "Alert resolved successfully", "alert_id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runbooks")
async def get_runbooks(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get list of available runbooks."""
    try:
        runbooks = await runbook_service.get_available_runbooks()

        return [
            {
                "id": runbook.id,
                "name": runbook.name,
                "description": runbook.description,
                "severity": runbook.severity.value,
                "category": runbook.category,
                "triggers": runbook.triggers,
                "total_steps": len(runbook.steps),
                "requires_approval": runbook.requires_approval,
                "max_execution_time_minutes": runbook.max_execution_time_minutes,
                "metadata": runbook.metadata,
            }
            for runbook in runbooks
        ]

    except Exception as e:
        logger.error(f"Failed to get runbooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runbooks/{runbook_id}/execute")
async def execute_runbook(
    runbook_id: str,
    trigger_context: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Execute a runbook."""
    try:
        async with tracing_service.trace_span(
            "observability.execute_runbook",
            tracing_service.SpanMetadata(
                component="observability",
                operation="execute_runbook",
                user_id=str(current_user.id),
                additional_attributes={"runbook_id": runbook_id}
            )
        ):
            execution = await runbook_service.trigger_runbook(
                runbook_id=runbook_id,
                trigger_context={
                    **trigger_context,
                    "triggered_by": current_user.email,
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                },
                user_id=str(current_user.id)
            )

            return {
                "execution_id": execution.id,
                "runbook_id": execution.runbook_id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "total_steps": execution.total_steps,
                "message": "Runbook execution started",
            }

    except Exception as e:
        logger.error(f"Failed to execute runbook {runbook_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runbooks/executions")
async def get_runbook_executions(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get runbook executions with filtering and pagination."""
    try:
        # Build query
        query = select(RunbookExecution).order_by(desc(RunbookExecution.started_at))

        # Apply filters
        if status:
            query = query.where(RunbookExecution.status == status)

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        executions = result.scalars().all()

        # Get total count
        count_query = select(func.count(RunbookExecution.id))
        if status:
            count_query = count_query.where(RunbookExecution.status == status)

        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        return {
            "executions": [
                {
                    "id": str(execution.id),
                    "runbook_id": execution.runbook_id,
                    "runbook_name": execution.runbook_name,
                    "status": execution.status,
                    "current_step": execution.current_step,
                    "total_steps": execution.total_steps,
                    "completed_steps": execution.completed_steps,
                    "failed_steps": execution.failed_steps,
                    "started_at": execution.started_at.isoformat(),
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "duration_seconds": execution.duration_seconds,
                    "error_message": execution.error_message,
                    "triggered_by": execution.triggered_by,
                    "metadata": execution.metadata,
                }
                for execution in executions
            ],
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(executions) < total_count,
            }
        }

    except Exception as e:
        logger.error(f"Failed to get runbook executions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runbooks/executions/{execution_id}")
async def get_runbook_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get details of a specific runbook execution."""
    try:
        # Get execution
        execution_query = select(RunbookExecution).where(RunbookExecution.id == execution_id)
        execution_result = await session.execute(execution_query)
        execution = execution_result.scalar_one_or_none()

        if not execution:
            raise HTTPException(status_code=404, detail="Runbook execution not found")

        # Get step executions
        steps_query = select(RunbookStepExecution).where(
            RunbookStepExecution.execution_id == execution.id
        ).order_by(RunbookStepExecution.created_at)

        steps_result = await session.execute(steps_query)
        step_executions = steps_result.scalars().all()

        return {
            "execution": {
                "id": str(execution.id),
                "runbook_id": execution.runbook_id,
                "runbook_name": execution.runbook_name,
                "status": execution.status,
                "current_step": execution.current_step,
                "total_steps": execution.total_steps,
                "completed_steps": execution.completed_steps,
                "failed_steps": execution.failed_steps,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration_seconds": execution.duration_seconds,
                "error_message": execution.error_message,
                "error_details": execution.error_details,
                "trigger_context": execution.trigger_context,
                "execution_context": execution.execution_context,
                "step_results": execution.step_results,
                "triggered_by": execution.triggered_by,
                "requires_approval": execution.requires_approval,
                "approved_at": execution.approved_at.isoformat() if execution.approved_at else None,
                "approved_by": execution.approved_by,
                "metadata": execution.metadata,
            },
            "step_executions": [
                {
                    "id": str(step.id),
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "status": step.status,
                    "action_type": step.action_type,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "duration_seconds": step.duration_seconds,
                    "result": step.result,
                    "error_message": step.error_message,
                    "error_details": step.error_details,
                    "retry_count": step.retry_count,
                    "max_retries": step.max_retries,
                    "dependencies": step.dependencies,
                    "parallel": step.parallel,
                    "metadata": step.metadata,
                }
                for step in step_executions
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get runbook execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runbooks/executions/{execution_id}/cancel")
async def cancel_runbook_execution(
    execution_id: str,
    reason: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Cancel a running runbook execution."""
    try:
        async with tracing_service.trace_span(
            "observability.cancel_runbook_execution",
            tracing_service.SpanMetadata(
                component="observability",
                operation="cancel_runbook_execution",
                user_id=str(current_user.id),
                additional_attributes={"execution_id": execution_id}
            )
        ):
            success = await runbook_service.cancel_execution(
                execution_id=execution_id,
                reason=f"Cancelled by {current_user.email}: {reason}"
            )

            if not success:
                raise HTTPException(status_code=404, detail="Runbook execution not found or cannot be cancelled")

            return {"message": "Runbook execution cancelled successfully", "execution_id": execution_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel runbook execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emergency-drill")
async def execute_emergency_drill(
    drill_type: str,
    background_tasks: BackgroundTasks,
    execution_context: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Execute an emergency drill."""
    try:
        async with tracing_service.trace_span(
            "observability.execute_emergency_drill",
            tracing_service.SpanMetadata(
                component="observability",
                operation="execute_emergency_drill",
                user_id=str(current_user.id),
                additional_attributes={"drill_type": drill_type}
            )
        ):
            execution = await runbook_service.execute_emergency_drill(
                drill_type=drill_type,
                execution_context={
                    **(execution_context or {}),
                    "initiated_by": current_user.email,
                    "initiated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            return {
                "execution_id": execution.id,
                "drill_type": drill_type,
                "runbook_id": execution.runbook_id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "message": "Emergency drill started",
            }

    except Exception as e:
        logger.error(f"Failed to execute emergency drill {drill_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system-health")
async def get_system_health(
    component: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get system health check data."""
    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Build query
        query = select(SystemHealthCheck).where(
            SystemHealthCheck.checked_at >= start_time
        ).order_by(desc(SystemHealthCheck.checked_at))

        if component:
            query = query.where(SystemHealthCheck.component == component)

        result = await session.execute(query)
        health_checks = result.scalars().all()

        # Group by component
        component_health = {}
        for check in health_checks:
            comp = check.component
            if comp not in component_health:
                component_health[comp] = []
            component_health[comp].append({
                "check_name": check.check_name,
                "status": check.status,
                "response_time_ms": check.response_time_ms,
                "message": check.message,
                "checked_at": check.checked_at.isoformat(),
                "details": check.details,
                "metrics": check.metrics,
            })

        # Calculate overall summary
        total_checks = len(health_checks)
        healthy_count = len([h for h in health_checks if h.status == "healthy"])
        degraded_count = len([h for h in health_checks if h.status == "degraded"])
        unhealthy_count = len([h for h in health_checks if h.status == "unhealthy"])

        overall_status = "healthy"
        if unhealthy_count > 0:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"

        return {
            "overall_status": overall_status,
            "summary": {
                "total_checks": total_checks,
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count,
                "health_percentage": (healthy_count / total_checks * 100) if total_checks > 0 else 0,
            },
            "component_health": component_health,
            "time_range": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "hours": hours,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces")
async def get_traces(
    trace_id: Optional[str] = Query(None),
    component: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get trace data with filtering."""
    try:
        from app.models.observability import TraceSpan

        # Build query
        query = select(TraceSpan).order_by(desc(TraceSpan.start_time))

        # Apply filters
        if trace_id:
            query = query.where(TraceSpan.trace_id == trace_id)
        if component:
            query = query.where(TraceSpan.component == component)
        if operation:
            query = query.where(TraceSpan.operation_name.like(f"%{operation}%"))

        # Apply limit
        query = query.limit(limit)

        result = await session.execute(query)
        traces = result.scalars().all()

        # Group by trace_id
        trace_groups = {}
        for trace in traces:
            if trace.trace_id not in trace_groups:
                trace_groups[trace.trace_id] = {
                    "trace_id": trace.trace_id,
                    "spans": [],
                    "total_spans": 0,
                    "total_duration_ms": 0,
                    "start_time": None,
                    "end_time": None,
                }

            trace_group = trace_groups[trace.trace_id]
            trace_group["spans"].append({
                "span_id": trace.span_id,
                "parent_span_id": trace.parent_span_id,
                "operation_name": trace.operation_name,
                "component": trace.component,
                "service_name": trace.service_name,
                "start_time": trace.start_time.isoformat(),
                "end_time": trace.end_time.isoformat() if trace.end_time else None,
                "duration_ms": trace.duration_ms,
                "status_code": trace.status_code,
                "status_message": trace.status_message,
                "tags": trace.tags,
                "attributes": trace.attributes,
                "operation_cost": trace.operation_cost,
                "llm_tokens_used": trace.llm_tokens_used,
                "llm_cost": trace.llm_cost,
            })

            trace_group["total_spans"] += 1
            if trace.duration_ms:
                trace_group["total_duration_ms"] += trace.duration_ms

            if trace_group["start_time"] is None or trace.start_time < trace_group["start_time"]:
                trace_group["start_time"] = trace.start_time

            if trace.end_time and (trace_group["end_time"] is None or trace.end_time > trace_group["end_time"]):
                trace_group["end_time"] = trace.end_time

        # Convert datetime to isoformat
        for trace_group in trace_groups.values():
            if trace_group["start_time"]:
                trace_group["start_time"] = trace_group["start_time"].isoformat()
            if trace_group["end_time"]:
                trace_group["end_time"] = trace_group["end_time"].isoformat()

        return {
            "traces": list(trace_groups.values()),
            "total_traces": len(trace_groups),
            "filters": {
                "trace_id": trace_id,
                "component": component,
                "operation": operation,
                "limit": limit,
            }
        }

    except Exception as e:
        logger.error(f"Failed to get traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prometheus/metrics")
async def get_prometheus_metrics(
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Get Prometheus metrics."""
    try:
        return prometheus_service.get_metrics_response()

    except Exception as e:
        logger.error(f"Failed to get Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/record")
async def record_metric(
    metric_name: str,
    metric_category: str,
    value: float,
    unit: Optional[str] = None,
    dimensions: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Record a custom metric."""
    try:
        await metrics_service.record_system_metric(
            metric_name=metric_name,
            metric_category=metric_category,
            value=value,
            unit=unit,
            dimensions=dimensions,
            tags=tags,
            metadata=metadata,
            data_source="api",
            confidence_score=1.0,
        )

        return {"message": "Metric recorded successfully", "metric_name": metric_name}

    except Exception as e:
        logger.error(f"Failed to record metric {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/custom")
async def create_custom_alert(
    name: str,
    description: str,
    severity: AlertSeverity,
    context: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a custom alert."""
    try:
        alert = await alert_service.create_custom_alert(
            name=name,
            description=description,
            severity=severity,
            context={
                **context,
                "created_by": current_user.email,
            },
            metadata=metadata,
        )

        return {
            "alert_id": alert.id,
            "name": alert.name,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "created_at": alert.evaluated_at.isoformat(),
            "message": "Custom alert created successfully",
        }

    except Exception as e:
        logger.error(f"Failed to create custom alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))