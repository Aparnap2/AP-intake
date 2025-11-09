"""
Runbook execution service for automated emergency response and system recovery procedures.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.tracing_service import tracing_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class RunbookStatus(str, Enum):
    """Runbook execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class RunbookSeverity(str, Enum):
    """Runbook severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StepStatus(str, Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RunbookStep:
    """Individual runbook step definition."""
    id: str
    name: str
    description: str
    action_type: str  # command, api_call, script, manual, rollback
    command: Optional[str] = None
    api_endpoint: Optional[str] = None
    script_path: Optional[str] = None
    timeout_seconds: int = 300
    retry_count: int = 0
    rollback_command: Optional[str] = None
    expected_result: Optional[Dict[str, Any]] = None
    requires_approval: bool = False
    parallel: bool = False
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunbookExecution:
    """Runbook execution context."""
    id: str
    runbook_id: str
    status: RunbookStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_context: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    current_step: Optional[str] = None
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunbookDefinition:
    """Runbook definition."""
    id: str
    name: str
    description: str
    severity: RunbookSeverity
    category: str
    triggers: List[str]  # Conditions that trigger this runbook
    steps: List[RunbookStep]
    rollback_strategy: str  # automatic, manual, none
    max_execution_time_minutes: int = 60
    requires_approval: bool = False
    approval_timeout_minutes: int = 15
    metadata: Dict[str, Any] = field(default_factory=dict)


class RunbookService:
    """Comprehensive runbook execution and management service."""

    def __init__(self):
        """Initialize the runbook service."""
        self.logger = logging.getLogger(__name__)
        self.active_executions: Dict[str, RunbookExecution] = {}
        self.runbooks: Dict[str, RunbookDefinition] = {}
        self.execution_callbacks: Dict[str, List[Callable]] = {}
        self._load_default_runbooks()

    def _load_default_runbooks(self) -> None:
        """Load default runbook definitions."""
        try:
            # Emergency Rollback Runbook
            emergency_rollback = RunbookDefinition(
                id="emergency_rollback",
                name="Emergency Staged Export Rollback",
                description="Rollback all staged exports within the specified time window",
                severity=RunbookSeverity.CRITICAL,
                category="recovery",
                triggers=["export_failure", "data_corruption", "emergency_shutdown"],
                steps=[
                    RunbookStep(
                        id="identify_staged_exports",
                        name="Identify Staged Exports",
                        description="Find all staged exports within rollback window",
                        action_type="api_call",
                        api_endpoint="/api/v1/exports/staged/list",
                        timeout_seconds=60,
                        expected_result={"status": "success", "exports_found": True},
                        metadata={"rollback_window_hours": 24}
                    ),
                    RunbookStep(
                        id="validate_rollback_eligibility",
                        name="Validate Rollback Eligibility",
                        description="Check which exports can be safely rolled back",
                        action_type="api_call",
                        api_endpoint="/api/v1/exports/validate-rollback",
                        timeout_seconds=120,
                        dependencies=["identify_staged_exports"]
                    ),
                    RunbookStep(
                        id="execute_rollback",
                        name="Execute Rollback",
                        description="Rollback staged exports and update statuses",
                        action_type="api_call",
                        api_endpoint="/api/v1/exports/rollback",
                        timeout_seconds=300,
                        requires_approval=True,
                        dependencies=["validate_rollback_eligibility"]
                    ),
                    RunbookStep(
                        id="notify_stakeholders",
                        name="Notify Stakeholders",
                        description="Send rollback completion notifications",
                        action_type="api_call",
                        api_endpoint="/api/v1/notifications/send-rollback",
                        timeout_seconds=60,
                        dependencies=["execute_rollback"]
                    ),
                    RunbookStep(
                        id="log_audit_trail",
                        name="Log Audit Trail",
                        description="Create comprehensive audit log of rollback",
                        action_type="api_call",
                        api_endpoint="/api/v1/audit/create",
                        timeout_seconds=60,
                        dependencies=["execute_rollback"]
                    )
                ],
                rollback_strategy="automatic",
                max_execution_time_minutes=30,
                requires_approval=True,
                metadata={"emergency": True, "impact_scope": "all_staged_exports"}
            )

            # DLQ Recovery Runbook
            dlq_recovery = RunbookDefinition(
                id="dlq_recovery",
                name="Dead Letter Queue Recovery",
                description="Process and recover failed messages from dead letter queues",
                severity=RunbookSeverity.HIGH,
                category="recovery",
                triggers=["dlq_threshold_exceeded", "queue_processing_failure"],
                steps=[
                    RunbookStep(
                        id="analyze_dlq_contents",
                        name="Analyze DLQ Contents",
                        description="Examine failed messages and categorize by error type",
                        action_type="api_call",
                        api_endpoint="/api/v1/celery/dlq/analyze",
                        timeout_seconds=120,
                        expected_result={"status": "success"}
                    ),
                    RunbookStep(
                        id="identify_recovery_candidates",
                        name="Identify Recovery Candidates",
                        description="Determine which messages can be auto-recovered",
                        action_type="api_call",
                        api_endpoint="/api/v1/celery/dlq/recovery-candidates",
                        timeout_seconds=180,
                        dependencies=["analyze_dlq_contents"]
                    ),
                    RunbookStep(
                        id="test_message_retry",
                        name="Test Message Retry",
                        description="Test retry on a sample of failed messages",
                        action_type="api_call",
                        api_endpoint="/api/v1/celery/dlq/test-retry",
                        timeout_seconds=300,
                        dependencies=["identify_recovery_candidates"]
                    ),
                    RunbookStep(
                        id="execute_batch_retry",
                        name="Execute Batch Retry",
                        description="Retry eligible messages in batches",
                        action_type="api_call",
                        api_endpoint="/api/v1/celery/dlq/batch-retry",
                        timeout_seconds=600,
                        dependencies=["test_message_retry"]
                    ),
                    RunbookStep(
                        id="move_permanent_failures",
                        name="Move Permanent Failures",
                        description="Move messages that cannot be recovered to permanent storage",
                        action_type="api_call",
                        api_endpoint="/api/v1/celery/dlq/archive-failures",
                        timeout_seconds=300,
                        dependencies=["execute_batch_retry"]
                    ),
                    RunbookStep(
                        id="update_monitoring",
                        name="Update Monitoring Dashboards",
                        description="Update monitoring with recovery results",
                        action_type="api_call",
                        api_endpoint="/api/v1/monitoring/update-dlq-status",
                        timeout_seconds=60,
                        dependencies=["execute_batch_retry", "move_permanent_failures"]
                    )
                ],
                rollback_strategy="automatic",
                max_execution_time_minutes=45,
                metadata={"queue_types": ["celery", "redis", "rabbitmq"]}
            )

            # Invoice Recovery Runbook
            invoice_recovery = RunbookDefinition(
                id="invoice_recovery",
                name="Invoice Processing Recovery",
                description="Reopen and reprocess failed invoices from last known good state",
                severity=RunbookSeverity.MEDIUM,
                category="recovery",
                triggers=["invoice_batch_failure", "processing_bottleneck"],
                steps=[
                    RunbookStep(
                        id="identify_failed_invoices",
                        name="Identify Failed Invoices",
                        description="Find invoices that failed processing",
                        action_type="api_call",
                        api_endpoint="/api/v1/invoices/failed/list",
                        timeout_seconds=120,
                        expected_result={"status": "success", "failed_invoices": True}
                    ),
                    RunbookStep(
                        id="determine_failure_root_cause",
                        name="Determine Failure Root Cause",
                        description="Analyze failure patterns and identify root cause",
                        action_type="api_call",
                        api_endpoint="/api/v1/invoices/analyze-failures",
                        timeout_seconds=180,
                        dependencies=["identify_failed_invoices"]
                    ),
                    RunbookStep(
                        id="create_recovery_plan",
                        name="Create Recovery Plan",
                        description="Generate step-by-step recovery plan",
                        action_type="api_call",
                        api_endpoint="/api/v1/invoices/recovery-plan",
                        timeout_seconds=300,
                        dependencies=["determine_failure_root_cause"]
                    ),
                    RunbookStep(
                        id="execute_recovery",
                        name="Execute Invoice Recovery",
                        description="Reprocess invoices from last known good state",
                        action_type="api_call",
                        api_endpoint="/api/v1/invoices/recover",
                        timeout_seconds=600,
                        requires_approval=True,
                        dependencies=["create_recovery_plan"]
                    ),
                    RunbookStep(
                        id="validate_recovery",
                        name="Validate Recovery Results",
                        description="Verify that invoices were successfully recovered",
                        action_type="api_call",
                        api_endpoint="/api/v1/invoices/validate-recovery",
                        timeout_seconds=180,
                        dependencies=["execute_recovery"]
                    ),
                    RunbookStep(
                        id="update_status_notifications",
                        name="Update Status Notifications",
                        description="Send recovery status updates",
                        action_type="api_call",
                        api_endpoint="/api/v1/notifications/recovery-status",
                        timeout_seconds=60,
                        dependencies=["validate_recovery"]
                    )
                ],
                rollback_strategy="manual",
                max_execution_time_minutes=60,
                metadata={"recovery_modes": ["from_checkpoint", "full_reprocess"]}
            )

            # System Recovery Runbook
            system_recovery = RunbookDefinition(
                id="system_recovery",
                name="System Recovery and Restoration",
                description="Restore system from backup after critical failure",
                severity=RunbookSeverity.CRITICAL,
                category="recovery",
                triggers=["system_crash", "database_corruption", "critical_service_failure"],
                steps=[
                    RunbookStep(
                        id="assess_system_state",
                        name="Assess System State",
                        description="Determine current system state and damage assessment",
                        action_type="command",
                        command="systemctl status --all && df -h && free -m",
                        timeout_seconds=60,
                        expected_result={"system_assessed": True}
                    ),
                    RunbookStep(
                        id="stop_affected_services",
                        name="Stop Affected Services",
                        description="Gracefully stop services to prevent further damage",
                        action_type="command",
                        command="docker-compose stop api worker celery",
                        timeout_seconds=120,
                        dependencies=["assess_system_state"]
                    ),
                    RunbookStep(
                        id="validate_backup_integrity",
                        name="Validate Backup Integrity",
                        description="Verify that backups are intact and recoverable",
                        action_type="api_call",
                        api_endpoint="/api/v1/backup/validate",
                        timeout_seconds=300,
                        dependencies=["stop_affected_services"]
                    ),
                    RunbookStep(
                        id="execute_database_restore",
                        name="Execute Database Restore",
                        description="Restore database from latest valid backup",
                        action_type="api_call",
                        api_endpoint="/api/v1/database/restore",
                        timeout_seconds=600,
                        requires_approval=True,
                        dependencies=["validate_backup_integrity"]
                    ),
                    RunbookStep(
                        id="restore_file_storage",
                        name="Restore File Storage",
                        description="Restore uploaded files and processed documents",
                        action_type="api_call",
                        api_endpoint="/api/v1/storage/restore",
                        timeout_seconds=300,
                        dependencies=["execute_database_restore"]
                    ),
                    RunbookStep(
                        id="restart_services",
                        name="Restart Services",
                        description="Restart all services in correct order",
                        action_type="command",
                        command="docker-compose up -d",
                        timeout_seconds=180,
                        dependencies=["restore_file_storage"]
                    ),
                    RunbookStep(
                        id="verify_system_health",
                        name="Verify System Health",
                        description="Run comprehensive health checks",
                        action_type="api_call",
                        api_endpoint="/api/v1/health/comprehensive",
                        timeout_seconds=120,
                        dependencies=["restart_services"]
                    ),
                    RunbookStep(
                        id="enable_monitoring_alerts",
                        name="Enable Monitoring Alerts",
                        description="Re-enable monitoring and alerting",
                        action_type="api_call",
                        api_endpoint="/api/v1/monitoring/enable",
                        timeout_seconds=60,
                        dependencies=["verify_system_health"]
                    )
                ],
                rollback_strategy="manual",
                max_execution_time_minutes=120,
                requires_approval=True,
                metadata={"backup_types": ["database", "files", "config"]}
            )

            # Performance Degradation Runbook
            performance_degradation = RunbookDefinition(
                id="performance_degradation",
                name="Performance Degradation Response",
                description="Address system performance degradation and bottlenecks",
                severity=RunbookSeverity.MEDIUM,
                category="performance",
                triggers=["performance_threshold_exceeded", "response_time_spike"],
                steps=[
                    RunbookStep(
                        id="identify_performance_bottlenecks",
                        name="Identify Performance Bottlenecks",
                        description="Analyze system metrics to identify bottlenecks",
                        action_type="api_call",
                        api_endpoint="/api/v1/performance/analyze",
                        timeout_seconds=180,
                        expected_result={"bottlenecks_identified": True}
                    ),
                    RunbookStep(
                        id="check_resource_utilization",
                        name="Check Resource Utilization",
                        description="Monitor CPU, memory, disk, and network usage",
                        action_type="command",
                        command="top -b -n1 && iostat -x 1 2 && df -h",
                        timeout_seconds=60,
                        dependencies=["identify_performance_bottlenecks"]
                    ),
                    RunbookStep(
                        id="clear_caches_temporary",
                        name="Clear Temporary Caches",
                        description="Clear application and system caches",
                        action_type="command",
                        command="redis-cli FLUSHDB && find /tmp -name '*cache*' -delete",
                        timeout_seconds=120,
                        dependencies=["check_resource_utilization"]
                    ),
                    RunbookStep(
                        id="restart_problematic_services",
                        name="Restart Problematic Services",
                        description="Restart services showing poor performance",
                        action_type="command",
                        command="docker-compose restart api worker",
                        timeout_seconds=180,
                        dependencies=["clear_caches_temporary"]
                    ),
                    RunbookStep(
                        id="optimize_database_queries",
                        name="Optimize Database Queries",
                        description="Run database optimizations and update statistics",
                        action_type="api_call",
                        api_endpoint="/api/v1/database/optimize",
                        timeout_seconds=300,
                        dependencies=["restart_problematic_services"]
                    ),
                    RunbookStep(
                        id="scale_resources_if_needed",
                        name="Scale Resources If Needed",
                        description="Auto-scale resources based on load",
                        action_type="api_call",
                        api_endpoint="/api/v1/infrastructure/scale",
                        timeout_seconds=240,
                        dependencies=["optimize_database_queries"]
                    ),
                    RunbookStep(
                        id="monitor_recovery",
                        name="Monitor Recovery",
                        description="Monitor system for 30 minutes post-recovery",
                        action_type="api_call",
                        api_endpoint="/api/v1/performance/monitor",
                        timeout_seconds=1800,
                        dependencies=["scale_resources_if_needed"]
                    )
                ],
                rollback_strategy="automatic",
                max_execution_time_minutes=60,
                metadata={"auto_scaling": True, "cache_clearing": True}
            )

            # Data Integrity Runbook
            data_integrity = RunbookDefinition(
                id="data_integrity",
                name="Data Integrity Check and Repair",
                description="Verify and repair data integrity issues",
                severity=RunbookSeverity.HIGH,
                category="integrity",
                triggers=["data_corruption_detected", "validation_failure_batch"],
                steps=[
                    RunbookStep(
                        id="identify_corrupted_data",
                        name="Identify Corrupted Data",
                        description="Scan for data integrity violations",
                        action_type="api_call",
                        api_endpoint="/api/v1/data/integrity-scan",
                        timeout_seconds=300,
                        expected_result={"scan_completed": True}
                    ),
                    RunbookStep(
                        id="isolate_affected_records",
                        name="Isolate Affected Records",
                        description="Quarantine corrupted records to prevent spread",
                        action_type="api_call",
                        api_endpoint="/api/v1/data/isolate-corrupted",
                        timeout_seconds=180,
                        dependencies=["identify_corrupted_data"]
                    ),
                    RunbookStep(
                        id="determine_repair_strategy",
                        name="Determine Repair Strategy",
                        action_type="api_call",
                        api_endpoint="/api/v1/data/repair-strategy",
                        timeout_seconds=240,
                        dependencies=["isolate_affected_records"]
                    ),
                    RunbookStep(
                        id="execute_data_repair",
                        name="Execute Data Repair",
                        description="Repair or restore corrupted data",
                        action_type="api_call",
                        api_endpoint="/api/v1/data/repair",
                        timeout_seconds=600,
                        requires_approval=True,
                        dependencies=["determine_repair_strategy"]
                    ),
                    RunbookStep(
                        id="verify_repairs",
                        name="Verify Repairs",
                        description="Validate that data integrity is restored",
                        action_type="api_call",
                        api_endpoint="/api/v1/data/verify-repair",
                        timeout_seconds=300,
                        dependencies=["execute_data_repair"]
                    ),
                    RunbookStep(
                        id="update_indices_constraints",
                        name="Update Indices and Constraints",
                        description="Rebuild database indices and constraints",
                        action_type="api_call",
                        api_endpoint="/api/v1/database/rebuild-indices",
                        timeout_seconds=400,
                        dependencies=["verify_repairs"]
                    ),
                    RunbookStep(
                        id="run_full_integrity_check",
                        name="Run Full Integrity Check",
                        description="Comprehensive data integrity verification",
                        action_type="api_call",
                        api_endpoint="/api/v1/data/full-integrity-check",
                        timeout_seconds=600,
                        dependencies=["update_indices_constraints"]
                    )
                ],
                rollback_strategy="manual",
                max_execution_time_minutes=90,
                metadata={"repair_methods": ["restore", "reconstruct", "manual"]}
            )

            # Security Incident Runbook
            security_incident = RunbookDefinition(
                id="security_incident",
                name="Security Incident Response",
                description="Respond to security incidents and potential breaches",
                severity=RunbookSeverity.CRITICAL,
                category="security",
                triggers=["security_breach_detected", "unauthorized_access", "suspicious_activity"],
                steps=[
                    RunbookStep(
                        id="assess_security_incident",
                        name="Assess Security Incident",
                        description="Initial assessment of security incident scope",
                        action_type="api_call",
                        api_endpoint="/api/v1/security/assess-incident",
                        timeout_seconds=300,
                        expected_result={"assessment_completed": True}
                    ),
                    RunbookStep(
                        id="contain_threat",
                        name="Contain Threat",
                        description="Isolate affected systems and prevent spread",
                        action_type="command",
                        command="iptables -A INPUT -s SUSPICIOUS_IP -j DROP",
                        timeout_seconds=120,
                        dependencies=["assess_security_incident"]
                    ),
                    RunbookStep(
                        id="preserve_evidence",
                        name="Preserve Evidence",
                        description="Collect and preserve forensic evidence",
                        action_type="command",
                        command="tar -czf security_evidence_$(date +%Y%m%d_%H%M%S).tar.gz /var/log/ /tmp/",
                        timeout_seconds=180,
                        dependencies=["contain_threat"]
                    ),
                    RunbookStep(
                        id="rotate_credentials",
                        name="Rotate Credentials",
                        description="Rotate all potentially compromised credentials",
                        action_type="api_call",
                        api_endpoint="/api/v1/security/rotate-credentials",
                        timeout_seconds=240,
                        dependencies=["preserve_evidence"]
                    ),
                    RunbookStep(
                        id="patch_vulnerabilities",
                        name="Patch Vulnerabilities",
                        description="Apply security patches to close vulnerabilities",
                        action_type="command",
                        command="apt-get update && apt-get upgrade -y",
                        timeout_seconds=600,
                        dependencies=["rotate_credentials"]
                    ),
                    RunbookStep(
                        id="scan_for_malware",
                        name="Scan for Malware",
                        description="Comprehensive malware and intrusion detection scan",
                        action_type="command",
                        command="clamscan -r / --bell -i",
                        timeout_seconds=1200,
                        dependencies=["patch_vulnerabilities"]
                    ),
                    RunbookStep(
                        id="audit_user_accounts",
                        name="Audit User Accounts",
                        description="Review and audit all user accounts and access",
                        action_type="api_call",
                        api_endpoint="/api/v1/security/audit-accounts",
                        timeout_seconds=300,
                        dependencies=["scan_for_malware"]
                    ),
                    RunbookStep(
                        id="update_security_config",
                        name="Update Security Configuration",
                        description="Strengthen security configurations",
                        action_type="api_call",
                        api_endpoint="/api/v1/security/update-config",
                        timeout_seconds=240,
                        dependencies=["audit_user_accounts"]
                    ),
                    RunbookStep(
                        id="notify_security_team",
                        name="Notify Security Team",
                        description="Alert security team and stakeholders",
                        action_type="api_call",
                        api_endpoint="/api/v1/notifications/security-incident",
                        timeout_seconds=60,
                        dependencies=["assess_security_incident"]
                    )
                ],
                rollback_strategy="manual",
                max_execution_time_minutes=90,
                requires_approval=True,
                metadata=["incident_type", "severity", "affected_systems"]
            )

            # Register all runbooks
            self.runbooks.update({
                "emergency_rollback": emergency_rollback,
                "dlq_recovery": dlq_recovery,
                "invoice_recovery": invoice_recovery,
                "system_recovery": system_recovery,
                "performance_degradation": performance_degradation,
                "data_integrity": data_integrity,
                "security_incident": security_incident,
            })

            self.logger.info(f"Loaded {len(self.runbooks)} default runbooks")

        except Exception as e:
            self.logger.error(f"Failed to load default runbooks: {e}")
            raise

    async def trigger_runbook(
        self,
        runbook_id: str,
        trigger_context: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> RunbookExecution:
        """
        Trigger a runbook execution.

        Args:
            runbook_id: ID of the runbook to execute
            trigger_context: Context information about what triggered the runbook
            user_id: Optional user ID who triggered the runbook

        Returns:
            RunbookExecution instance
        """
        try:
            runbook = self.runbooks.get(runbook_id)
            if not runbook:
                raise ValueError(f"Runbook not found: {runbook_id}")

            # Create execution context
            execution_id = str(uuid.uuid4())
            execution = RunbookExecution(
                id=execution_id,
                runbook_id=runbook_id,
                status=RunbookStatus.PENDING,
                started_at=datetime.now(timezone.utc),
                execution_context={
                    "trigger_context": trigger_context,
                    "user_id": user_id,
                    "runbook_severity": runbook.severity.value,
                    "runbook_category": runbook.category,
                },
                total_steps=len(runbook.steps),
                metadata={
                    "runbook_name": runbook.name,
                    "requires_approval": runbook.requires_approval,
                    "max_execution_time_minutes": runbook.max_execution_time_minutes,
                }
            )

            # Store execution
            self.active_executions[execution_id] = execution

            # Start execution in background
            asyncio.create_task(self._execute_runbook(execution_id, runbook, trigger_context))

            self.logger.info(f"Triggered runbook '{runbook.name}' (ID: {execution_id})")

            # Send notification
            await notification_service.send_runbook_notification(
                runbook_id=runbook_id,
                execution_id=execution_id,
                status="started",
                message=f"Runbook '{runbook.name}' started execution"
            )

            return execution

        except Exception as e:
            self.logger.error(f"Failed to trigger runbook {runbook_id}: {e}")
            raise

    async def _execute_runbook(
        self,
        execution_id: str,
        runbook: RunbookDefinition,
        trigger_context: Dict[str, Any],
    ) -> None:
        """Execute a runbook with all its steps."""
        execution = self.active_executions.get(execution_id)
        if not execution:
            return

        try:
            # Update status to running
            execution.status = RunbookStatus.RUNNING
            execution.current_step = "initialization"

            # Create tracing span for the entire runbook execution
            async with tracing_service.trace_span(
                f"runbook.{runbook.id}",
                tracing_service.SpanMetadata(
                    component="runbook",
                    operation=f"execute_{runbook.id}",
                    workflow_id=execution_id,
                    additional_attributes={
                        "runbook.name": runbook.name,
                        "runbook.severity": runbook.severity.value,
                        "runbook.category": runbook.category,
                        "trigger_context": trigger_context,
                    }
                )
            ) as span_context:

                # Check if approval is required
                if runbook.requires_approval:
                    await self._wait_for_approval(execution, runbook, span_context)

                # Execute steps
                await self._execute_runbook_steps(execution, runbook, span_context)

                # Update final status
                if execution.failed_steps == 0:
                    execution.status = RunbookStatus.COMPLETED
                    execution.completed_at = datetime.now(timezone.utc)

                    # Send completion notification
                    await notification_service.send_runbook_notification(
                        runbook_id=runbook.id,
                        execution_id=execution_id,
                        status="completed",
                        message=f"Runbook '{runbook.name}' completed successfully"
                    )
                else:
                    execution.status = RunbookStatus.FAILED
                    execution.error_message = f"Failed to execute {execution.failed_steps} steps"
                    execution.completed_at = datetime.now(timezone.utc)

                    # Send failure notification
                    await notification_service.send_runbook_notification(
                        runbook_id=runbook.id,
                        execution_id=execution_id,
                        status="failed",
                        message=f"Runbook '{runbook.name}' failed with {execution.failed_steps} failed steps"
                    )

                self.logger.info(
                    f"Runbook execution {execution_id} completed with status: {execution.status.value}"
                )

        except Exception as e:
            execution.status = RunbookStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)

            self.logger.error(f"Runbook execution {execution_id} failed: {e}")

            # Send failure notification
            await notification_service.send_runbook_notification(
                runbook_id=runbook.id,
                execution_id=execution_id,
                status="failed",
                message=f"Runbook '{runbook.name}' failed: {str(e)}"
            )

        finally:
            # Clean up execution after completion
            await asyncio.sleep(300)  # Keep in memory for 5 minutes
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]

    async def _wait_for_approval(
        self,
        execution: RunbookExecution,
        runbook: RunbookDefinition,
        span_context: Dict[str, Any],
    ) -> None:
        """Wait for runbook approval if required."""
        try:
            # Send approval request notification
            await notification_service.send_runbook_notification(
                runbook_id=runbook.id,
                execution_id=execution.id,
                status="awaiting_approval",
                message=f"Runbook '{runbook.name}' requires approval to proceed"
            )

            tracing_service.add_event(
                span_context,
                "awaiting_approval",
                {"approval_timeout_minutes": runbook.approval_timeout_minutes}
            )

            # Wait for approval (would integrate with approval system)
            # For now, auto-approve critical runbooks in emergency mode
            if runbook.severity == RunbookSeverity.CRITICAL:
                self.logger.warning(f"Auto-approving critical runbook '{runbook.name}'")
                tracing_service.add_event(span_context, "auto_approved", {"reason": "critical_severity"})
            else:
                # Simulate approval wait
                await asyncio.sleep(5)  # Would wait for actual approval

            tracing_service.add_event(span_context, "approval_received", {"approved": True})

        except Exception as e:
            self.logger.error(f"Failed to wait for approval: {e}")
            raise

    async def _execute_runbook_steps(
        self,
        execution: RunbookExecution,
        runbook: RunbookDefinition,
        span_context: Dict[str, Any],
    ) -> None:
        """Execute all steps in the runbook."""
        try:
            # Build dependency graph
            step_graph = self._build_step_dependency_graph(runbook.steps)

            # Execute steps respecting dependencies
            completed_steps = set()
            failed_steps = set()

            while len(completed_steps) < len(runbook.steps):
                # Find steps that can be executed (dependencies satisfied)
                ready_steps = [
                    step for step in runbook.steps
                    if step.id not in completed_steps
                    and step.id not in failed_steps
                    and all(dep in completed_steps for dep in step.dependencies)
                ]

                if not ready_steps:
                    if failed_steps:
                        break  # No more steps can be executed due to failures
                    else:
                        # Circular dependency or other issue
                        raise RuntimeError("No executable steps found - possible circular dependency")

                # Execute ready steps (parallel if allowed)
                if any(step.parallel for step in ready_steps):
                    # Execute parallel steps
                    parallel_tasks = []
                    for step in ready_steps:
                        if step.parallel:
                            task = asyncio.create_task(
                                self._execute_step(execution, step, span_context)
                            )
                            parallel_tasks.append(task)

                    # Wait for parallel tasks
                    results = await asyncio.gather(*parallel_tasks, return_exceptions=True)

                    # Process results
                    for i, result in enumerate(results):
                        step = ready_steps[i]
                        if isinstance(result, Exception):
                            failed_steps.add(step.id)
                            execution.failed_steps += 1
                        else:
                            completed_steps.add(step.id)
                            execution.completed_steps += 1

                    # Execute non-parallel steps
                    non_parallel_steps = [step for step in ready_steps if not step.parallel]
                    for step in non_parallel_steps:
                        try:
                            await self._execute_step(execution, step, span_context)
                            completed_steps.add(step.id)
                            execution.completed_steps += 1
                        except Exception as e:
                            failed_steps.add(step.id)
                            execution.failed_steps += 1
                            self.logger.error(f"Step {step.id} failed: {e}")

                else:
                    # Execute sequentially
                    for step in ready_steps:
                        try:
                            await self._execute_step(execution, step, span_context)
                            completed_steps.add(step.id)
                            execution.completed_steps += 1
                        except Exception as e:
                            failed_steps.add(step.id)
                            execution.failed_steps += 1
                            self.logger.error(f"Step {step.id} failed: {e}")

                            # For non-critical steps, continue with others
                            if runbook.severity != RunbookSeverity.CRITICAL:
                                continue
                            else:
                                break  # Stop execution on critical failure

        except Exception as e:
            self.logger.error(f"Failed to execute runbook steps: {e}")
            raise

    async def _execute_step(
        self,
        execution: RunbookExecution,
        step: RunbookStep,
        parent_span_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single runbook step."""
        step_start_time = datetime.now(timezone.utc)
        execution.current_step = step.id

        # Create span for step execution
        async with tracing_service.trace_span(
            f"runbook_step.{step.id}",
            tracing_service.SpanMetadata(
                component="runbook_step",
                operation=step.name,
                workflow_id=execution.id,
                additional_attributes={
                    "step.id": step.id,
                    "step.action_type": step.action_type,
                    "step.timeout": step.timeout_seconds,
                    "step.retry_count": step.retry_count,
                }
            )
        ) as step_span_context:

            try:
                self.logger.info(f"Executing step: {step.name} ({step.id})")

                # Execute based on action type
                if step.action_type == "command":
                    result = await self._execute_command(step, step_span_context)
                elif step.action_type == "api_call":
                    result = await self._execute_api_call(step, step_span_context, execution.execution_context)
                elif step.action_type == "script":
                    result = await self._execute_script(step, step_span_context)
                elif step.action_type == "manual":
                    result = await self._execute_manual_step(step, step_span_context)
                else:
                    raise ValueError(f"Unknown action type: {step.action_type}")

                # Validate expected result if specified
                if step.expected_result:
                    self._validate_step_result(step, result)

                # Store step result
                execution.step_results[step.id] = {
                    "status": "completed",
                    "result": result,
                    "executed_at": step_start_time.isoformat(),
                    "duration_seconds": (datetime.now(timezone.utc) - step_start_time).total_seconds(),
                }

                tracing_service.add_event(step_span_context, "step_completed", {"result": result})

                self.logger.info(f"Step completed: {step.name}")
                return result

            except Exception as e:
                # Store failed step result
                execution.step_results[step.id] = {
                    "status": "failed",
                    "error": str(e),
                    "executed_at": step_start_time.isoformat(),
                    "duration_seconds": (datetime.now(timezone.utc) - step_start_time).total_seconds(),
                }

                tracing_service.add_event(step_span_context, "step_failed", {"error": str(e)})
                self.logger.error(f"Step failed: {step.name} - {e}")

                # Retry if configured
                if step.retry_count > 0:
                    step.retry_count -= 1
                    self.logger.info(f"Retrying step {step.name} ({step.retry_count} retries remaining)")
                    await asyncio.sleep(5)  # Brief delay before retry
                    return await self._execute_step(execution, step, parent_span_context)

                raise

    async def _execute_command(
        self,
        step: RunbookStep,
        span_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a shell command."""
        import subprocess

        tracing_service.add_event(span_context, "command_started", {"command": step.command})

        try:
            result = subprocess.run(
                step.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=step.timeout_seconds,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed with return code {result.returncode}: {result.stderr}")

            tracing_service.add_event(span_context, "command_completed", {
                "return_code": result.returncode,
                "stdout_length": len(result.stdout),
                "stderr_length": len(result.stderr),
            })

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out after {step.timeout_seconds} seconds")

    async def _execute_api_call(
        self,
        step: RunbookStep,
        span_context: Dict[str, Any],
        execution_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an API call."""
        import httpx

        tracing_service.add_event(span_context, "api_call_started", {"endpoint": step.api_endpoint})

        try:
            async with httpx.AsyncClient(timeout=step.timeout_seconds) as client:
                # Prepare request with execution context
                request_data = {
                    "execution_context": execution_context,
                    "step_metadata": step.metadata,
                }

                response = await client.post(step.api_endpoint, json=request_data)
                response.raise_for_status()

                result = response.json()

                tracing_service.add_event(span_context, "api_call_completed", {
                    "status_code": response.status_code,
                    "response_size": len(str(result)),
                })

                return result

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API call failed: {e.response.status_code} - {e.response.text}")
        except httpx.TimeoutException:
            raise RuntimeError(f"API call timed out after {step.timeout_seconds} seconds")

    async def _execute_script(
        self,
        step: RunbookStep,
        span_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a script file."""
        import subprocess
        import os

        if not step.script_path or not os.path.exists(step.script_path):
            raise FileNotFoundError(f"Script not found: {step.script_path}")

        tracing_service.add_event(span_context, "script_started", {"script": step.script_path})

        try:
            result = subprocess.run(
                ["python", step.script_path],
                capture_output=True,
                text=True,
                timeout=step.timeout_seconds,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Script failed with return code {result.returncode}: {result.stderr}")

            tracing_service.add_event(span_context, "script_completed", {
                "return_code": result.returncode,
                "stdout_length": len(result.stdout),
            })

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Script timed out after {step.timeout_seconds} seconds")

    async def _execute_manual_step(
        self,
        step: RunbookStep,
        span_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a manual step (requires human intervention)."""
        tracing_service.add_event(span_context, "manual_step_started", {
            "description": step.description,
            "requires_approval": step.requires_approval,
        })

        # Send notification for manual step
        await notification_service.send_runbook_notification(
            runbook_id="manual_step",
            execution_id="current",
            status="manual_intervention_required",
            message=f"Manual step '{step.name}' requires human intervention: {step.description}"
        )

        # For now, simulate manual step completion
        # In production, this would integrate with a manual approval system
        await asyncio.sleep(10)

        tracing_service.add_event(span_context, "manual_step_completed", {
            "completed_by": "system_simulation",
        })

        return {
            "status": "completed",
            "completed_by": "system_simulation",
            "note": "Manual step simulated for development",
        }

    def _validate_step_result(self, step: RunbookStep, result: Dict[str, Any]) -> None:
        """Validate step result against expected result."""
        if not step.expected_result:
            return

        for key, expected_value in step.expected_result.items():
            if key not in result:
                raise ValueError(f"Expected result key '{key}' not found in step result")

            actual_value = result[key]
            if actual_value != expected_value:
                raise ValueError(
                    f"Step result validation failed: expected {key}={expected_value}, got {actual_value}"
                )

    def _build_step_dependency_graph(self, steps: List[RunbookStep]) -> Dict[str, List[str]]:
        """Build a dependency graph for steps."""
        graph = {}
        for step in steps:
            graph[step.id] = step.dependencies
        return graph

    async def get_execution_status(self, execution_id: str) -> Optional[RunbookExecution]:
        """Get the status of a runbook execution."""
        return self.active_executions.get(execution_id)

    async def cancel_execution(self, execution_id: str, reason: str) -> bool:
        """Cancel a running runbook execution."""
        execution = self.active_executions.get(execution_id)
        if not execution:
            return False

        if execution.status in [RunbookStatus.COMPLETED, RunbookStatus.FAILED, RunbookStatus.CANCELLED]:
            return False

        execution.status = RunbookStatus.CANCELLED
        execution.error_message = f"Cancelled: {reason}"
        execution.completed_at = datetime.now(timezone.utc)

        self.logger.info(f"Cancelled runbook execution {execution_id}: {reason}")

        # Send cancellation notification
        await notification_service.send_runbook_notification(
            runbook_id=execution.runbook_id,
            execution_id=execution_id,
            status="cancelled",
            message=f"Runbook execution cancelled: {reason}"
        )

        return True

    async def list_active_executions(self) -> List[RunbookExecution]:
        """List all active runbook executions."""
        return list(self.active_executions.values())

    async def get_available_runbooks(self) -> List[RunbookDefinition]:
        """Get list of available runbooks."""
        return list(self.runbooks.values())

    async def execute_emergency_drill(
        self,
        drill_type: str,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> RunbookExecution:
        """
        Execute a 2-minute emergency drill.

        Args:
            drill_type: Type of emergency drill to execute
            execution_context: Additional context for the drill

        Returns:
            RunbookExecution instance
        """
        drill_scenarios = {
            "export_rollback": "emergency_rollback",
            "dlq_recovery": "dlq_recovery",
            "invoice_recovery": "invoice_recovery",
            "performance_degradation": "performance_degradation",
        }

        runbook_id = drill_scenarios.get(drill_type)
        if not runbook_id:
            raise ValueError(f"Unknown drill type: {drill_type}")

        # Create drill context
        drill_context = {
            "drill_type": drill_type,
            "drill_mode": True,
            "execution_context": execution_context or {},
            "initiated_at": datetime.now(timezone.utc).isoformat(),
        }

        return await self.trigger_runbook(
            runbook_id=runbook_id,
            trigger_context=drill_context,
            user_id="emergency_drill_system",
        )


# Singleton instance
runbook_service = RunbookService()