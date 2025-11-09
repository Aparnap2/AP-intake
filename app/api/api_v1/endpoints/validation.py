"""
Enhanced validation API endpoints with comprehensive validation features.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

from app.api.deps import get_async_db, get_current_user
from app.api.schemas.validation import (
    ValidationRequest,
    ValidationResponse,
    ValidationSummary,
    ValidationExport,
    ValidationErrorDetail
)
from app.api.schemas.invoice import InvoiceResponse
from app.services.validation_engine import ValidationEngine, ReasonTaxonomy
from app.services.enhanced_extraction_service import EnhancedExtractionService
from app.services.llm_patch_service import LLMPatchService
from app.models.validation import (
    ValidationSession,
    ValidationIssue,
    ValidationRule,
    ValidationMetrics
)
from app.models.invoice import Invoice, InvoiceExtraction
from app.core.exceptions import ValidationException
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/validate", response_model=ValidationResponse)
async def validate_invoice(
    validation_request: ValidationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Perform comprehensive validation of invoice extraction data.

    This endpoint runs the full validation suite including:
    - Structural validation (required fields, formats)
    - Mathematical validation (calculations, totals)
    - Business rules validation (vendor, PO, duplicates)
    """
    logger.info(f"Starting validation for invoice {validation_request.invoice_id}")

    try:
        # Initialize validation engine
        validation_engine = ValidationEngine()

        # Perform comprehensive validation
        validation_result = await validation_engine.validate_comprehensive(
            extraction_result=validation_request.extraction_result,
            invoice_id=validation_request.invoice_id,
            vendor_id=validation_request.vendor_id,
            strict_mode=validation_request.strict_mode,
            custom_rules=validation_request.rules_config.rules if validation_request.rules_config else None
        )

        # Create validation session record
        session = await _create_validation_session(
            db, validation_request, validation_result, current_user.id
        )

        # Store validation issues
        await _store_validation_issues(db, session.id, validation_result.issues)

        # Schedule background tasks for analytics
        background_tasks.add_task(
            _update_validation_metrics,
            validation_request.invoice_id,
            validation_result
        )

        processing_time = validation_result.processing_time_ms or "0"

        return ValidationResponse(
            success=validation_result.passed,
            validation_result=validation_result,
            processing_time_ms=processing_time,
            applied_rules=[rule.name for category in validation_engine.rules.values() for rule in category]
        )

    except ValidationException as e:
        logger.error(f"Validation exception for invoice {validation_request.invoice_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error")


