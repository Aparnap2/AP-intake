"""
Comprehensive alert management service for multi-tier alerting and escalation workflows.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.tracing_service import tracing_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status values."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"


class NotificationChannel(str, Enum):
    """Notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"


@dataclass
class AlertRule:
    """Alert rule definition."""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    condition: str  # SQL-like condition
    threshold: float
    operator: str  # >, <, >=, <=, ==, !=
    evaluation_window_seconds: int
    consecutive_breaches: int
    notification_channels: List[NotificationChannel]
    escalation_policy: Optional[str] = None
    cooldown_period_seconds: int = 300
    enabled: bool = True
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert instance."""
    id: str
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    current_value: float
    threshold: float
    evaluated_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    last_notification_at: Optional[datetime] = None
    notification_count: int = 0
    escalation_level: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationPolicy:
    """Alert escalation policy."""
    id: str
    name: str
    description: str
    levels: List[Dict[str, Any]]  # List of escalation levels
    default_timeout_minutes: int = 30
    max_escalation_level: int = 3
    notification_channels: List[NotificationChannel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertService:
    """Comprehensive alert management service."""

    def __init__(self):
        """Initialize the alert service."""
        self.logger = logging.getLogger(__name__)
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_rules: Dict[str, AlertRule] = {}
        self.escalation_policies: Dict[str, EscalationPolicy] = {}
        self.suppression_rules: Dict[str, Dict[str, Any]] = {}
        self.alert_callbacks: Dict[str, List[Callable]] = {}
        self._load_default_alert_rules()
        self._load_default_escalation_policies()

    def _load_default_alert_rules(self) -> None:
        """Load default alert rules."""
        try:
            # SLO Breach Alert Rule
            slo_breach_rule = AlertRule(
                id="slo_breach",
                name="SLO Breach Alert",
                description="Alert when SLO achievement falls below threshold",
                severity=AlertSeverity.ERROR,
                condition="slo.achieved_percentage < slo.target_percentage",
                threshold=90.0,
                operator="<",
                evaluation_window_seconds=300,
                consecutive_breaches=1,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="slo_escalation",
                cooldown_period_seconds=900,
                tags={"category": "slo", "team": "platform"},
                metadata={"requires_immediate_attention": True}
            )

            # Error Budget Exhaustion Alert Rule
            error_budget_rule = AlertRule(
                id="error_budget_exhaustion",
                name="Error Budget Exhausted",
                description="Alert when error budget is completely exhausted",
                severity=AlertSeverity.CRITICAL,
                condition="slo.error_budget_consumed >= 100",
                threshold=100.0,
                operator=">=",
                evaluation_window_seconds=60,
                consecutive_breaches=1,
                notification_channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
                escalation_policy="critical_escalation",
                cooldown_period_seconds=300,
                tags={"category": "slo", "urgency": "critical"},
                metadata={"requires_immediate_response": True, "runbook_id": "emergency_rollback"}
            )

            # Processing Queue Size Alert Rule
            queue_size_rule = AlertRule(
                id="queue_size",
                name="Processing Queue Size",
                description="Alert when processing queue size exceeds threshold",
                severity=AlertSeverity.WARNING,
                condition="queue.size > threshold",
                threshold=1000.0,
                operator=">",
                evaluation_window_seconds=180,
                consecutive_breaches=2,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="performance_escalation",
                cooldown_period_seconds=600,
                tags={"category": "performance", "team": "infrastructure"},
                metadata={"component": "celery", "metric_type": "queue_size"}
            )

            # API Response Time Alert Rule
            api_response_time_rule = AlertRule(
                id="api_response_time",
                name="API Response Time",
                description="Alert when API response time exceeds threshold",
                severity=AlertSeverity.WARNING,
                condition="api.response_time_p95 > threshold",
                threshold=2000.0,  # 2 seconds
                operator=">",
                evaluation_window_seconds=300,
                consecutive_breaches=3,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="performance_escalation",
                cooldown_period_seconds=900,
                tags={"category": "performance", "team": "backend"},
                metadata={"endpoint_pattern": "/api/v1/*", "percentile": "p95"}
            )

            # Error Rate Alert Rule
            error_rate_rule = AlertRule(
                id="error_rate",
                name="Error Rate",
                description="Alert when error rate exceeds threshold",
                severity=AlertSeverity.ERROR,
                condition="error_rate > threshold",
                threshold=5.0,  # 5%
                operator=">",
                evaluation_window_seconds=300,
                consecutive_breaches=2,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="reliability_escalation",
                cooldown_period_seconds=600,
                tags={"category": "reliability", "team": "backend"},
                metadata={"metric_type": "http_error_rate", "threshold_percent": 5.0}
            )

            # Database Connection Pool Alert Rule
            db_connection_pool_rule = AlertRule(
                id="db_connection_pool",
                name="Database Connection Pool",
                description="Alert when database connection pool usage is high",
                severity=AlertSeverity.WARNING,
                condition="db.pool_utilization > threshold",
                threshold=80.0,  # 80%
                operator=">",
                evaluation_window_seconds=120,
                consecutive_breaches=2,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="infrastructure_escalation",
                cooldown_period_seconds=900,
                tags={"category": "infrastructure", "team": "database"},
                metadata={"pool_name": "default", "warning_threshold": 80.0, "critical_threshold": 95.0}
            )

            # Disk Space Alert Rule
            disk_space_rule = AlertRule(
                id="disk_space",
                name="Disk Space",
                description="Alert when disk space usage is high",
                severity=AlertSeverity.ERROR,
                condition="disk.usage_percent > threshold",
                threshold=85.0,  # 85%
                operator=">",
                evaluation_window_seconds=300,
                consecutive_breaches=1,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="infrastructure_escalation",
                cooldown_period_seconds=1800,
                tags={"category": "infrastructure", "team": "ops"},
                metadata={"mount_point": "/", "critical_threshold": 95.0}
            )

            # Invoice Processing Failure Rate Alert Rule
            invoice_failure_rate_rule = AlertRule(
                id="invoice_failure_rate",
                name="Invoice Processing Failure Rate",
                description="Alert when invoice processing failure rate is high",
                severity=AlertSeverity.ERROR,
                condition="invoice.failure_rate > threshold",
                threshold=10.0,  # 10%
                operator=">",
                evaluation_window_seconds=600,
                consecutive_breaches=1,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="business_escalation",
                cooldown_period_seconds=1200,
                tags={"category": "business", "team": "ap_operations"},
                metadata={"business_impact": "high", "runbook_id": "invoice_recovery"}
            )

            # DLQ Size Alert Rule
            dlq_size_rule = AlertRule(
                id="dlq_size",
                name="Dead Letter Queue Size",
                description="Alert when DLQ size exceeds threshold",
                severity=AlertSeverity.ERROR,
                condition="dlq.size > threshold",
                threshold=100.0,
                operator=">",
                evaluation_window_seconds=180,
                consecutive_breaches=1,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_policy="reliability_escalation",
                cooldown_period_seconds=600,
                tags={"category": "reliability", "team": "backend"},
                metadata={"queue_type": "celery", "runbook_id": "dlq_recovery"}
            )

            # Extraction Confidence Alert Rule
            extraction_confidence_rule = AlertRule(
                id="extraction_confidence",
                name="Low Extraction Confidence",
                description="Alert when document extraction confidence is consistently low",
                severity=AlertSeverity.WARNING,
                condition="extraction.avg_confidence < threshold",
                threshold=0.75,  # 75%
                operator="<",
                evaluation_window_seconds=1800,  # 30 minutes
                consecutive_breaches=3,
                notification_channels=[NotificationChannel.EMAIL],
                escalation_policy="ml_escalation",
                cooldown_period_seconds=3600,
                tags={"category": "ml", "team": "data_science"},
                metadata={"model_name": "docling", "min_sample_size": 50}
            )

            # Register all rules
            self.alert_rules.update({
                "slo_breach": slo_breach_rule,
                "error_budget_exhaustion": error_budget_rule,
                "queue_size": queue_size_rule,
                "api_response_time": api_response_time_rule,
                "error_rate": error_rate_rule,
                "db_connection_pool": db_connection_pool_rule,
                "disk_space": disk_space_rule,
                "invoice_failure_rate": invoice_failure_rate_rule,
                "dlq_size": dlq_size_rule,
                "extraction_confidence": extraction_confidence_rule,
            })

            self.logger.info(f"Loaded {len(self.alert_rules)} default alert rules")

        except Exception as e:
            self.logger.error(f"Failed to load default alert rules: {e}")
            raise

    def _load_default_escalation_policies(self) -> None:
        """Load default escalation policies."""
        try:
            # Critical Escalation Policy
            critical_escalation = EscalationPolicy(
                id="critical_escalation",
                name="Critical Alert Escalation",
                description="Escalation policy for critical alerts",
                levels=[
                    {
                        "level": 1,
                        "timeout_minutes": 5,
                        "channels": [NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
                        "recipients": ["oncall_engineer"],
                        "message": "CRITICAL: Immediate response required"
                    },
                    {
                        "level": 2,
                        "timeout_minutes": 10,
                        "channels": [NotificationChannel.PAGERDUTY, NotificationChannel.SMS, NotificationChannel.SLACK],
                        "recipients": ["oncall_engineer", "tech_lead"],
                        "message": "CRITICAL: Alert escalated to tech lead"
                    },
                    {
                        "level": 3,
                        "timeout_minutes": 15,
                        "channels": [NotificationChannel.PAGERDUTY, NotificationChannel.SMS, NotificationChannel.EMAIL],
                        "recipients": ["oncall_engineer", "tech_lead", "engineering_manager"],
                        "message": "CRITICAL: Alert escalated to engineering manager"
                    }
                ],
                default_timeout_minutes=30,
                max_escalation_level=3,
                notification_channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
                metadata={"urgency": "critical", "auto_runbook": True}
            )

            # SLO Escalation Policy
            slo_escalation = EscalationPolicy(
                id="slo_escalation",
                name="SLO Alert Escalation",
                description="Escalation policy for SLO-related alerts",
                levels=[
                    {
                        "level": 1,
                        "timeout_minutes": 15,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
                        "recipients": ["sre_team", "product_team"],
                        "message": "SLO breach detected - investigation required"
                    },
                    {
                        "level": 2,
                        "timeout_minutes": 30,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
                        "recipients": ["sre_team", "product_team", "engineering_manager"],
                        "message": "SLO breach persisted - escalation initiated"
                    },
                    {
                        "level": 3,
                        "timeout_minutes": 60,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
                        "recipients": ["sre_team", "product_team", "engineering_manager", "vp_engineering"],
                        "message": "SLO breach critical - leadership notification"
                    }
                ],
                default_timeout_minutes=60,
                max_escalation_level=3,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                metadata={"category": "slo", "requires_sre_response": True}
            )

            # Performance Escalation Policy
            performance_escalation = EscalationPolicy(
                id="performance_escalation",
                name="Performance Alert Escalation",
                description="Escalation policy for performance-related alerts",
                levels=[
                    {
                        "level": 1,
                        "timeout_minutes": 20,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
                        "recipients": ["performance_team", "infrastructure_team"],
                        "message": "Performance degradation detected"
                    },
                    {
                        "level": 2,
                        "timeout_minutes": 45,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
                        "recipients": ["performance_team", "infrastructure_team", "tech_lead"],
                        "message": "Performance issues persisting - escalation"
                    }
                ],
                default_timeout_minutes=45,
                max_escalation_level=2,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                metadata={"category": "performance", "auto_scaling": True}
            )

            # Business Escalation Policy
            business_escalation = EscalationPolicy(
                id="business_escalation",
                name="Business Impact Escalation",
                description="Escalation policy for business-impacting alerts",
                levels=[
                    {
                        "level": 1,
                        "timeout_minutes": 10,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
                        "recipients": ["ap_operations_team", "product_manager"],
                        message="Business process impact detected"
                    },
                    {
                        "level": 2,
                        "timeout_minutes": 25,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.TEAMS],
                        "recipients": ["ap_operations_team", "product_manager", "business_operations"],
                        "message": "Business impact escalating - leadership notification"
                    },
                    {
                        "level": 3,
                        "timeout_minutes": 45,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.TEAMS],
                        "recipients": ["ap_operations_team", "product_manager", "business_operations", "vp_operations"],
                        "message": "Critical business impact - executive notification"
                    }
                ],
                default_timeout_minutes=45,
                max_escalation_level=3,
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.TEAMS],
                metadata={"category": "business", "revenue_impact": True}
            )

            # Register all policies
            self.escalation_policies.update({
                "critical_escalation": critical_escalation,
                "slo_escalation": slo_escalation,
                "performance_escalation": performance_escalation,
                "business_escalation": business_escalation,
            })

            self.logger.info(f"Loaded {len(self.escalation_policies)} default escalation policies")

        except Exception as e:
            self.logger.error(f"Failed to load default escalation policies: {e}")
            raise

    async def evaluate_metric(
        self,
        metric_name: str,
        current_value: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Alert]:
        """
        Evaluate a metric against all applicable alert rules.

        Args:
            metric_name: Name of the metric being evaluated
            current_value: Current value of the metric
            context: Additional context for the evaluation

        Returns:
            List of triggered alerts
        """
        triggered_alerts = []

        try:
            # Find applicable rules
            applicable_rules = [
                rule for rule in self.alert_rules.values()
                if rule.enabled and self._is_rule_applicable(rule, metric_name, context)
            ]

            for rule in applicable_rules:
                # Check if alert condition is met
                if self._evaluate_condition(rule, current_value, context):
                    # Check for existing alert
                    existing_alert = self._find_existing_alert(rule.id, context)

                    if existing_alert:
                        # Update existing alert
                        await self._update_existing_alert(existing_alert, current_value, context)
                        triggered_alerts.append(existing_alert)
                    else:
                        # Create new alert
                        new_alert = await self._create_alert(rule, current_value, context)
                        if new_alert:
                            triggered_alerts.append(new_alert)
                else:
                    # Check if we should resolve any existing alerts
                    await self._resolve_alerts_for_rule(rule.id, context)

            return triggered_alerts

        except Exception as e:
            self.logger.error(f"Failed to evaluate metric {metric_name}: {e}")
            return []

    def _is_rule_applicable(
        self,
        rule: AlertRule,
        metric_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if an alert rule is applicable to the given metric."""
        try:
            # Check if rule condition matches metric
            if metric_name not in rule.condition:
                return False

            # Check if rule is suppressed
            if self._is_rule_suppressed(rule.id, context):
                return False

            # Check cooldown period
            if self._is_rule_in_cooldown(rule.id):
                return False

            # Check context-based applicability
            if context:
                # Check tags match
                if rule.tags:
                    for tag_key, tag_value in rule.tags.items():
                        if context.get(f"tag_{tag_key}") != tag_value:
                            return False

            return True

        except Exception as e:
            self.logger.error(f"Failed to check rule applicability: {e}")
            return False

    def _evaluate_condition(
        self,
        rule: AlertRule,
        current_value: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluate alert rule condition."""
        try:
            # Simple threshold evaluation
            if rule.operator == ">":
                return current_value > rule.threshold
            elif rule.operator == "<":
                return current_value < rule.threshold
            elif rule.operator == ">=":
                return current_value >= rule.threshold
            elif rule.operator == "<=":
                return current_value <= rule.threshold
            elif rule.operator == "==":
                return current_value == rule.threshold
            elif rule.operator == "!=":
                return current_value != rule.threshold
            else:
                self.logger.warning(f"Unknown operator: {rule.operator}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to evaluate condition: {e}")
            return False

    def _find_existing_alert(
        self,
        rule_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """Find existing active alert for the rule and context."""
        for alert in self.active_alerts.values():
            if (alert.rule_id == rule_id and
                alert.status == AlertStatus.ACTIVE and
                self._contexts_match(alert.context, context)):
                return alert
        return None

    def _contexts_match(
        self,
        alert_context: Dict[str, Any],
        new_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if alert contexts match for alert deduplication."""
        if not new_context:
            return True

        # Define which context keys are important for deduplication
        dedup_keys = ["resource_id", "workflow_id", "invoice_id", "component"]

        for key in dedup_keys:
            if alert_context.get(key) != new_context.get(key):
                return False

        return True

    async def _update_existing_alert(
        self,
        alert: Alert,
        current_value: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update an existing alert with new data."""
        try:
            alert.current_value = current_value
            alert.evaluated_at = datetime.now(timezone.utc)
            alert.context.update(context or {})

            # Check if we need to escalate
            await self._check_escalation(alert)

            self.logger.debug(f"Updated existing alert {alert.id}")

        except Exception as e:
            self.logger.error(f"Failed to update existing alert {alert.id}: {e}")

    async def _create_alert(
        self,
        rule: AlertRule,
        current_value: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """Create a new alert."""
        try:
            alert_id = str(uuid4())
            alert = Alert(
                id=alert_id,
                rule_id=rule.id,
                name=rule.name,
                description=rule.description,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                current_value=current_value,
                threshold=rule.threshold,
                evaluated_at=datetime.now(timezone.utc),
                context=context or {},
                metadata=rule.metadata.copy(),
            )

            # Store alert
            self.active_alerts[alert_id] = alert

            # Send initial notification
            await self._send_alert_notification(alert, rule)

            # Start escalation timer if policy exists
            if rule.escalation_policy:
                await self._start_escalation_timer(alert, rule)

            self.logger.info(f"Created new alert {alert_id} for rule {rule.name}")

            return alert

        except Exception as e:
            self.logger.error(f"Failed to create alert: {e}")
            return None

    async def _send_alert_notification(
        self,
        alert: Alert,
        rule: AlertRule,
        escalation_level: int = 0,
    ) -> None:
        """Send alert notification through configured channels."""
        try:
            # Check cooldown for notifications
            if alert.last_notification_at:
                time_since_last = datetime.now(timezone.utc) - alert.last_notification_at
                if time_since_last.total_seconds() < rule.cooldown_period_seconds:
                    return

            # Prepare notification message
            message = self._prepare_notification_message(alert, rule, escalation_level)

            # Send through each channel
            for channel in rule.notification_channels:
                try:
                    await notification_service.send_alert_notification(
                        channel=channel,
                        alert_id=alert.id,
                        severity=alert.severity,
                        message=message,
                        context={
                            "alert": alert,
                            "rule": rule,
                            "escalation_level": escalation_level,
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Failed to send alert notification via {channel}: {e}")

            # Update notification tracking
            alert.last_notification_at = datetime.now(timezone.utc)
            alert.notification_count += 1

            # Create tracing event
            tracing_service.add_event(
                {"trace_id": alert.id},
                "alert_notification_sent",
                {
                    "channel_count": len(rule.notification_channels),
                    "escalation_level": escalation_level,
                    "notification_count": alert.notification_count,
                }
            )

        except Exception as e:
            self.logger.error(f"Failed to send alert notification for {alert.id}: {e}")

    def _prepare_notification_message(
        self,
        alert: Alert,
        rule: AlertRule,
        escalation_level: int = 0,
    ) -> str:
        """Prepare alert notification message."""
        severity_emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨",
        }

        emoji = severity_emoji.get(alert.severity, "⚠️")
        escalation_text = f" [Escalation Level {escalation_level}]" if escalation_level > 0 else ""

        message = f"""
{emoji} {alert.name}{escalation_text}

Description: {alert.description}
Current Value: {alert.current_value}
Threshold: {alert.threshold}
Evaluated At: {alert.evaluated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
"""

        # Add context information
        if alert.context:
            message += "\nContext:\n"
            for key, value in alert.context.items():
                if key != "metadata":
                    message += f"  {key}: {value}\n"

        # Add suggested actions if available
        suggested_actions = alert.metadata.get("suggested_actions")
        if suggested_actions:
            message += "\nSuggested Actions:\n"
            for action in suggested_actions:
                message += f"  • {action}\n"

        # Add runbook if available
        runbook_id = alert.metadata.get("runbook_id")
        if runbook_id:
            message += f"\nRunbook: {runbook_id}\n"

        return message

    async def _start_escalation_timer(
        self,
        alert: Alert,
        rule: AlertRule,
    ) -> None:
        """Start escalation timer for the alert."""
        try:
            escalation_policy = self.escalation_policies.get(rule.escalation_policy)
            if not escalation_policy:
                return

            if alert.escalation_level >= escalation_policy.max_escalation_level:
                return

            # Get current escalation level timeout
            current_level_config = None
            for level_config in escalation_policy.levels:
                if level_config["level"] == alert.escalation_level + 1:
                    current_level_config = level_config
                    break

            if not current_level_config:
                return

            # Schedule escalation
            timeout_seconds = current_level_config["timeout_minutes"] * 60
            asyncio.create_task(
                self._escalate_alert_after_timeout(alert, escalation_policy, timeout_seconds)
            )

        except Exception as e:
            self.logger.error(f"Failed to start escalation timer for alert {alert.id}: {e}")

    async def _escalate_alert_after_timeout(
        self,
        alert: Alert,
        escalation_policy: EscalationPolicy,
        timeout_seconds: int,
    ) -> None:
        """Escalate alert after timeout."""
        try:
            await asyncio.sleep(timeout_seconds)

            # Check if alert is still active and not acknowledged
            if (alert.id not in self.active_alerts or
                alert.status != AlertStatus.ACTIVE or
                alert.acknowledged_at):
                return

            # Escalate the alert
            await self._escalate_alert(alert, escalation_policy)

        except Exception as e:
            self.logger.error(f"Failed to escalate alert {alert.id}: {e}")

    async def _escalate_alert(
        self,
        alert: Alert,
        escalation_policy: EscalationPolicy,
    ) -> None:
        """Escalate alert to next level."""
        try:
            alert.escalation_level += 1
            alert.status = AlertStatus.ESCALATED

            # Get escalation level config
            current_level_config = None
            for level_config in escalation_policy.levels:
                if level_config["level"] == alert.escalation_level:
                    current_level_config = level_config
                    break

            if not current_level_config:
                self.logger.warning(f"No escalation config found for level {alert.escalation_level}")
                return

            # Send escalation notification
            rule = self.alert_rules.get(alert.rule_id)
            if rule:
                await self._send_alert_notification(alert, rule, alert.escalation_level)

            # Schedule next escalation if not at max level
            if alert.escalation_level < escalation_policy.max_escalation_level:
                timeout_seconds = current_level_config["timeout_minutes"] * 60
                asyncio.create_task(
                    self._escalate_alert_after_timeout(alert, escalation_policy, timeout_seconds)
                )

            self.logger.info(f"Escalated alert {alert.id} to level {alert.escalation_level}")

        except Exception as e:
            self.logger.error(f"Failed to escalate alert {alert.id}: {e}")

    async def _check_escalation(self, alert: Alert) -> None:
        """Check if alert should be escalated based on duration or other criteria."""
        try:
            # Check if alert has been active for too long without acknowledgment
            if not alert.acknowledged_at:
                active_duration = datetime.now(timezone.utc) - alert.evaluated_at
                if active_duration.total_seconds() > 3600:  # 1 hour
                    rule = self.alert_rules.get(alert.rule_id)
                    if rule and rule.escalation_policy:
                        escalation_policy = self.escalation_policies.get(rule.escalation_policy)
                        if escalation_policy:
                            await self._escalate_alert(alert, escalation_policy)

        except Exception as e:
            self.logger.error(f"Failed to check escalation for alert {alert.id}: {e}")

    async def _resolve_alerts_for_rule(
        self,
        rule_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Resolve active alerts for a rule when condition is no longer met."""
        try:
            alerts_to_resolve = [
                alert for alert in self.active_alerts.values()
                if (alert.rule_id == rule_id and
                    alert.status == AlertStatus.ACTIVE and
                    self._contexts_match(alert.context, context))
            ]

            for alert in alerts_to_resolve:
                await self.resolve_alert(alert.id, "Condition no longer met", "system")

        except Exception as e:
            self.logger.error(f"Failed to resolve alerts for rule {rule_id}: {e}")

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
        note: Optional[str] = None,
    ) -> bool:
        """Acknowledge an alert."""
        try:
            alert = self.active_alerts.get(alert_id)
            if not alert:
                return False

            if alert.status not in [AlertStatus.ACTIVE, AlertStatus.ESCALATED]:
                return False

            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by

            if note:
                alert.metadata["acknowledgment_note"] = note

            # Send acknowledgment notification
            rule = self.alert_rules.get(alert.rule_id)
            if rule:
                await notification_service.send_alert_notification(
                    channel=NotificationChannel.SLACK,
                    alert_id=alert_id,
                    severity=alert.severity,
                    message=f"Alert '{alert.name}' acknowledged by {acknowledged_by}",
                    context={"alert": alert, "acknowledged_by": acknowledged_by}
                )

            self.logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False

    async def resolve_alert(
        self,
        alert_id: str,
        resolution_note: str,
        resolved_by: str,
    ) -> bool:
        """Resolve an alert."""
        try:
            alert = self.active_alerts.get(alert_id)
            if not alert:
                return False

            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolved_by = resolved_by
            alert.metadata["resolution_note"] = resolution_note

            # Send resolution notification
            rule = self.alert_rules.get(alert.rule_id)
            if rule:
                await notification_service.send_alert_notification(
                    channel=NotificationChannel.SLACK,
                    alert_id=alert_id,
                    severity=alert.severity,
                    message=f"Alert '{alert.name}' resolved by {resolved_by}: {resolution_note}",
                    context={"alert": alert, "resolved_by": resolved_by}
                )

            self.logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False

    async def suppress_alerts(
        self,
        rule_id: str,
        suppression_duration_minutes: int,
        reason: str,
        suppressed_by: str,
    ) -> bool:
        """Suppress alerts for a rule for a specified duration."""
        try:
            suppression_id = str(uuid4())
            self.suppression_rules[suppression_id] = {
                "rule_id": rule_id,
                "suppressed_at": datetime.now(timezone.utc),
                "duration_minutes": suppression_duration_minutes,
                "reason": reason,
                "suppressed_by": suppressed_by,
            }

            # Schedule suppression removal
            asyncio.create_task(
                self._remove_suppression_after_duration(suppression_id, suppression_duration_minutes * 60)
            )

            self.logger.info(f"Alerts for rule {rule_id} suppressed for {suppression_duration_minutes} minutes by {suppressed_by}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to suppress alerts for rule {rule_id}: {e}")
            return False

    async def _remove_suppression_after_duration(
        self,
        suppression_id: str,
        duration_seconds: int,
    ) -> None:
        """Remove alert suppression after duration."""
        try:
            await asyncio.sleep(duration_seconds)
            if suppression_id in self.suppression_rules:
                del self.suppression_rules[suppression_id]
                self.logger.info(f"Alert suppression {suppression_id} removed")

        except Exception as e:
            self.logger.error(f"Failed to remove suppression {suppression_id}: {e}")

    def _is_rule_suppressed(
        self,
        rule_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if a rule is currently suppressed."""
        for suppression in self.suppression_rules.values():
            if suppression["rule_id"] == rule_id:
                # Check if suppression is still active
                elapsed = datetime.now(timezone.utc) - suppression["suppressed_at"]
                if elapsed.total_seconds() < suppression["duration_minutes"] * 60:
                    return True
        return False

    def _is_rule_in_cooldown(self, rule_id: str) -> bool:
        """Check if a rule is in cooldown period."""
        # This would check the last alert creation time for the rule
        # For now, return False
        return False

    async def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        status: Optional[AlertStatus] = None,
    ) -> List[Alert]:
        """Get active alerts with optional filtering."""
        alerts = list(self.active_alerts.values())

        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]

        if status:
            alerts = [alert for alert in alerts if alert.status == status]

        return alerts

    async def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of active alerts."""
        alerts = list(self.active_alerts.values())

        summary = {
            "total_active": len([a for a in alerts if a.status == AlertStatus.ACTIVE]),
            "total_acknowledged": len([a for a in alerts if a.status == AlertStatus.ACKNOWLEDGED]),
            "total_escalated": len([a for a in alerts if a.status == AlertStatus.ESCALATED]),
            "severity_breakdown": {},
            "recent_alerts": [],
        }

        # Severity breakdown
        for severity in AlertSeverity:
            count = len([a for a in alerts if a.severity == severity and a.status in [AlertStatus.ACTIVE, AlertStatus.ESCALATED]])
            summary["severity_breakdown"][severity.value] = count

        # Recent alerts (last 10)
        recent_alerts = sorted(alerts, key=lambda a: a.evaluated_at, reverse=True)[:10]
        summary["recent_alerts"] = [
            {
                "id": alert.id,
                "name": alert.name,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "evaluated_at": alert.evaluated_at.isoformat(),
                "current_value": alert.current_value,
                "threshold": alert.threshold,
            }
            for alert in recent_alerts
        ]

        return summary

    async def create_custom_alert(
        self,
        name: str,
        description: str,
        severity: AlertSeverity,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        """Create a custom alert not tied to a rule."""
        try:
            alert_id = str(uuid4())
            alert = Alert(
                id=alert_id,
                rule_id="custom",
                name=name,
                description=description,
                severity=severity,
                status=AlertStatus.ACTIVE,
                current_value=0.0,
                threshold=0.0,
                evaluated_at=datetime.now(timezone.utc),
                context=context,
                metadata=metadata or {},
            )

            # Store alert
            self.active_alerts[alert_id] = alert

            # Send notification
            await notification_service.send_alert_notification(
                channel=NotificationChannel.EMAIL,
                alert_id=alert_id,
                severity=alert.severity,
                message=f"Custom Alert: {name}\n\n{description}",
                context={"alert": alert, "custom_alert": True}
            )

            self.logger.info(f"Created custom alert {alert_id}: {name}")
            return alert

        except Exception as e:
            self.logger.error(f"Failed to create custom alert: {e}")
            raise


# Singleton instance
alert_service = AlertService()