"""
Exception Management Service for AP Intake & Validation system.

This service provides comprehensive exception classification, resolution workflows,
notification management, and metrics for the AP Intake system.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from app.api.schemas.validation import (
    ValidationCode,
    ValidationIssue,
    ValidationSeverity,
    ValidationRulesConfig,
)
from app.api.schemas.exception import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionCategory,
    ExceptionAction,
    ExceptionCreate,
    ExceptionUpdate,
    ExceptionResponse,
    ExceptionListResponse,
    ExceptionMetrics,
    ExceptionResolutionRequest,
    ExceptionBatchUpdate,
    ExceptionNotification,
)
from app.core.exceptions import ValidationException
from app.models.invoice import Invoice, InvoiceExtraction, Exception as ExceptionModel
from app.models.reference import Vendor
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ExceptionService:
    """Comprehensive exception management service."""

    def __init__(self):
        """Initialize the exception service."""
        self.exception_handlers = {
            ExceptionCategory.MATH: MathExceptionHandler(),
            ExceptionCategory.DUPLICATE: DuplicateExceptionHandler(),
            ExceptionCategory.MATCHING: MatchingExceptionHandler(),
            ExceptionCategory.VENDOR_POLICY: VendorPolicyExceptionHandler(),
            ExceptionCategory.DATA_QUALITY: DataQualityExceptionHandler(),
            ExceptionCategory.SYSTEM: SystemExceptionHandler(),
        }

    async def create_exception_from_validation(
        self,
        invoice_id: str,
        validation_issues: List[ValidationIssue],
        session: Optional[AsyncSession] = None
    ) -> List[ExceptionResponse]:
        """Create exception records from validation issues."""
        logger.info(f"Creating exceptions for invoice {invoice_id} from {len(validation_issues)} validation issues")

        exceptions = []
        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._process_validation_exceptions(invoice_id, validation_issues, session)
        else:
            return await self._process_validation_exceptions(invoice_id, validation_issues, session)

    async def _process_validation_exceptions(
        self,
        invoice_id: str,
        validation_issues: List[ValidationIssue],
        session: AsyncSession
    ) -> List[ExceptionResponse]:
        """Process validation issues and create exception records."""
        exceptions = []

        # Group related issues to avoid duplicate exceptions
        grouped_issues = self._group_related_issues(validation_issues)

        for group in grouped_issues:
            # Determine exception category and severity
            category = self._classify_exception_category(group[0].code)
            severity = self._determine_exception_severity(group)

            # Get appropriate handler
            handler = self.exception_handlers.get(category)
            if not handler:
                handler = self.exception_handlers[ExceptionCategory.SYSTEM]

            # Create exception using handler
            exception_data = await handler.create_exception(
                invoice_id=invoice_id,
                issues=group,
                session=session
            )

            # Save to database
            db_exception = ExceptionModel(
                id=uuid.uuid4(),
                invoice_id=uuid.UUID(invoice_id),
                reason_code=exception_data.reason_code,
                details_json={
                    "category": category.value,
                    "severity": severity.value,
                    "issues": [issue.dict() for issue in group],
                    "handler_data": exception_data.details,
                    "auto_resolution_possible": exception_data.auto_resolution_possible,
                    "suggested_actions": exception_data.suggested_actions,
                },
                resolved_at=None,
                resolved_by=None,
                resolution_notes=None,
            )

            session.add(db_exception)
            await session.flush()
            await session.refresh(db_exception)

            # Create response
            exception_response = ExceptionResponse(
                id=str(db_exception.id),
                invoice_id=str(db_exception.invoice_id),
                reason_code=db_exception.reason_code,
                category=category,
                severity=severity,
                status=ExceptionStatus.OPEN,
                message=exception_data.message,
                details=exception_data.details,
                auto_resolution_possible=exception_data.auto_resolution_possible,
                suggested_actions=exception_data.suggested_actions,
                created_at=db_exception.created_at,
                updated_at=db_exception.updated_at,
                resolved_at=None,
                resolved_by=None,
                resolution_notes=None,
            )

            exceptions.append(exception_response)

        await session.commit()

        # Send notifications for high-priority exceptions
        await self._send_exception_notifications(exceptions, session)

        logger.info(f"Created {len(exceptions)} exceptions for invoice {invoice_id}")
        return exceptions

    def _group_related_issues(self, issues: List[ValidationIssue]) -> List[List[ValidationIssue]]:
        """Group related validation issues to avoid duplicate exceptions."""
        grouped = {}

        for issue in issues:
            # Group by code and field/line_number combination
            group_key = (issue.code.value, issue.field, issue.line_number)

            if group_key not in grouped:
                grouped[group_key] = []
            grouped[group_key].append(issue)

        return list(grouped.values())

    def _classify_exception_category(self, code: ValidationCode) -> ExceptionCategory:
        """Classify validation code into exception category."""
        math_codes = {
            ValidationCode.SUBTOTAL_MISMATCH,
            ValidationCode.TOTAL_MISMATCH,
            ValidationCode.LINE_MATH_MISMATCH,
            ValidationCode.INVALID_AMOUNT,
        }

        duplicate_codes = {
            ValidationCode.DUPLICATE_INVOICE,
        }

        matching_codes = {
            ValidationCode.PO_NOT_FOUND,
            ValidationCode.PO_MISMATCH,
            ValidationCode.PO_AMOUNT_MISMATCH,
            ValidationCode.PO_QUANTITY_MISMATCH,
            ValidationCode.GRN_NOT_FOUND,
            ValidationCode.GRN_MISMATCH,
            ValidationCode.GRN_QUANTITY_MISMATCH,
        }

        vendor_policy_codes = {
            ValidationCode.INACTIVE_VENDOR,
            ValidationCode.INVALID_CURRENCY,
            ValidationCode.INVALID_TAX_ID,
            ValidationCode.SPEND_LIMIT_EXCEEDED,
            ValidationCode.PAYMENT_TERMS_VIOLATION,
        }

        data_quality_codes = {
            ValidationCode.MISSING_REQUIRED_FIELD,
            ValidationCode.INVALID_FIELD_FORMAT,
            ValidationCode.INVALID_DATA_STRUCTURE,
            ValidationCode.NO_LINE_ITEMS,
        }

        system_codes = {
            ValidationCode.VALIDATION_ERROR,
            ValidationCode.DATABASE_ERROR,
        }

        if code in math_codes:
            return ExceptionCategory.MATH
        elif code in duplicate_codes:
            return ExceptionCategory.DUPLICATE
        elif code in matching_codes:
            return ExceptionCategory.MATCHING
        elif code in vendor_policy_codes:
            return ExceptionCategory.VENDOR_POLICY
        elif code in data_quality_codes:
            return ExceptionCategory.DATA_QUALITY
        elif code in system_codes:
            return ExceptionCategory.SYSTEM
        else:
            return ExceptionCategory.DATA_QUALITY  # Default category

    def _determine_exception_severity(self, issues: List[ValidationIssue]) -> ExceptionSeverity:
        """Determine exception severity based on validation issues."""
        if any(issue.severity == ValidationSeverity.ERROR for issue in issues):
            return ExceptionSeverity.ERROR
        elif any(issue.severity == ValidationSeverity.WARNING for issue in issues):
            return ExceptionSeverity.WARNING
        else:
            return ExceptionSeverity.INFO

    async def get_exception(
        self,
        exception_id: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[ExceptionResponse]:
        """Get exception by ID."""
        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._get_exception_by_id(exception_id, session)
        else:
            return await self._get_exception_by_id(exception_id, session)

    async def _get_exception_by_id(
        self,
        exception_id: str,
        session: AsyncSession
    ) -> Optional[ExceptionResponse]:
        """Get exception by ID from database."""
        query = select(ExceptionModel).where(ExceptionModel.id == uuid.UUID(exception_id))
        result = await session.execute(query)
        db_exception = result.scalar_one_or_none()

        if not db_exception:
            return None

        return self._convert_to_response(db_exception)

    async def list_exceptions(
        self,
        invoice_id: Optional[str] = None,
        status: Optional[ExceptionStatus] = None,
        severity: Optional[ExceptionSeverity] = None,
        category: Optional[ExceptionCategory] = None,
        reason_code: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
        session: Optional[AsyncSession] = None
    ) -> ExceptionListResponse:
        """List exceptions with filtering and pagination."""
        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._query_exceptions(
                    invoice_id, status, severity, category, reason_code,
                    created_after, created_before, limit, offset, session
                )
        else:
            return await self._query_exceptions(
                invoice_id, status, severity, category, reason_code,
                created_after, created_before, limit, offset, session
            )

    async def _query_exceptions(
        self,
        invoice_id: Optional[str],
        status: Optional[ExceptionStatus],
        severity: Optional[ExceptionSeverity],
        category: Optional[ExceptionCategory],
        reason_code: Optional[str],
        created_after: Optional[datetime],
        created_before: Optional[datetime],
        limit: int,
        offset: int,
        session: AsyncSession
    ) -> ExceptionListResponse:
        """Query exceptions from database with filters."""
        query = select(ExceptionModel)

        # Apply filters
        conditions = []

        if invoice_id:
            conditions.append(ExceptionModel.invoice_id == uuid.UUID(invoice_id))

        if status:
            conditions.append(ExceptionModel.details_json['status'].astext == status.value)

        if severity:
            conditions.append(ExceptionModel.details_json['severity'].astext == severity.value)

        if category:
            conditions.append(ExceptionModel.details_json['category'].astext == category.value)

        if reason_code:
            conditions.append(ExceptionModel.reason_code == reason_code)

        if created_after:
            conditions.append(ExceptionModel.created_at >= created_after)

        if created_before:
            conditions.append(ExceptionModel.created_at <= created_before)

        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count(ExceptionModel.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        count_result = await session.execute(count_query)
        total = count_result.scalar()

        # Apply ordering and pagination
        query = query.order_by(desc(ExceptionModel.created_at))
        query = query.offset(offset).limit(limit)

        # Execute query
        result = await session.execute(query)
        exceptions = result.scalars().all()

        # Convert to response
        exception_responses = [self._convert_to_response(exc) for exc in exceptions]

        return ExceptionListResponse(
            exceptions=exception_responses,
            total=total,
            limit=limit,
            offset=offset,
        )

    def _convert_to_response(self, db_exception: ExceptionModel) -> ExceptionResponse:
        """Convert database exception to response model."""
        details = db_exception.details_json or {}

        return ExceptionResponse(
            id=str(db_exception.id),
            invoice_id=str(db_exception.invoice_id),
            reason_code=db_exception.reason_code,
            category=ExceptionCategory(details.get('category', 'DATA_QUALITY')),
            severity=ExceptionSeverity(details.get('severity', 'ERROR')),
            status=ExceptionStatus.OPEN if db_exception.resolved_at is None else ExceptionStatus.RESOLVED,
            message=details.get('message', db_exception.reason_code),
            details=details.get('handler_data', {}),
            auto_resolution_possible=details.get('auto_resolution_possible', False),
            suggested_actions=[ExceptionAction(action) for action in details.get('suggested_actions', [])],
            created_at=db_exception.created_at,
            updated_at=db_exception.updated_at,
            resolved_at=db_exception.resolved_at,
            resolved_by=db_exception.resolved_by,
            resolution_notes=db_exception.resolution_notes,
        )

    async def resolve_exception(
        self,
        exception_id: str,
        resolution_request: ExceptionResolutionRequest,
        session: Optional[AsyncSession] = None
    ) -> ExceptionResponse:
        """Resolve an exception."""
        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._process_exception_resolution(exception_id, resolution_request, session)
        else:
            return await self._process_exception_resolution(exception_id, resolution_request, session)

    async def _process_exception_resolution(
        self,
        exception_id: str,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> ExceptionResponse:
        """Process exception resolution."""
        # Get exception
        query = select(ExceptionModel).where(ExceptionModel.id == uuid.UUID(exception_id))
        result = await session.execute(query)
        db_exception = result.scalar_one_or_none()

        if not db_exception:
            raise ValueError(f"Exception {exception_id} not found")

        # Get handler for exception category
        details = db_exception.details_json or {}
        category = ExceptionCategory(details.get('category', 'DATA_QUALITY'))
        handler = self.exception_handlers.get(category)

        if handler:
            # Validate resolution
            validation_result = await handler.validate_resolution(
                db_exception, resolution_request, session
            )
            if not validation_result.valid:
                raise ValueError(f"Invalid resolution: {validation_result.message}")

        # Update exception
        db_exception.resolved_at = datetime.utcnow()
        db_exception.resolved_by = resolution_request.resolved_by
        db_exception.resolution_notes = resolution_request.notes

        # Update details
        details.update({
            "status": ExceptionStatus.RESOLVED.value,
            "resolution_action": resolution_request.action.value,
            "resolution_data": resolution_request.resolution_data or {},
        })
        db_exception.details_json = details

        await session.commit()
        await session.refresh(db_exception)

        # If auto-approve invoice after resolution
        if resolution_request.auto_approve_invoice:
            await self._auto_approve_invoice(db_exception.invoice_id, session)

        return self._convert_to_response(db_exception)

    async def batch_resolve_exceptions(
        self,
        exception_ids: List[str],
        batch_request: ExceptionBatchUpdate,
        session: Optional[AsyncSession] = None
    ) -> List[ExceptionResponse]:
        """Resolve multiple exceptions at once."""
        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._process_batch_resolution(exception_ids, batch_request, session)
        else:
            return await self._process_batch_resolution(exception_ids, batch_request, session)

    async def _process_batch_resolution(
        self,
        exception_ids: List[str],
        batch_request: ExceptionBatchUpdate,
        session: AsyncSession
    ) -> List[ExceptionResponse]:
        """Process batch exception resolution."""
        resolved_exceptions = []
        errors = []

        for exception_id in exception_ids:
            try:
                resolution_request = ExceptionResolutionRequest(
                    action=batch_request.action,
                    resolved_by=batch_request.resolved_by,
                    notes=batch_request.notes,
                    resolution_data=batch_request.resolution_data,
                    auto_approve_invoice=batch_request.auto_approve_invoices,
                )

                resolved = await self._process_exception_resolution(exception_id, resolution_request, session)
                resolved_exceptions.append(resolved)

            except Exception as e:
                errors.append({
                    "exception_id": exception_id,
                    "error": str(e)
                })
                logger.error(f"Failed to resolve exception {exception_id}: {e}")

        if errors:
            logger.warning(f"Batch resolution completed with {len(errors)} errors")

        return resolved_exceptions

    async def get_exception_metrics(
        self,
        days: int = 30,
        session: Optional[AsyncSession] = None
    ) -> ExceptionMetrics:
        """Get exception metrics for the specified period."""
        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._calculate_metrics(days, session)
        else:
            return await self._calculate_metrics(days, session)

    async def _calculate_metrics(
        self,
        days: int,
        session: AsyncSession
    ) -> ExceptionMetrics:
        """Calculate exception metrics."""
        since_date = datetime.utcnow() - timedelta(days=days)

        # Total exceptions
        total_query = select(func.count(ExceptionModel.id)).where(
            ExceptionModel.created_at >= since_date
        )
        total_result = await session.execute(total_query)
        total_exceptions = total_result.scalar()

        # Resolved exceptions
        resolved_query = select(func.count(ExceptionModel.id)).where(
            and_(
                ExceptionModel.created_at >= since_date,
                ExceptionModel.resolved_at.isnot(None)
            )
        )
        resolved_result = await session.execute(resolved_query)
        resolved_exceptions = resolved_result.scalar()

        # Breakdown by category
        category_query = select(
            ExceptionModel.details_json['category'].astext,
            func.count(ExceptionModel.id)
        ).where(
            ExceptionModel.created_at >= since_date
        ).group_by(ExceptionModel.details_json['category'].astext)

        category_result = await session.execute(category_query)
        by_category = dict(category_result.all())

        # Breakdown by severity
        severity_query = select(
            ExceptionModel.details_json['severity'].astext,
            func.count(ExceptionModel.id)
        ).where(
            ExceptionModel.created_at >= since_date
        ).group_by(ExceptionModel.details_json['severity'].astext)

        severity_result = await session.execute(severity_query)
        by_severity = dict(severity_result.all())

        # Breakdown by status
        open_query = select(func.count(ExceptionModel.id)).where(
            and_(
                ExceptionModel.created_at >= since_date,
                ExceptionModel.resolved_at.is_(None)
            )
        )
        open_result = await session.execute(open_query)
        open_exceptions = open_result.scalar()

        # Average resolution time
        resolution_time_query = select(
            func.avg(
                func.extract('epoch', ExceptionModel.resolved_at - ExceptionModel.created_at)
            )
        ).where(
            and_(
                ExceptionModel.created_at >= since_date,
                ExceptionModel.resolved_at.isnot(None)
            )
        )
        resolution_time_result = await session.execute(resolution_time_query)
        avg_resolution_hours = resolution_time_result.scalar() or 0

        # Top reason codes
        reason_code_query = select(
            ExceptionModel.reason_code,
            func.count(ExceptionModel.id)
        ).where(
            ExceptionModel.created_at >= since_date
        ).group_by(ExceptionModel.reason_code).order_by(
            desc(func.count(ExceptionModel.id))
        ).limit(10)

        reason_code_result = await session.execute(reason_code_query)
        top_reason_codes = dict(reason_code_result.all())

        return ExceptionMetrics(
            total_exceptions=total_exceptions,
            resolved_exceptions=resolved_exceptions,
            open_exceptions=open_exceptions,
            resolution_rate=(resolved_exceptions / total_exceptions * 100) if total_exceptions > 0 else 0,
            avg_resolution_hours=avg_resolution_hours / 3600,  # Convert seconds to hours
            by_category=by_category,
            by_severity=by_severity,
            top_reason_codes=top_reason_codes,
            period_days=days,
            generated_at=datetime.utcnow(),
        )

    async def _send_exception_notifications(
        self,
        exceptions: List[ExceptionResponse],
        session: AsyncSession
    ) -> None:
        """Send notifications for high-priority exceptions."""
        high_priority = [exc for exc in exceptions if exc.severity == ExceptionSeverity.ERROR]

        if not high_priority:
            return

        # Get invoice details for context
        invoice_ids = [exc.invoice_id for exc in high_priority]
        invoice_query = select(Invoice).where(Invoice.id.in_(invoice_ids))
        invoice_result = await session.execute(invoice_query)
        invoices = {str(inv.id): inv for inv in invoice_result.scalars().all()}

        # Create notifications
        notifications = []
        for exc in high_priority:
            invoice = invoices.get(exc.invoice_id)
            if invoice:
                notification = ExceptionNotification(
                    exception_id=exc.id,
                    invoice_id=exc.invoice_id,
                    severity=exc.severity,
                    message=f"High priority exception: {exc.message}",
                    category=exc.category,
                    reason_code=exc.reason_code,
                    created_at=exc.created_at,
                    invoice_number=f"Invoice-{exc.invoice_id[:8]}",  # Would get from extraction
                    vendor_name="Unknown Vendor",  # Would get from vendor relationship
                )
                notifications.append(notification)

        # Send notifications (placeholder - would integrate with email/Slack/etc.)
        await self._send_notifications(notifications)

    async def _send_notifications(self, notifications: List[ExceptionNotification]) -> None:
        """Send notifications through configured channels."""
        # This would integrate with actual notification systems
        # For now, just log the notifications
        for notification in notifications:
            logger.info(f"NOTIFICATION: {notification.message} - Exception: {notification.exception_id}")

    async def _auto_approve_invoice(self, invoice_id: uuid.UUID, session: AsyncSession) -> None:
        """Auto-approve invoice after exception resolution."""
        # Update invoice status to ready
        query = select(Invoice).where(Invoice.id == invoice_id)
        result = await session.execute(query)
        invoice = result.scalar_one_or_none()

        if invoice:
            invoice.status = InvoiceStatus.READY
            await session.commit()
            logger.info(f"Auto-approved invoice {invoice_id} after exception resolution")


# Exception Handlers for different categories

class ExceptionHandler:
    """Base class for exception handlers."""

    async def create_exception(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> ExceptionCreate:
        """Create exception data from validation issues."""
        raise NotImplementedError

    async def validate_resolution(
        self,
        db_exception: ExceptionModel,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> Any:
        """Validate exception resolution."""
        raise NotImplementedError


class MathExceptionHandler(ExceptionHandler):
    """Handler for math-related exceptions."""

    async def create_exception(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> ExceptionCreate:
        """Create math exception."""
        issue = issues[0]  # Primary issue

        return ExceptionCreate(
            reason_code=issue.code.value,
            message=f"Mathematical discrepancy detected: {issue.message}",
            details={
                "field": issue.field,
                "actual_value": issue.actual_value,
                "expected_value": issue.expected_value,
                "difference": issue.details.get("difference") if issue.details else None,
            },
            auto_resolution_possible=True,
            suggested_actions=[ExceptionAction.RECALCULATE, ExceptionAction.MANUAL_ADJUST],
        )

    async def validate_resolution(
        self,
        db_exception: ExceptionModel,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> Any:
        """Validate math exception resolution."""
        # Check if adjustment amounts are reasonable
        if resolution_request.action == ExceptionAction.MANUAL_ADJUST:
            adjustment = resolution_request.resolution_data.get("adjustment_amount", 0)
            if abs(float(adjustment)) > 10000:  # Large adjustment threshold
                return {"valid": False, "message": "Adjustment amount too large"}

        return {"valid": True}


class DuplicateExceptionHandler(ExceptionHandler):
    """Handler for duplicate invoice exceptions."""

    async def create_exception(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> ExceptionCreate:
        """Create duplicate invoice exception."""
        issue = issues[0]

        return ExceptionCreate(
            reason_code=issue.code.value,
            message="Potential duplicate invoice detected",
            details=issue.details or {},
            auto_resolution_possible=False,
            suggested_actions=[ExceptionAction.MANUAL_REVIEW, ExceptionAction.REJECT_DUPLICATE],
        )

    async def validate_resolution(
        self,
        db_exception: ExceptionModel,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> Any:
        """Validate duplicate exception resolution."""
        # Manual review required for duplicates
        if resolution_request.action == ExceptionAction.MANUAL_ADJUST:
            return {"valid": False, "message": "Manual adjustments not allowed for duplicates"}

        return {"valid": True}


class MatchingExceptionHandler(ExceptionHandler):
    """Handler for PO/GRN matching exceptions."""

    async def create_exception(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> ExceptionCreate:
        """Create matching exception."""
        issue = issues[0]

        return ExceptionCreate(
            reason_code=issue.code.value,
            message=f"Document matching issue: {issue.message}",
            details={
                "field": issue.field,
                "po_number": issue.details.get("po_number") if issue.details else None,
                "tolerance": issue.details.get("tolerance_percent") if issue.details else None,
            },
            auto_resolution_possible=True,
            suggested_actions=[ExceptionAction.UPDATE_PO, ExceptionAction.ACCEPT_VARIANCE, ExceptionAction.MANUAL_REVIEW],
        )

    async def validate_resolution(
        self,
        db_exception: ExceptionModel,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> Any:
        """Validate matching exception resolution."""
        # Check variance acceptance limits
        if resolution_request.action == ExceptionAction.ACCEPT_VARIANCE:
            variance = resolution_request.resolution_data.get("variance_percent", 0)
            if float(variance) > 10:  # 10% variance limit
                return {"valid": False, "message": "Variance exceeds acceptable limit"}

        return {"valid": True}


class VendorPolicyExceptionHandler(ExceptionHandler):
    """Handler for vendor policy violations."""

    async def create_exception(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> ExceptionCreate:
        """Create vendor policy exception."""
        issue = issues[0]

        return ExceptionCreate(
            reason_code=issue.code.value,
            message=f"Vendor policy violation: {issue.message}",
            details={
                "vendor_name": issue.details.get("vendor_name") if issue.details else None,
                "policy_type": issue.field,
            },
            auto_resolution_possible=False,
            suggested_actions=[ExceptionAction.ESCALATE, ExceptionAction.MANUAL_APPROVAL],
        )

    async def validate_resolution(
        self,
        db_exception: ExceptionModel,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> Any:
        """Validate vendor policy exception resolution."""
        # Policy violations often require escalation
        if resolution_request.action == ExceptionAction.AUTO_APPROVE:
            return {"valid": False, "message": "Auto-approval not allowed for policy violations"}

        return {"valid": True}


class DataQualityExceptionHandler(ExceptionHandler):
    """Handler for data quality issues."""

    async def create_exception(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> ExceptionCreate:
        """Create data quality exception."""
        issue = issues[0]

        return ExceptionCreate(
            reason_code=issue.code.value,
            message=f"Data quality issue: {issue.message}",
            details={
                "field": issue.field,
                "line_number": issue.line_number,
                "expected_format": issue.expected_value,
            },
            auto_resolution_possible=True,
            suggested_actions=[ExceptionAction.DATA_CORRECTION, ExceptionAction.MANUAL_REVIEW],
        )

    async def validate_resolution(
        self,
        db_exception: ExceptionModel,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> Any:
        """Validate data quality exception resolution."""
        # Check corrected data format
        if resolution_request.action == ExceptionAction.DATA_CORRECTION:
            corrected_value = resolution_request.resolution_data.get("corrected_value")
            if not corrected_value:
                return {"valid": False, "message": "Corrected value required"}

        return {"valid": True}


class SystemExceptionHandler(ExceptionHandler):
    """Handler for system-level exceptions."""

    async def create_exception(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> ExceptionCreate:
        """Create system exception."""
        issue = issues[0]

        return ExceptionCreate(
            reason_code=issue.code.value,
            message=f"System error: {issue.message}",
            details={
                "error_type": issue.details.get("error_type") if issue.details else None,
                "stack_trace": issue.details.get("stack_trace") if issue.details else None,
            },
            auto_resolution_possible=False,
            suggested_actions=[ExceptionAction.ESCALATE, ExceptionAction.SYSTEM_RETRY],
        )

    async def validate_resolution(
        self,
        db_exception: ExceptionModel,
        resolution_request: ExceptionResolutionRequest,
        session: AsyncSession
    ) -> Any:
        """Validate system exception resolution."""
        # System errors usually require escalation or retry
        return {"valid": True}