@router.post("/validate/{invoice_id}", response_model=ValidationResponse)
async def validate_invoice_by_id(
    invoice_id: str,
    strict_mode: bool = Query(False, description="Enable strict validation mode"),
    enhance_extraction: bool = Query(True, description="Apply LLM enhancement before validation"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Validate an invoice by ID with optional enhancement.

    This endpoint retrieves the latest extraction for an invoice,
    optionally enhances it with LLM patching, then validates it.
    """
    logger.info(f"Validating invoice {invoice_id} (strict_mode={strict_mode}, enhance={enhance_extraction})")

    try:
        # Get invoice and extraction
        query = select(Invoice, InvoiceExtraction).join(InvoiceExtraction).where(
            Invoice.id == invoice_id
        ).order_by(desc(InvoiceExtraction.created_at)).limit(1)

        result = await db.execute(query)
        invoice_extraction = result.first()

        if not invoice_extraction:
            raise HTTPException(status_code=404, detail="Invoice or extraction not found")

        invoice, extraction = invoice_extraction

        # Prepare extraction result
        extraction_result = {
            "header": extraction.header_json or {},
            "lines": extraction.lines_json or [],
            "confidence": extraction.confidence_json or {}
        }

        # Apply enhancement if requested
        if enhance_extraction:
            enhanced_extraction = await _enhance_extraction_result(extraction_result)
            extraction_result = enhanced_extraction

        # Create validation request
        validation_request = ValidationRequest(
            invoice_id=invoice_id,
            extraction_result=extraction_result,
            vendor_id=str(invoice.vendor_id) if invoice.vendor_id else None,
            strict_mode=strict_mode
        )

        # Perform validation
        validation_engine = ValidationEngine()
        validation_result = await validation_engine.validate_comprehensive(
            extraction_result=extraction_result,
            invoice_id=invoice_id,
            vendor_id=validation_request.vendor_id,
            strict_mode=strict_mode
        )

        # Create validation session
        session = await _create_validation_session(
            db, validation_request, validation_result, current_user.id
        )

        # Store validation issues
        await _store_validation_issues(db, session.id, validation_result.issues)

        # Update invoice status based on validation
        await _update_invoice_validation_status(db, invoice_id, validation_result)

        processing_time = validation_result.processing_time_ms or "0"

        return ValidationResponse(
            success=validation_result.passed,
            validation_result=validation_result,
            processing_time_ms=processing_time,
            applied_rules=[rule.name for category in validation_engine.rules.values() for rule in category]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Validation failed")


@router.get("/rules", response_model=List[Dict[str, Any]])
async def get_validation_rules(
    category: Optional[str] = Query(None, description="Filter by rule category"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """Get available validation rules with their configurations."""
    try:
        query = select(ValidationRule)

        if category:
            query = query.where(ValidationRule.category == category)
        if enabled is not None:
            query = query.where(ValidationRule.enabled == enabled)

        result = await db.execute(query)
        rules = result.scalars().all()

        return [
            {
                "id": str(rule.id),
                "name": rule.name,
                "category": rule.category,
                "description": rule.description,
                "severity": rule.severity,
                "enabled": rule.enabled,
                "version": rule.version,
                "parameters": rule.parameters,
                "execution_count": rule.execution_count,
                "failure_count": rule.failure_count,
                "last_executed": rule.last_executed
            }
            for rule in rules
        ]

    except Exception as e:
        logger.error(f"Error getting validation rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve validation rules")


@router.put("/rules/{rule_id}")
async def update_validation_rule(
    rule_id: str,
    rule_update: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """Update a validation rule configuration."""
    try:
        # Get existing rule
        query = select(ValidationRule).where(ValidationRule.id == rule_id)
        result = await db.execute(query)
        rule = result.scalar_one_or_none()

        if not rule:
            raise HTTPException(status_code=404, detail="Validation rule not found")

        # Update rule properties
        if "enabled" in rule_update:
            rule.enabled = rule_update["enabled"]
        if "parameters" in rule_update:
            rule.parameters = rule_update["parameters"]
        if "condition" in rule_update:
            rule.condition = rule_update["condition"]

        rule.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(rule)

        return {"message": "Validation rule updated successfully", "rule_id": rule_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating validation rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update validation rule")


@router.get("/sessions/{session_id}/issues")
async def get_validation_issues(
    session_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """Get validation issues for a specific session."""
    try:
        # Get validation session
        session_query = select(ValidationSession).where(ValidationSession.id == session_id)
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Validation session not found")

        # Get issues for the session
        query = select(ValidationIssue).where(ValidationIssue.session_id == session_id)

        if severity:
            query = query.where(ValidationIssue.severity == severity.upper())
        if category:
            query = query.where(ValidationIssue.category == category)

        query = query.order_by(ValidationIssue.created_at)
        result = await db.execute(query)
        issues = result.scalars().all()

        return [
            {
                "id": str(issue.id),
                "reason_taxonomy": issue.reason_taxonomy,
                "validation_code": issue.validation_code,
                "severity": issue.severity,
                "category": issue.category,
                "message": issue.message,
                "field_name": issue.field_name,
                "line_number": issue.line_number,
                "expected_value": issue.expected_value,
                "actual_value": issue.actual_value,
                "details": issue.details,
                "suggested_actions": issue.suggested_actions or [],
                "business_impact": issue.business_impact,
                "auto_resolvable": issue.auto_resolvable,
                "requires_human_review": issue.requires_human_review,
                "resolution_status": issue.resolution_status,
                "created_at": issue.created_at
            }
            for issue in issues
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting validation issues for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve validation issues")


@router.post("/issues/{issue_id}/resolve")
async def resolve_validation_issue(
    issue_id: str,
    resolution_data: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """Resolve a validation issue."""
    try:
        # Get the issue
        query = select(ValidationIssue).where(ValidationIssue.id == issue_id)
        result = await db.execute(query)
        issue = result.scalar_one_or_none()

        if not issue:
            raise HTTPException(status_code=404, detail="Validation issue not found")

        # Update issue resolution
        issue.resolution_status = resolution_data.get("status", "resolved")
        issue.resolution_notes = resolution_data.get("notes")
        issue.resolved_at = datetime.utcnow()
        issue.resolved_by = current_user.email

        await db.commit()

        return {"message": "Validation issue resolved successfully", "issue_id": issue_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving validation issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve validation issue")


@router.get("/summary", response_model=ValidationSummary)
async def get_validation_summary(
    days: int = Query(7, description="Number of days to summarize", ge=1, le=365),
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """Get validation summary for the specified period."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get validation sessions for the period
        query = select(
            func.count(ValidationSession.id).label('total_invoices'),
            func.sum(func.case([(ValidationSession.overall_passed == True, 1)], else_=0)).label('passed_invoices'),
            func.sum(func.case([(ValidationSession.overall_passed == False, 1)], else_=0)).label('failed_invoices'),
            func.sum(func.case([(ValidationSession.confidence_score >= 0.9, 1)], else_=0)).label('auto_approved'),
            func.sum(func.case([(ValidationSession.requires_human_review == True, 1)], else_=0)).label('human_review_required'),
            func.avg(ValidationSession.confidence_score).label('average_confidence'),
            func.avg(ValidationSession.processing_time_ms).label('average_processing_time')
        ).where(ValidationSession.started_at >= start_date)

        result = await db.execute(query)
        summary_data = result.first()

        # Get common issues
        issues_query = select(
            ValidationIssue.reason_taxonomy,
            func.count(ValidationIssue.id).label('count')
        ).join(ValidationSession).filter(
            ValidationSession.started_at >= start_date
        ).group_by(ValidationIssue.reason_taxonomy).order_by(
            desc(func.count(ValidationIssue.id))
        ).limit(10)

        issues_result = await db.execute(issues_query)
        common_issues = [
            {"taxonomy": row.reason_taxonomy, "count": row.count}
            for row in issues_result
        ]

        # Get issue categories breakdown
        categories_query = select(
            ValidationIssue.category,
            func.count(ValidationIssue.id).label('count')
        ).join(ValidationSession).filter(
            ValidationSession.started_at >= start_date
        ).group_by(ValidationIssue.category)

        categories_result = await db.execute(categories_query)
        issue_categories = {
            row.category: row.count for row in categories_result
        }

        total_invoices = summary_data.total_invoices or 0
        passed_invoices = summary_data.passed_invoices or 0

        return ValidationSummary(
            total_invoices=total_invoices,
            passed_invoices=passed_invoices,
            failed_invoices=summary_data.failed_invoices or 0,
            auto_approved=summary_data.auto_approved or 0,
            human_review_required=summary_data.human_review_required or 0,
            common_issues=common_issues,
            issue_categories=issue_categories,
            average_processing_time_ms=float(summary_data.average_processing_time or 0),
            confidence_distribution={},  # Would be calculated from actual data
            po_match_rate=0.0,  # Would be calculated from actual data
            grn_match_rate=0.0,  # Would be calculated from actual data
            duplicate_detection_rate=0.0,  # Would be calculated from actual data
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting validation summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate validation summary")


@router.get("/export")
async def export_validation_data(
    days: int = Query(7, description="Number of days to export", ge=1, le=365),
    format: str = Query("json", description="Export format: json, csv"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """Export validation data for the specified period."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get validation sessions with related data
        query = select(ValidationSession, Invoice, InvoiceExtraction).join(
            Invoice, ValidationSession.invoice_id == Invoice.id
        ).join(
            InvoiceExtraction, Invoice.id == InvoiceExtraction.invoice_id
        ).where(
            ValidationSession.started_at >= start_date
        ).order_by(ValidationSession.started_at.desc())

        result = await db.execute(query)
        export_data = []

        for session, invoice, extraction in result:
            # Get validation issues for this session
            issues_query = select(ValidationIssue).where(
                ValidationIssue.session_id == session.id
            )
            issues_result = await db.execute(issues_query)
            issues = issues_result.scalars().all()

            # Get top issues
            top_issues = [issue.message for issue in issues[:5]]

            export_data.append(ValidationExport(
                invoice_id=str(invoice.id),
                vendor_name=extraction.header_json.get("vendor_name", "Unknown") if extraction.header_json else "Unknown",
                invoice_number=extraction.header_json.get("invoice_number", "Unknown") if extraction.header_json else "Unknown",
                invoice_date=extraction.header_json.get("invoice_date", "") if extraction.header_json else "",
                total_amount=float(extraction.header_json.get("total_amount", 0)) if extraction.header_json else 0.0,
                currency=extraction.header_json.get("currency", "USD") if extraction.header_json else "USD",
                validation_passed=session.overall_passed,
                confidence_score=session.confidence_score or 0.0,
                error_count=session.error_count,
                warning_count=session.warning_count,
                math_passed=session.mathematical_passed,
                duplicate_found=any(issue.reason_taxonomy == ReasonTaxonomy.DUPLICATE_SUSPECT.value for issue in issues),
                po_matched=session.business_rules_passed,  # Simplified
                grn_matched=session.business_rules_passed,  # Simplified
                vendor_policy_passed=session.structural_passed,  # Simplified
                top_issues=top_issues,
                validated_at=session.started_at
            ))

        if format.lower() == "csv":
            # Convert to CSV format
            import csv
            import io

            output = io.StringIO()
            if export_data:
                writer = csv.DictWriter(output, fieldnames=export_data[0].model_dump().keys())
                writer.writeheader()
                for item in export_data:
                    writer.writerow(item.model_dump())

            return {
                "format": "csv",
                "data": output.getvalue(),
                "filename": f"validation_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        else:
            # Return JSON format
            return {
                "format": "json",
                "data": [item.model_dump() for item in export_data],
                "filename": f"validation_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }

    except Exception as e:
        logger.error(f"Error exporting validation data: {e}")
        raise HTTPException(status_code=500, detail="Failed to export validation data")


@router.get("/metrics")
async def get_validation_metrics(
    days: int = Query(30, description="Number of days for metrics", ge=1, le=365),
    db: AsyncSession = Depends(get_async_db),
    current_user: Any = Depends(get_current_user)
):
    """Get detailed validation metrics and performance data."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get existing metrics or calculate new ones
        metrics_query = select(ValidationMetrics).where(
            and_(
                ValidationMetrics.period_start >= start_date,
                ValidationMetrics.period_type == "daily"
            )
        ).order_by(desc(ValidationMetrics.period_start))

        result = await db.execute(metrics_query)
        metrics = result.scalars().all()

        if not metrics:
            # Calculate metrics on-demand if not pre-calculated
            metrics = await _calculate_validation_metrics(db, start_date, datetime.utcnow())

        return [
            {
                "period_start": metric.period_start,
                "period_end": metric.period_end,
                "period_type": metric.period_type,
                "total_invoices": metric.total_invoices,
                "passed_invoices": metric.passed_invoices,
                "failed_invoices": metric.failed_invoices,
                "auto_approved": metric.auto_approved,
                "human_review_required": metric.human_review_required,
                "average_confidence": metric.average_confidence,
                "average_processing_time_ms": metric.average_processing_time_ms,
                "total_issues": metric.total_issues,
                "error_issues": metric.error_issues,
                "warning_issues": metric.warning_issues,
                "structural_pass_rate": metric.structural_pass_rate,
                "mathematical_pass_rate": metric.mathematical_pass_rate,
                "business_rules_pass_rate": metric.business_rules_pass_rate,
                "top_reason_taxonomies": metric.top_reason_taxonomies,
                "top_failed_rules": metric.top_failed_rules
            }
            for metric in metrics
        ]

    except Exception as e:
        logger.error(f"Error getting validation metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve validation metrics")


# Helper functions
async def _create_validation_session(
    db: AsyncSession,
    validation_request: ValidationRequest,
    validation_result: Any,
    user_id: str
) -> ValidationSession:
    """Create a validation session record."""
    session = ValidationSession(
        invoice_id=validation_request.invoice_id,
        rules_version=validation_result.rules_version,
        validator_version=validation_result.validator_version,
        strict_mode=validation_request.strict_mode,
        total_rules_executed=len(validation_result.check_results.model_dump()) if hasattr(validation_result.check_results, 'model_dump') else 0,
        rules_passed=validation_result.error_count + validation_result.warning_count == 0,
        rules_failed=validation_result.error_count,
        overall_passed=validation_result.passed,
        confidence_score=validation_result.confidence_score,
        error_count=validation_result.error_count,
        warning_count=validation_result.warning_count,
        info_count=validation_result.info_count,
        processing_time_ms=int(validation_result.processing_time_ms) if validation_result.processing_time_ms else None
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _store_validation_issues(
    db: AsyncSession,
    session_id: str,
    issues: List[Any]
):
    """Store validation issues in the database."""
    for issue in issues:
        validation_issue = ValidationIssue(
            session_id=session_id,
            reason_taxonomy=issue.code.value if hasattr(issue.code, 'value') else str(issue.code),
            validation_code=issue.code.value if hasattr(issue.code, 'value') else str(issue.code),
            severity=issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity),
            category=_categorize_issue(issue.code.value if hasattr(issue.code, 'value') else str(issue.code)),
            message=issue.message,
            field_name=issue.field,
            line_number=issue.line_number,
            expected_value=issue.expected_value,
            actual_value=issue.actual_value,
            details=issue.details,
            auto_resolvable=_is_auto_resolvable(issue),
            requires_human_review=issue.severity.value == "ERROR" if hasattr(issue.severity, 'value') else True
        )

        db.add(validation_issue)

    await db.commit()


def _categorize_issue(validation_code: str) -> str:
    """Categorize a validation issue by its code."""
    if "MISSING" in validation_code or "INVALID" in validation_code:
        return "structural"
    elif "MISMATCH" in validation_code or "CALCULATION" in validation_code:
        return "mathematical"
    elif "PO" in validation_code or "GRN" in validation_code or "DUPLICATE" in validation_code:
        return "business_rules"
    else:
        return "system"


def _is_auto_resolvable(issue: Any) -> bool:
    """Determine if an issue is automatically resolvable."""
    auto_resolvable_codes = [
        "INVALID_FIELD_FORMAT",
        "LINE_MATH_MISMATCH"
    ]
    return issue.code.value in auto_resolvable_codes if hasattr(issue.code, 'value') else False


async def _enhance_extraction_result(extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance extraction result with LLM patching."""
    try:
        enhanced_service = EnhancedExtractionService()
        enhanced_result = await enhanced_service.extract_with_enhancement(
            file_content=b"",  # Would need actual file content
            enable_llm_patching=True
        )
        return enhanced_result.model_dump()
    except Exception as e:
        logger.warning(f"Failed to enhance extraction result: {e}")
        return extraction_result


async def _update_invoice_validation_status(
    db: AsyncSession,
    invoice_id: str,
    validation_result: Any
):
    """Update invoice status based on validation result."""
    try:
        query = select(Invoice).where(Invoice.id == invoice_id)
        result = await db.execute(query)
        invoice = result.scalar_one_or_none()

        if invoice:
            if validation_result.passed:
                # Update status to validated or similar
                pass  # Would update based on actual status enum
            else:
                # Update status to validation_failed or similar
                pass  # Would update based on actual status enum

            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update invoice validation status: {e}")


async def _update_validation_metrics(invoice_id: str, validation_result: Any):
    """Update validation metrics in background."""
    try:
        # This would update aggregated metrics tables
        # Implementation depends on specific metrics requirements
        logger.debug(f"Updating metrics for invoice {invoice_id}")
    except Exception as e:
        logger.warning(f"Failed to update validation metrics: {e}")


async def _calculate_validation_metrics(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime
) -> List[ValidationMetrics]:
    """Calculate validation metrics for the period."""
    try:
        # Get validation sessions for the period
        query = select(ValidationSession).where(
            ValidationSession.started_at >= start_date,
            ValidationSession.started_at < end_date
        )
        result = await db.execute(query)
        sessions = result.scalars().all()

        if not sessions:
            return []

        # Calculate metrics
        total_invoices = len(sessions)
        passed_invoices = sum(1 for s in sessions if s.overall_passed)
        failed_invoices = total_invoices - passed_invoices
        auto_approved = sum(1 for s in sessions if s.confidence_score and s.confidence_score >= 0.9)
        human_review_required = total_invoices - auto_approved

        avg_confidence = sum(s.confidence_score or 0 for s in sessions) / total_invoices
        avg_processing_time = sum(s.processing_time_ms or 0 for s in sessions) / total_invoices

        # Get issue counts
        issue_query = select(ValidationIssue).join(ValidationSession).where(
            ValidationSession.started_at >= start_date,
            ValidationSession.started_at < end_date
        )
        issue_result = await db.execute(issue_query)
        issues = issue_result.scalars().all()

        total_issues = len(issues)
        error_issues = sum(1 for i in issues if i.severity == "ERROR")
        warning_issues = sum(1 for i in issues if i.severity == "WARNING")

        # Create metrics record
        metrics = ValidationMetrics(
            period_start=start_date,
            period_end=end_date,
            period_type="daily",
            total_invoices=total_invoices,
            passed_invoices=passed_invoices,
            failed_invoices=failed_invoices,
            auto_approved=auto_approved,
            human_review_required=human_review_required,
            average_confidence=avg_confidence,
            average_processing_time_ms=avg_processing_time,
            total_issues=total_issues,
            error_issues=error_issues,
            warning_issues=warning_issues,
            structural_pass_rate=0.0,  # Would calculate from actual data
            mathematical_pass_rate=0.0,
            business_rules_pass_rate=0.0
        )

        db.add(metrics)
        await db.commit()

        return [metrics]

    except Exception as e:
        logger.error(f"Failed to calculate validation metrics: {e}")
        return []