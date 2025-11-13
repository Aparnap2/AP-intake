"""
Comprehensive audit logging service for policy decisions and authorization events.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.select import select, and_, or_, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.rbac import PolicyAuditLog
from app.models.approval_models import ApprovalAuditLog
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuditEventType:
    """Audit event types for categorization."""

    # Authentication events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"

    # Authorization events
    PERMISSION_CHECK = "permission_check"
    ROLE_ASSIGNMENT = "role_assignment"
    ROLE_REVOCATION = "role_revocation"
    ACCESS_DENIED = "access_denied"
    ACCESS_GRANTED = "access_granted"

    # Policy evaluation events
    POLICY_EVALUATION = "policy_evaluation"
    POLICY_EVALUATION_COMPLETE = "policy_evaluation_complete"
    POLICY_EVALUATION_ERROR = "policy_evaluation_error"
    POLICY_GATE_TRIGGERED = "policy_gate_triggered"
    POLICY_DECISION = "policy_decision"

    # Approval workflow events
    APPROVAL_REQUEST_CREATED = "approval_request_created"
    APPROVAL_DECISION = "approval_decision"
    APPROVAL_ESCALATED = "approval_escalated"
    APPROVAL_COMPLETED = "approval_completed"
    APPROVAL_DELEGATED = "approval_delegated"

    # System events
    SYSTEM_INITIALIZATION = "system_initialization"
    CONFIGURATION_CHANGE = "configuration_change"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    SECURITY_ALERT = "security_alert"

    # Data events
    DATA_CREATED = "data_created"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    DATA_ACCESSED = "data_accessed"


class AuditSeverity:
    """Audit event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditContext:
    """Context information for audit events."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.correlation_id = correlation_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.request_id = request_id
        self.additional_data = additional_data or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            **self.additional_data
        }


class AuditEvent:
    """Audit event representation."""

    def __init__(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        severity: str = AuditSeverity.MEDIUM,
        context: Optional[AuditContext] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        decision: Optional[str] = None,
        decision_reason: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        self.event_type = event_type
        self.event_data = event_data
        self.severity = severity
        self.context = context or AuditContext()
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.decision = decision
        self.decision_reason = decision_reason
        self.tags = tags or []
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type,
            "event_data": self.event_data,
            "severity": self.severity,
            "context": self.context.to_dict(),
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat()
        }


class AuditService:
    """Comprehensive audit logging service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def log_event(self, event: AuditEvent) -> bool:
        """
        Log an audit event.

        Args:
            event: The audit event to log

        Returns:
            True if successful, False otherwise
        """
        try:
            # Log to application logger
            log_level = self._get_log_level(event.severity)
            self.logger.log(
                log_level,
                f"Audit Event: {event.event_type} - {event.decision or 'No decision'}",
                extra={
                    "audit_event": event.to_dict(),
                    "event_type": event.event_type,
                    "user_id": event.context.user_id,
                    "severity": event.severity
                }
            )

            # Store in database
            await self._store_audit_event(event)

            # Send to external systems if configured
            if settings.AUDIT_EXTERNAL_ENABLED:
                await self._send_to_external_systems(event)

            return True

        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")
            return False

    async def log_authentication_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[AuditContext] = None
    ):
        """Log authentication-related events."""
        severity = AuditSeverity.MEDIUM if success else AuditSeverity.HIGH

        event_data = {
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {})
        }

        if not success:
            event_data["failure_reason"] = details.get("reason", "Unknown") if details else "Unknown"

        event = AuditEvent(
            event_type=event_type,
            event_data=event_data,
            severity=severity,
            context=context,
            resource_type="user",
            resource_id=user_id,
            decision="granted" if success else "denied",
            tags=["authentication"]
        )

        await self.log_event(event)

    async def log_authorization_event(
        self,
        event_type: str,
        user_id: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        granted: bool = True,
        reason: Optional[str] = None,
        context: Optional[AuditContext] = None
    ):
        """Log authorization-related events."""
        severity = AuditSeverity.LOW if granted else AuditSeverity.MEDIUM

        event_data = {
            "action": action,
            "granted": granted,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if reason:
            event_data["reason"] = reason

        event = AuditEvent(
            event_type=event_type,
            event_data=event_data,
            severity=severity,
            context=context,
            resource_type=resource_type,
            resource_id=resource_id,
            decision="granted" if granted else "denied",
            decision_reason=reason,
            tags=["authorization"]
        )

        await self.log_event(event)

    async def log_policy_event(
        self,
        event_type: str,
        policy_gate_id: Optional[str] = None,
        invoice_id: Optional[str] = None,
        decision: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[AuditContext] = None
    ):
        """Log policy evaluation events."""
        severity = AuditSeverity.MEDIUM

        # Determine severity based on decision
        if decision == "blocked":
            severity = AuditSeverity.HIGH
        elif decision == "requires_approval":
            severity = AuditSeverity.MEDIUM
        elif decision == "allowed":
            severity = AuditSeverity.LOW

        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {})
        }

        event = AuditEvent(
            event_type=event_type,
            event_data=event_data,
            severity=severity,
            context=context,
            resource_type="policy",
            resource_id=policy_gate_id,
            decision=decision,
            tags=["policy", "evaluation"]
        )

        # Store in policy audit log table
        await self._store_policy_audit_event(event, policy_gate_id, invoice_id)

        # Also log to general audit
        await self.log_event(event)

    async def log_approval_event(
        self,
        event_type: str,
        approval_request_id: str,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[AuditContext] = None
    ):
        """Log approval workflow events."""
        severity = AuditSeverity.MEDIUM

        event_data = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {})
        }

        event = AuditEvent(
            event_type=event_type,
            event_data=event_data,
            severity=severity,
            context=context,
            resource_type="approval",
            resource_id=approval_request_id,
            decision=action,
            tags=["approval", "workflow"]
        )

        # Store in approval audit log table
        await self._store_approval_audit_event(event, approval_request_id)

        # Also log to general audit
        await self.log_event(event)

    async def log_security_event(
        self,
        event_type: str,
        severity: str = AuditSeverity.HIGH,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[AuditContext] = None
    ):
        """Log security-related events."""
        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {})
        }

        event = AuditEvent(
            event_type=event_type,
            event_data=event_data,
            severity=severity,
            context=context,
            resource_type="system",
            decision="security_alert",
            tags=["security"]
        )

        await self.log_event(event)

    async def get_audit_events(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit events with filtering."""
        try:
            # Query policy audit logs
            policy_events = await self._get_policy_audit_events(
                event_type, user_id, resource_type, resource_id,
                severity, start_date, end_date, limit, offset
            )

            # Query approval audit logs
            approval_events = await self._get_approval_audit_events(
                event_type, user_id, resource_type, resource_id,
                severity, start_date, end_date, limit, offset
            )

            # Combine and sort by timestamp
            all_events = policy_events + approval_events
            all_events.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)

            # Apply pagination
            return all_events[offset:offset + limit]

        except Exception as e:
            self.logger.error(f"Failed to get audit events: {e}")
            return []

    async def get_audit_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get audit statistics for the specified period."""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get policy statistics
            policy_stats = await self._get_policy_audit_statistics(start_date)

            # Get approval statistics
            approval_stats = await self._get_approval_audit_statistics(start_date)

            return {
                "period_days": days,
                "start_date": start_date.isoformat(),
                "policy_events": policy_stats,
                "approval_events": approval_stats,
                "total_events": policy_stats.get("total_events", 0) + approval_stats.get("total_events", 0)
            }

        except Exception as e:
            self.logger.error(f"Failed to get audit statistics: {e}")
            return {}

    def _get_log_level(self, severity: str) -> int:
        """Convert severity to logging level."""
        severity_levels = {
            AuditSeverity.LOW: logging.INFO,
            AuditSeverity.MEDIUM: logging.WARNING,
            AuditSeverity.HIGH: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL
        }
        return severity_levels.get(severity, logging.INFO)

    async def _store_audit_event(self, event: AuditEvent):
        """Store audit event in database (general audit log)."""
        # This would store in a general audit log table
        # For now, we're using specific policy and approval audit tables
        pass

    async def _store_policy_audit_event(
        self,
        event: AuditEvent,
        policy_gate_id: Optional[str],
        invoice_id: Optional[str]
    ):
        """Store policy audit event in database."""
        try:
            audit_log = PolicyAuditLog(
                gate_id=policy_gate_id,
                invoice_id=invoice_id,
                event_type=event.event_type,
                event_data=event.event_data,
                decision=event.decision,
                decision_reason=event.decision_reason,
                user_id=event.context.user_id,
                user_agent=event.context.user_agent,
                ip_address=event.context.ip_address,
                session_id=event.context.session_id,
                correlation_id=event.context.correlation_id
            )

            self.db.add(audit_log)
            await self.db.commit()

        except Exception as e:
            self.logger.error(f"Failed to store policy audit event: {e}")
            await self.db.rollback()

    async def _store_approval_audit_event(
        self,
        event: AuditEvent,
        approval_request_id: str
    ):
        """Store approval audit event in database."""
        try:
            audit_log = ApprovalAuditLog(
                approval_request_id=approval_request_id,
                event_type=event.event_type,
                event_data=event.event_data,
                user_id=event.context.user_id,
                user_agent=event.context.user_agent,
                ip_address=event.context.ip_address,
                session_id=event.context.session_id,
                correlation_id=event.context.correlation_id
            )

            self.db.add(audit_log)
            await self.db.commit()

        except Exception as e:
            self.logger.error(f"Failed to store approval audit event: {e}")
            await self.db.rollback()

    async def _send_to_external_systems(self, event: AuditEvent):
        """Send audit event to external monitoring systems."""
        try:
            # This would integrate with systems like:
            # - SIEM systems (Splunk, ELK)
            # - Security monitoring tools
            # - Compliance platforms
            # - External audit logs

            if settings.AUDIT_WEBHOOK_URL:
                # Send to webhook
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(
                        settings.AUDIT_WEBHOOK_URL,
                        json=event.to_dict(),
                        timeout=10.0
                    )

            # Could also send to message queues, cloud logging, etc.

        except Exception as e:
            self.logger.error(f"Failed to send audit event to external systems: {e}")

    async def _get_policy_audit_events(
        self,
        event_type: Optional[str],
        user_id: Optional[str],
        resource_type: Optional[str],
        resource_id: Optional[str],
        severity: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        """Get policy audit events."""
        stmt = select(PolicyAuditLog)

        # Apply filters
        if event_type:
            stmt = stmt.where(PolicyAuditLog.event_type == event_type)
        if user_id:
            stmt = stmt.where(PolicyAuditLog.user_id == user_id)
        if resource_id:
            stmt = stmt.where(PolicyAuditLog.gate_id == resource_id)
        if start_date:
            stmt = stmt.where(PolicyAuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(PolicyAuditLog.created_at <= end_date)

        # Order and paginate
        stmt = stmt.order_by(PolicyAuditLog.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "event_data": event.event_data,
                "decision": event.decision,
                "decision_reason": event.decision_reason,
                "user_id": event.user_id,
                "ip_address": event.ip_address,
                "created_at": event.created_at,
                "source": "policy"
            }
            for event in events
        ]

    async def _get_approval_audit_events(
        self,
        event_type: Optional[str],
        user_id: Optional[str],
        resource_type: Optional[str],
        resource_id: Optional[str],
        severity: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        """Get approval audit events."""
        stmt = select(ApprovalAuditLog)

        # Apply filters
        if event_type:
            stmt = stmt.where(ApprovalAuditLog.event_type == event_type)
        if user_id:
            stmt = stmt.where(ApprovalAuditLog.user_id == user_id)
        if resource_id:
            stmt = stmt.where(ApprovalAuditLog.approval_request_id == resource_id)
        if start_date:
            stmt = stmt.where(ApprovalAuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ApprovalAuditLog.created_at <= end_date)

        # Order and paginate
        stmt = stmt.order_by(ApprovalAuditLog.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "event_data": event.event_data,
                "user_id": event.user_id,
                "ip_address": event.ip_address,
                "created_at": event.created_at,
                "source": "approval"
            }
            for event in events
        ]

    async def _get_policy_audit_statistics(self, start_date: datetime) -> Dict[str, Any]:
        """Get policy audit statistics."""
        stmt = select(
            func.count(PolicyAuditLog.id).label('total_events'),
            func.count(func.distinct(PolicyAuditLog.user_id)).label('unique_users'),
            func.count(func.distinct(PolicyAuditLog.gate_id)).label('unique_gates')
        ).where(PolicyAuditLog.created_at >= start_date)

        result = await self.db.execute(stmt)
        stats = result.first()

        return {
            "total_events": stats.total_events or 0,
            "unique_users": stats.unique_users or 0,
            "unique_gates": stats.unique_gates or 0
        }

    async def _get_approval_audit_statistics(self, start_date: datetime) -> Dict[str, Any]:
        """Get approval audit statistics."""
        stmt = select(
            func.count(ApprovalAuditLog.id).label('total_events'),
            func.count(func.distinct(ApprovalAuditLog.user_id)).label('unique_users'),
            func.count(func.distinct(ApprovalAuditLog.approval_request_id)).label('unique_requests')
        ).where(ApprovalAuditLog.created_at >= start_date)

        result = await self.db.execute(stmt)
        stats = result.first()

        return {
            "total_events": stats.total_events or 0,
            "unique_users": stats.unique_users or 0,
            "unique_requests": stats.unique_requests or 0
        }


# Global audit service instance
_audit_service: Optional[AuditService] = None


def get_audit_service(db: AsyncSession) -> AuditService:
    """Get audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService(db)
    return _audit_service


# Convenience functions for common audit operations
async def log_user_login(
    user_id: str,
    success: bool,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: AsyncSession = None
):
    """Log user login attempt."""
    if not db:
        return

    audit_service = get_audit_service(db)
    context = AuditContext(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )

    await audit_service.log_authentication_event(
        event_type=AuditEventType.USER_LOGIN if success else AuditEventType.USER_LOGIN_FAILED,
        user_id=user_id,
        success=success,
        details={"ip_address": ip_address} if ip_address else None,
        context=context
    )


async def log_permission_check(
    user_id: str,
    resource_type: str,
    action: str,
    granted: bool,
    reason: Optional[str] = None,
    db: AsyncSession = None
):
    """Log permission check."""
    if not db:
        return

    audit_service = get_audit_service(db)
    context = AuditContext(user_id=user_id)

    await audit_service.log_authorization_event(
        event_type=AuditEventType.PERMISSION_CHECK,
        user_id=user_id,
        resource_type=resource_type,
        action=action,
        granted=granted,
        reason=reason,
        context=context
    )


async def log_policy_decision(
    policy_gate_id: str,
    invoice_id: str,
    decision: str,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = None
):
    """Log policy decision."""
    if not db:
        return

    audit_service = get_audit_service(db)
    context = AuditContext(user_id=user_id)

    await audit_service.log_policy_event(
        event_type=AuditEventType.POLICY_DECISION,
        policy_gate_id=policy_gate_id,
        invoice_id=invoice_id,
        decision=decision,
        details=details,
        context=context
    )