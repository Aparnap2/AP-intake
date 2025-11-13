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
                    "issues": [issue.model_dump() for issue in group],
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
        """Classify validation code into exception category with CFO-relevant insights."""
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

    def _generate_cfo_insights(
        self,
        category: ExceptionCategory,
        code: ValidationCode,
        invoice_data: Optional[Dict[str, Any]] = None,
        severity: ExceptionSeverity = ExceptionSeverity.ERROR
    ) -> Dict[str, Any]:
        """
        Generate CFO-relevant insights for exception analysis.

        This method provides executive-level insights about the financial and operational
        impact of exceptions, helping CFOs make informed decisions about resource
        allocation and process improvements.
        """
        # Base insights structure
        insights = {
            "executive_summary": {
                "impact_level": self._categorize_executive_impact(category, severity),
                "financial_risk": self._assess_financial_risk(category, code, invoice_data),
                "operational_impact": self._assess_operational_impact(category),
                "strategic_priority": self._determine_strategic_priority(category, severity),
            },
            "financial_analysis": {
                "working_capital_impact": self._calculate_wc_impact(category, invoice_data),
                "cash_flow_implications": self._assess_cash_flow_impact(category, invoice_data),
                "cost_of_resolution": self._estimate_resolution_cost(category, severity),
                "potential_savings": self._calculate_potential_savings(category, invoice_data),
            },
            "risk_assessment": {
                "duplicate_payment_risk": self._assess_duplicate_payment_risk(category, code),
                "compliance_risk": self._assess_compliance_risk(category, code),
                "vendor_relationship_risk": self._assess_vendor_risk(category, code),
                "audit_risk": self._assess_audit_risk(category, code),
            },
            "operational_insights": {
                "department_responsibility": self._assign_department_responsibility(category),
                "process_breakdown": self._identify_process_breakdown(category),
                "staff_training_needs": self._identify_training_needs(category),
                "technology_requirements": self._identify_technology_needs(category),
            },
            "actionable_recommendations": self._generate_cfo_recommendations(category, code, severity),
            "kpi_impact": {
                "days_sales_outstanding": self._assess_dso_impact(category),
                "payment_cycle_efficiency": self._assess_payment_cycle_impact(category),
                "cost_to_serve": self._assess_cost_to_serve_impact(category),
                "vendor_performance": self._assess_vendor_performance_impact(category),
            },
            "investment_justification": {
                "automation_roi": self._calculate_automation_roi(category),
                "staff_training_roi": self._calculate_training_roi(category),
                "technology_investment_roi": self._calculate_tech_investment_roi(category),
                "process_improvement_roi": self._calculate_process_improvement_roi(category),
            }
        }

        return insights

    def _categorize_executive_impact(
        self, category: ExceptionCategory, severity: ExceptionSeverity
    ) -> str:
        """Categorize executive impact level."""
        impact_matrix = {
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.ERROR): "critical",
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.WARNING): "high",
            (ExceptionCategory.MATH, ExceptionSeverity.ERROR): "high",
            (ExceptionCategory.MATH, ExceptionSeverity.WARNING): "medium",
            (ExceptionCategory.MATCHING, ExceptionSeverity.ERROR): "high",
            (ExceptionCategory.MATCHING, ExceptionSeverity.WARNING): "medium",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.ERROR): "high",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.WARNING): "medium",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.ERROR): "medium",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.WARNING): "low",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.ERROR): "medium",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.WARNING): "low",
        }

        return impact_matrix.get((category, severity), "low")

    def _assess_financial_risk(
        self,
        category: ExceptionCategory,
        code: ValidationCode,
        invoice_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess financial risk level and impact."""
        risk_levels = {
            ExceptionCategory.DUPLICATE: {
                "level": "critical",
                "potential_loss_percentage": 100,  # Full invoice value
                "working_capital_tied_up": True,
                "explanation": "Duplicate payments directly impact cash flow and working capital"
            },
            ExceptionCategory.MATH: {
                "level": "high",
                "potential_loss_percentage": 15,  # Average overpayment
                "working_capital_tied_up": False,
                "explanation": "Calculation errors typically result in overpayments"
            },
            ExceptionCategory.MATCHING: {
                "level": "medium",
                "potential_loss_percentage": 8,  # Disputed amounts
                "working_capital_tied_up": True,
                "explanation": "Matching failures delay payments and affect cash flow"
            },
            ExceptionCategory.VENDOR_POLICY: {
                "level": "medium",
                "potential_loss_percentage": 5,  # Penalties/fines
                "working_capital_tied_up": False,
                "explanation": "Policy violations may result in compliance costs"
            },
            ExceptionCategory.DATA_QUALITY: {
                "level": "low",
                "potential_loss_percentage": 2,  # Processing costs
                "working_capital_tied_up": False,
                "explanation": "Data quality issues primarily affect operational efficiency"
            },
            ExceptionCategory.SYSTEM: {
                "level": "medium",
                "potential_loss_percentage": 3,  # System downtime costs
                "working_capital_tied_up": True,
                "explanation": "System issues can delay payment processing"
            }
        }

        base_risk = risk_levels.get(category, risk_levels[ExceptionCategory.DATA_QUALITY])

        # Calculate actual financial impact if invoice data available
        if invoice_data and "total_amount" in invoice_data:
            invoice_total = float(invoice_data["total_amount"])
            potential_loss = invoice_total * (base_risk["potential_loss_percentage"] / 100)
            base_risk["estimated_financial_impact"] = potential_loss
            base_risk["invoice_amount"] = invoice_total

        return base_risk

    def _assess_operational_impact(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Assess operational impact of exception category."""
        impact_mapping = {
            ExceptionCategory.DUPLICATE: {
                "staff_hours_per_exception": 4,
                "departments_involved": ["AP", "Finance", "Procurement"],
                "approval_required": True,
                "vendor_communication_needed": True,
                "complexity": "high"
            },
            ExceptionCategory.MATH: {
                "staff_hours_per_exception": 1,
                "departments_involved": ["AP", "Finance"],
                "approval_required": False,
                "vendor_communication_needed": False,
                "complexity": "low"
            },
            ExceptionCategory.MATCHING: {
                "staff_hours_per_exception": 3,
                "departments_involved": ["AP", "Procurement", "Receiving"],
                "approval_required": True,
                "vendor_communication_needed": True,
                "complexity": "medium"
            },
            ExceptionCategory.VENDOR_POLICY: {
                "staff_hours_per_exception": 2,
                "departments_involved": ["AP", "Legal", "Procurement"],
                "approval_required": True,
                "vendor_communication_needed": True,
                "complexity": "medium"
            },
            ExceptionCategory.DATA_QUALITY: {
                "staff_hours_per_exception": 1,
                "departments_involved": ["AP", "Data Management"],
                "approval_required": False,
                "vendor_communication_needed": False,
                "complexity": "low"
            },
            ExceptionCategory.SYSTEM: {
                "staff_hours_per_exception": 2,
                "departments_involved": ["AP", "IT"],
                "approval_required": False,
                "vendor_communication_needed": False,
                "complexity": "medium"
            }
        }

        return impact_mapping.get(category, impact_mapping[ExceptionCategory.DATA_QUALITY])

    def _determine_strategic_priority(
        self, category: ExceptionCategory, severity: ExceptionSeverity
    ) -> str:
        """Determine strategic priority for exception category."""
        priority_matrix = {
            ExceptionCategory.DUPLICATE: "critical",
            ExceptionCategory.MATH: "high",
            ExceptionCategory.MATCHING: "high",
            ExceptionCategory.VENDOR_POLICY: "medium",
            ExceptionCategory.DATA_QUALITY: "medium",
            ExceptionCategory.SYSTEM: "low",
        }

        base_priority = priority_matrix.get(category, "medium")

        # Adjust based on severity
        if severity == ExceptionSeverity.ERROR:
            return base_priority
        elif severity == ExceptionSeverity.WARNING:
            return self._reduce_priority(base_priority)
        else:
            return self._reduce_priority(self._reduce_priority(base_priority))

    def _reduce_priority(self, priority: str) -> str:
        """Reduce priority level by one level."""
        priority_hierarchy = ["critical", "high", "medium", "low"]
        current_index = priority_hierarchy.index(priority)
        return priority_hierarchy[min(current_index + 1, len(priority_hierarchy) - 1)]

    def _calculate_wc_impact(
        self, category: ExceptionCategory, invoice_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate working capital impact."""
        if not invoice_data:
            return {
                "impact_days": 0,
                "capital_tied": 0,
                "cost_of_capital": 0,
                "daily_impact": 0
            }

        invoice_amount = float(invoice_data.get("total_amount", 0))

        impact_scenarios = {
            ExceptionCategory.DUPLICATE: {
                "impact_days": 45,  # Average days to resolve duplicate
                "capital_percentage": 100,  # Full amount tied up
            },
            ExceptionCategory.MATH: {
                "impact_days": 2,
                "capital_percentage": 15,  # Overpayment amount
            },
            ExceptionCategory.MATCHING: {
                "impact_days": 14,
                "capital_percentage": 100,  # Full amount delayed
            },
            ExceptionCategory.VENDOR_POLICY: {
                "impact_days": 7,
                "capital_percentage": 100,  # Full amount delayed
            },
            ExceptionCategory.DATA_QUALITY: {
                "impact_days": 1,
                "capital_percentage": 0,  # No direct WC impact
            },
            ExceptionCategory.SYSTEM: {
                "impact_days": 3,
                "capital_percentage": 100,  # Processing delay
            }
        }

        scenario = impact_scenarios.get(category, impact_scenarios[ExceptionCategory.DATA_QUALITY])
        capital_tied = invoice_amount * (scenario["capital_percentage"] / 100)
        cost_of_capital = capital_tied * 0.08 * (scenario["impact_days"] / 365)  # 8% annual cost
        daily_impact = cost_of_capital / scenario["impact_days"] if scenario["impact_days"] > 0 else 0

        return {
            "impact_days": scenario["impact_days"],
            "capital_tied": capital_tied,
            "cost_of_capital": cost_of_capital,
            "daily_impact": daily_impact,
            "invoice_amount": invoice_amount
        }

    def _assess_cash_flow_impact(
        self, category: ExceptionCategory, invoice_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess cash flow implications."""
        wc_impact = self._calculate_wc_impact(category, invoice_data)

        return {
            "immediate_impact": wc_impact["capital_tied"],
            "delayed_payment_risk": category in [ExceptionCategory.MATCHING, ExceptionCategory.VENDOR_POLICY],
            "forecast_accuracy_impact": category in [ExceptionCategory.DUPLICATE, ExceptionCategory.MATH],
            "liquidity_impact": wc_impact["daily_impact"] > 100,  # Significant daily impact
            "payment_cycle_extension": wc_impact["impact_days"]
        }

    def _estimate_resolution_cost(
        self, category: ExceptionCategory, severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Estimate cost of resolution."""
        base_costs = {
            ExceptionCategory.DUPLICATE: 250,
            ExceptionCategory.MATH: 50,
            ExceptionCategory.MATCHING: 150,
            ExceptionCategory.VENDOR_POLICY: 100,
            ExceptionCategory.DATA_QUALITY: 25,
            ExceptionCategory.SYSTEM: 75,
        }

        severity_multipliers = {
            ExceptionSeverity.ERROR: 1.5,
            ExceptionSeverity.WARNING: 1.0,
            ExceptionSeverity.INFO: 0.5,
        }

        base_cost = base_costs.get(category, 50)
        severity_multiplier = severity_multipliers.get(severity, 1.0)
        total_cost = base_cost * severity_multiplier

        return {
            "base_cost": base_cost,
            "severity_multiplier": severity_multiplier,
            "estimated_total_cost": total_cost,
            "staff_cost_component": total_cost * 0.6,  # 60% staff cost
            "system_cost_component": total_cost * 0.3,  # 30% system cost
            "other_cost_component": total_cost * 0.1,  # 10% other costs
        }

    def _calculate_potential_savings(
        self, category: ExceptionCategory, invoice_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate potential savings from resolving exceptions."""
        wc_impact = self._calculate_wc_impact(category, invoice_data)
        resolution_cost = self._estimate_resolution_cost(category, ExceptionSeverity.ERROR)

        # Potential savings include avoiding WC costs and resolution costs
        potential_savings = wc_impact["cost_of_capital"] + resolution_cost["estimated_total_cost"]

        return {
            "working_capital_savings": wc_impact["cost_of_capital"],
            "operational_savings": resolution_cost["estimated_total_cost"],
            "total_potential_savings": potential_savings,
            "annualized_savings": potential_savings * 12,  # Assume monthly occurrence
            "roi_percentage": (potential_savings / resolution_cost["estimated_total_cost"] * 100) if resolution_cost["estimated_total_cost"] > 0 else 0
        }

    def _assess_duplicate_payment_risk(self, category: ExceptionCategory, code: ValidationCode) -> Dict[str, Any]:
        """Assess duplicate payment risk."""
        if category == ExceptionCategory.DUPLICATE:
            return {
                "risk_level": "critical",
                "probability": 0.95,
                "potential_loss": "full_invoice_amount",
                "mitigation": "immediate_hold_required"
            }
        elif category == ExceptionCategory.MATCHING:
            return {
                "risk_level": "medium",
                "probability": 0.3,
                "potential_loss": "partial_dispute",
                "mitigation": "enhanced_verification"
            }
        else:
            return {
                "risk_level": "low",
                "probability": 0.05,
                "potential_loss": "minimal",
                "mitigation": "standard_controls"
            }

    def _assess_compliance_risk(self, category: ExceptionCategory, code: ValidationCode) -> Dict[str, Any]:
        """Assess compliance risk."""
        high_compliance_risk = {
            ExceptionCategory.VENDOR_POLICY,
            ExceptionCategory.MATCHING,
        }

        if category in high_compliance_risk:
            return {
                "risk_level": "high",
                "regulatory_impact": True,
                "audit_findings_likely": True,
                "penalty_risk": "moderate"
            }
        else:
            return {
                "risk_level": "low",
                "regulatory_impact": False,
                "audit_findings_likely": False,
                "penalty_risk": "minimal"
            }

    def _assess_vendor_risk(self, category: ExceptionCategory, code: ValidationCode) -> Dict[str, Any]:
        """Assess vendor relationship risk."""
        vendor_impact_categories = {
            ExceptionCategory.DUPLICATE,
            ExceptionCategory.MATCHING,
            ExceptionCategory.VENDOR_POLICY,
        }

        if category in vendor_impact_categories:
            return {
                "risk_level": "medium",
                "relationship_impact": True,
                "communication_required": True,
                "trust_impact": "moderate"
            }
        else:
            return {
                "risk_level": "low",
                "relationship_impact": False,
                "communication_required": False,
                "trust_impact": "minimal"
            }

    def _assess_audit_risk(self, category: ExceptionCategory, code: ValidationCode) -> Dict[str, Any]:
        """Assess audit risk."""
        audit_attention_categories = {
            ExceptionCategory.DUPLICATE,
            ExceptionCategory.VENDOR_POLICY,
            ExceptionCategory.MATCHING,
        }

        if category in audit_attention_categories:
            return {
                "risk_level": "medium",
                "audit_scrutiny_likely": True,
                "documentation_required": True,
                "materiality_level": "significant"
            }
        else:
            return {
                "risk_level": "low",
                "audit_scrutiny_likely": False,
                "documentation_required": False,
                "materiality_level": "minimal"
            }

    def _assign_department_responsibility(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Assign department responsibility."""
        responsibility_mapping = {
            ExceptionCategory.DUPLICATE: {
                "primary": "AP Operations",
                "secondary": ["Finance", "Procurement"],
                "escalation_path": ["AP Manager", "Finance Director", "CFO"]
            },
            ExceptionCategory.MATH: {
                "primary": "AP Operations",
                "secondary": ["Finance"],
                "escalation_path": ["AP Supervisor", "AP Manager"]
            },
            ExceptionCategory.MATCHING: {
                "primary": "Procurement",
                "secondary": ["AP Operations", "Receiving"],
                "escalation_path": ["Procurement Manager", "Operations Director"]
            },
            ExceptionCategory.VENDOR_POLICY: {
                "primary": "Procurement",
                "secondary": ["Legal", "AP Operations"],
                "escalation_path": ["Procurement Manager", "Legal Counsel", "CFO"]
            },
            ExceptionCategory.DATA_QUALITY: {
                "primary": "Data Management",
                "secondary": ["AP Operations", "IT"],
                "escalation_path": ["Data Manager", "IT Director"]
            },
            ExceptionCategory.SYSTEM: {
                "primary": "IT",
                "secondary": ["AP Operations"],
                "escalation_path": ["IT Manager", "CTO"]
            }
        }

        return responsibility_mapping.get(category, responsibility_mapping[ExceptionCategory.DATA_QUALITY])

    def _identify_process_breakdown(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Identify process breakdown points."""
        breakdown_mapping = {
            ExceptionCategory.DUPLICATE: {
                "breakdown_points": ["duplicate_detection", "invoice_validation", "payment_approval"],
                "root_causes": ["inadequate_controls", "manual_processes", "lack_of_real_time_detection"],
                "impact_assessment": "direct_financial_loss"
            },
            ExceptionCategory.MATH: {
                "breakdown_points": ["calculation_validation", "invoice_review"],
                "root_causes": ["manual_calculation", "inadequate_validation_rules"],
                "impact_assessment": "overpayment_risk"
            },
            ExceptionCategory.MATCHING: {
                "breakdown_points": ["po_matching", "receiving_verification", "three_way_match"],
                "root_causes": ["system_integration", "process_gaps", "data_synchronization"],
                "impact_assessment": "payment_delays"
            },
            ExceptionCategory.VENDOR_POLICY: {
                "breakdown_points": ["vendor_onboarding", "policy_enforcement", "compliance_check"],
                "root_causes": ["policy_gaps", "inadequate_vendor_vetting", "lack_of_controls"],
                "impact_assessment": "compliance_risk"
            },
            ExceptionCategory.DATA_QUALITY: {
                "breakdown_points": ["data_entry", "validation_rules", "quality_controls"],
                "root_causes": ["manual_data_entry", "inadequate_validation", "ocr_errors"],
                "impact_assessment": "operational_inefficiency"
            },
            ExceptionCategory.SYSTEM: {
                "breakdown_points": ["system_interfaces", "error_handling", "data_processing"],
                "root_causes": ["technical_issues", "system_limitations", "integration_problems"],
                "impact_assessment": "processing_delays"
            }
        }

        return breakdown_mapping.get(category, breakdown_mapping[ExceptionCategory.DATA_QUALITY])

    def _identify_training_needs(self, category: ExceptionCategory) -> List[str]:
        """Identify staff training needs."""
        training_mapping = {
            ExceptionCategory.DUPLICATE: [
                "Duplicate detection training",
                "Payment validation procedures",
                "Risk assessment protocols"
            ],
            ExceptionCategory.MATH: [
                "Calculation verification techniques",
                "Attention to detail training",
                "Validation rule application"
            ],
            ExceptionCategory.MATCHING: [
                "Three-way matching procedures",
                "PO management training",
                "Vendor communication skills"
            ],
            ExceptionCategory.VENDOR_POLICY: [
                "Compliance training",
                "Policy enforcement procedures",
                "Risk assessment methods"
            ],
            ExceptionCategory.DATA_QUALITY: [
                "Data entry best practices",
                "Quality control procedures",
                "System utilization training"
            ],
            ExceptionCategory.SYSTEM: [
                "System troubleshooting",
                "Error handling procedures",
                "Technical documentation review"
            ]
        }

        return training_mapping.get(category, ["General process training"])

    def _identify_technology_needs(self, category: ExceptionCategory) -> List[str]:
        """Identify technology investment needs."""
        tech_mapping = {
            ExceptionCategory.DUPLICATE: [
                "Advanced duplicate detection system",
                "Real-time payment validation",
                "Machine learning for pattern recognition"
            ],
            ExceptionCategory.MATH: [
                "Automated calculation validation",
                "Enhanced validation rules engine",
                "Mathematical verification tools"
            ],
            ExceptionCategory.MATCHING: [
                "Three-way matching automation",
                "PO integration improvements",
                "Receiving system integration"
            ],
            ExceptionCategory.VENDOR_POLICY: [
                "Policy compliance monitoring",
                "Vendor management system",
                "Automated rule enforcement"
            ],
            ExceptionCategory.DATA_QUALITY: [
                "Data quality monitoring tools",
                "Enhanced validation systems",
                "OCR improvement technology"
            ],
            ExceptionCategory.SYSTEM: [
                "System performance optimization",
                "Error handling improvements",
                "Integration platform enhancements"
            ]
        }

        return tech_mapping.get(category, ["System improvements"])

    def _generate_cfo_recommendations(
        self, category: ExceptionCategory, code: ValidationCode, severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Generate CFO-level recommendations."""
        immediate_actions = []
        strategic_initiatives = []
        investment_priorities = []

        # Category-specific recommendations
        if category == ExceptionCategory.DUPLICATE:
            immediate_actions = [
                "Implement immediate payment hold for suspected duplicates",
                "Conduct comprehensive vendor payment audit",
                "Escalate to Finance Director for review"
            ]
            strategic_initiatives = [
                "Invest in advanced duplicate detection technology",
                "Implement real-time payment validation controls",
                "Establish vendor payment verification protocols"
            ]
            investment_priorities = [
                "Machine learning duplicate detection system",
                "Automated payment validation platform",
                "Enhanced vendor management system"
            ]

        elif category == ExceptionCategory.MATH:
            immediate_actions = [
                "Review calculation validation procedures",
                "Implement pre-payment verification checks",
                "Staff training on calculation verification"
            ]
            strategic_initiatives = [
                "Automate calculation validation processes",
                "Enhance validation rules engine",
                "Implement quality control checkpoints"
            ]
            investment_priorities = [
                "Automated calculation validation system",
                "Enhanced validation rules platform",
                "Quality control monitoring tools"

            ]

        elif category == ExceptionCategory.MATCHING:
            immediate_actions = [
                "Review procurement-to-finance integration",
                "Implement enhanced three-way matching",
                "Strengthen vendor communication protocols"
            ]
            strategic_initiatives = [
                "Automate three-way matching processes",
                "Improve system integration between procurement and finance",
                "Implement real-time matching capabilities"
            ]
            investment_priorities = [
                "Three-way matching automation platform",
                "System integration improvements",
                "Real-time matching technology"
            ]

        elif category == ExceptionCategory.VENDOR_POLICY:
            immediate_actions = [
                "Review vendor compliance procedures",
                "Strengthen policy enforcement controls",
                "Update vendor onboarding processes"
            ]
            strategic_initiatives = [
                "Implement comprehensive vendor management system",
                "Establish automated policy compliance monitoring",
                "Enhance vendor risk assessment capabilities"
            ]
            investment_priorities = [
                "Vendor management platform",
                "Policy compliance monitoring system",
                "Risk assessment tools"
            ]

        elif category == ExceptionCategory.DATA_QUALITY:
            immediate_actions = [
                "Review data entry procedures",
                "Implement enhanced validation controls",
                "Staff training on data quality"
            ]
            strategic_initiatives = [
                "Invest in data quality monitoring tools",
                "Implement automated validation systems",
                "Enhance OCR and extraction technology"
            ]
            investment_priorities = [
                "Data quality monitoring platform",
                "Automated validation systems",
                "OCR technology improvements"
            ]

        elif category == ExceptionCategory.SYSTEM:
            immediate_actions = [
                "Review system error handling procedures",
                "Implement enhanced system monitoring",
                "Technical support review"
            ]
            strategic_initiatives = [
                "Optimize system performance and reliability",
                "Implement comprehensive error handling",
                "Enhance system integration capabilities"
            ]
            investment_priorities = [
                "System performance optimization",
                "Error handling improvements",
                "Integration platform enhancements"
            ]

        return {
            "immediate_actions": immediate_actions,
            "strategic_initiatives": strategic_initiatives,
            "investment_priorities": investment_priorities,
            "expected_roi": self._calculate_expected_roi(category),
            "implementation_timeline": self._estimate_implementation_timeline(category),
            "success_metrics": self._define_success_metrics(category)
        }

    def _calculate_expected_roi(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Calculate expected ROI for addressing exception category."""
        roi_mapping = {
            ExceptionCategory.DUPLICATE: {
                "annual_savings_potential": 50000,  # $50K annual savings
                "implementation_cost": 25000,  # $25K implementation cost
                "roi_percentage": 200,
                "payback_period_months": 6
            },
            ExceptionCategory.MATH: {
                "annual_savings_potential": 15000,
                "implementation_cost": 8000,
                "roi_percentage": 187,
                "payback_period_months": 5
            },
            ExceptionCategory.MATCHING: {
                "annual_savings_potential": 30000,
                "implementation_cost": 20000,
                "roi_percentage": 150,
                "payback_period_months": 8
            },
            ExceptionCategory.VENDOR_POLICY: {
                "annual_savings_potential": 20000,
                "implementation_cost": 15000,
                "roi_percentage": 133,
                "payback_period_months": 9
            },
            ExceptionCategory.DATA_QUALITY: {
                "annual_savings_potential": 12000,
                "implementation_cost": 10000,
                "roi_percentage": 120,
                "payback_period_months": 10
            },
            ExceptionCategory.SYSTEM: {
                "annual_savings_potential": 18000,
                "implementation_cost": 15000,
                "roi_percentage": 120,
                "payback_period_months": 10
            }
        }

        return roi_mapping.get(category, roi_mapping[ExceptionCategory.DATA_QUALITY])

    def _estimate_implementation_timeline(self, category: ExceptionCategory) -> Dict[str, str]:
        """Estimate implementation timeline for improvements."""
        timeline_mapping = {
            ExceptionCategory.DUPLICATE: {
                "quick_wins": "1-2 months",
                "system_implementation": "3-6 months",
                "full_automation": "6-12 months"
            },
            ExceptionCategory.MATH: {
                "quick_wins": "1 month",
                "system_implementation": "2-3 months",
                "full_automation": "3-6 months"
            },
            ExceptionCategory.MATCHING: {
                "quick_wins": "2-3 months",
                "system_implementation": "4-8 months",
                "full_automation": "8-15 months"
            },
            ExceptionCategory.VENDOR_POLICY: {
                "quick_wins": "1-2 months",
                "system_implementation": "3-5 months",
                "full_automation": "5-10 months"
            },
            ExceptionCategory.DATA_QUALITY: {
                "quick_wins": "1 month",
                "system_implementation": "2-4 months",
                "full_automation": "4-8 months"
            },
            ExceptionCategory.SYSTEM: {
                "quick_wins": "2-3 months",
                "system_implementation": "4-9 months",
                "full_automation": "9-18 months"
            }
        }

        return timeline_mapping.get(category, timeline_mapping[ExceptionCategory.DATA_QUALITY])

    def _define_success_metrics(self, category: ExceptionCategory) -> List[str]:
        """Define success metrics for improvements."""
        metrics_mapping = {
            ExceptionCategory.DUPLICATE: [
                "Reduction in duplicate payments by 95%",
                "Decrease in duplicate detection time by 80%",
                "Improvement in vendor satisfaction scores",
                "Reduction in manual review requirements"
            ],
            ExceptionCategory.MATH: [
                "Elimination of calculation errors",
                "Reduction in validation processing time by 60%",
                "Improvement in payment accuracy to 99.9%",
                "Reduction in staff correction time"
            ],
            ExceptionCategory.MATCHING: [
                "Increase in three-way match rate to 95%",
                "Reduction in matching exceptions by 80%",
                "Improvement in payment cycle time by 30%",
                "Reduction in manual intervention requirements"
            ],
            ExceptionCategory.VENDOR_POLICY: [
                "Achieve 100% policy compliance",
                "Reduction in policy violations by 90%",
                "Improvement in vendor onboarding efficiency",
                "Reduction in compliance-related delays"
            ],
            ExceptionCategory.DATA_QUALITY: [
                "Achieve 99% data quality accuracy",
                "Reduction in data-related exceptions by 85%",
                "Improvement in processing speed by 50%",
                "Reduction in manual data correction"
            ],
            ExceptionCategory.SYSTEM: [
                "Achieve 99.9% system uptime",
                "Reduction in system errors by 95%",
                "Improvement in processing speed by 40%",
                "Reduction in manual system interventions"
            ]
        }

        return metrics_mapping.get(category, metrics_mapping[ExceptionCategory.DATA_QUALITY])

    def _assess_dso_impact(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Assess Days Sales Outstanding impact."""
        dso_impacts = {
            ExceptionCategory.DUPLICATE: {
                "impact_level": "high",
                "days_increase": 5,
                "reason": "Duplicate investigations delay payment processing"
            },
            ExceptionCategory.MATH: {
                "impact_level": "low",
                "days_increase": 1,
                "reason": "Calculation corrections cause minor delays"
            },
            ExceptionCategory.MATCHING: {
                "impact_level": "medium",
                "days_increase": 3,
                "reason": "Matching failures delay payment approvals"
            },
            ExceptionCategory.VENDOR_POLICY: {
                "impact_level": "medium",
                "days_increase": 2,
                "reason": "Policy compliance reviews delay payments"
            },
            ExceptionCategory.DATA_QUALITY: {
                "impact_level": "low",
                "days_increase": 1,
                "reason": "Data corrections cause minimal delays"
            },
            ExceptionCategory.SYSTEM: {
                "impact_level": "medium",
                "days_increase": 2,
                "reason": "System issues delay processing"
            }
        }

        return dso_impacts.get(category, dso_impacts[ExceptionCategory.DATA_QUALITY])

    def _assess_payment_cycle_impact(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Assess payment cycle efficiency impact."""
        cycle_impacts = {
            ExceptionCategory.DUPLICATE: {
                "efficiency_reduction": 40,  # 40% reduction in efficiency
                "additional_processing_time": "3-5 days",
                "manual_intervention_required": True
            },
            ExceptionCategory.MATH: {
                "efficiency_reduction": 10,
                "additional_processing_time": "1-2 hours",
                "manual_intervention_required": False
            },
            ExceptionCategory.MATCHING: {
                "efficiency_reduction": 25,
                "additional_processing_time": "1-3 days",
                "manual_intervention_required": True
            },
            ExceptionCategory.VENDOR_POLICY: {
                "efficiency_reduction": 20,
                "additional_processing_time": "1-2 days",
                "manual_intervention_required": True
            },
            ExceptionCategory.DATA_QUALITY: {
                "efficiency_reduction": 15,
                "additional_processing_time": "2-4 hours",
                "manual_intervention_required": False
            },
            ExceptionCategory.SYSTEM: {
                "efficiency_reduction": 30,
                "additional_processing_time": "1-4 days",
                "manual_intervention_required": True
            }
        }

        return cycle_impacts.get(category, cycle_impacts[ExceptionCategory.DATA_QUALITY])

    def _assess_cost_to_serve_impact(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Assess cost to serve impact."""
        cost_impacts = {
            ExceptionCategory.DUPLICATE: {
                "additional_cost_per_exception": 250,
                "annual_cost_impact": 15000,  # Assuming 60 exceptions/year
                "cost_drivers": ["investigation_time", "vendor_communication", "management_review"]
            },
            ExceptionCategory.MATH: {
                "additional_cost_per_exception": 50,
                "annual_cost_impact": 3000,
                "cost_drivers": ["correction_time", "validation_review"]
            },
            ExceptionCategory.MATCHING: {
                "additional_cost_per_exception": 150,
                "annual_cost_impact": 9000,
                "cost_drivers": ["procurement_coordination", "vendor_communication", "documentation"]
            },
            ExceptionCategory.VENDOR_POLICY: {
                "additional_cost_per_exception": 100,
                "annual_cost_impact": 6000,
                "cost_drivers": ["compliance_review", "legal_consultation", "policy_enforcement"]
            },
            ExceptionCategory.DATA_QUALITY: {
                "additional_cost_per_exception": 25,
                "annual_cost_impact": 2000,
                "cost_drivers": ["data_correction", "quality_control", "revalidation"]
            },
            ExceptionCategory.SYSTEM: {
                "additional_cost_per_exception": 75,
                "annual_cost_impact": 4500,
                "cost_drivers": ["troubleshooting", "system_downtime", "manual_workarounds"]
            }
        }

        return cost_impacts.get(category, cost_impacts[ExceptionCategory.DATA_QUALITY])

    def _assess_vendor_performance_impact(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Assess vendor performance impact."""
        vendor_impacts = {
            ExceptionCategory.DUPLICATE: {
                "relationship_impact": "negative",
                "payment_reliability_affected": True,
                "communication_required": True,
                "trust_level_reduction": "significant"
            },
            ExceptionCategory.MATH: {
                "relationship_impact": "neutral",
                "payment_reliability_affected": False,
                "communication_required": False,
                "trust_level_reduction": "minimal"
            },
            ExceptionCategory.MATCHING: {
                "relationship_impact": "mixed",
                "payment_reliability_affected": True,
                "communication_required": True,
                "trust_level_reduction": "moderate"
            },
            ExceptionCategory.VENDOR_POLICY: {
                "relationship_impact": "negative",
                "payment_reliability_affected": True,
                "communication_required": True,
                "trust_level_reduction": "moderate"
            },
            ExceptionCategory.DATA_QUALITY: {
                "relationship_impact": "neutral",
                "payment_reliability_affected": False,
                "communication_required": False,
                "trust_level_reduction": "minimal"
            },
            ExceptionCategory.SYSTEM: {
                "relationship_impact": "neutral",
                "payment_reliability_affected": True,
                "communication_required": False,
                "trust_level_reduction": "minimal"
            }
        }

        return vendor_impacts.get(category, vendor_impacts[ExceptionCategory.DATA_QUALITY])

    def _calculate_automation_roi(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Calculate ROI for automation investments."""
        automation_rois = {
            ExceptionCategory.DUPLICATE: {
                "automation_potential": 95,  # 95% automation possible
                "implementation_cost": 50000,
                "annual_savings": 120000,
                "roi_percentage": 240,
                "payback_months": 5
            },
            ExceptionCategory.MATH: {
                "automation_potential": 90,
                "implementation_cost": 15000,
                "annual_savings": 35000,
                "roi_percentage": 233,
                "payback_months": 5
            },
            ExceptionCategory.MATCHING: {
                "automation_potential": 85,
                "implementation_cost": 40000,
                "annual_savings": 80000,
                "roi_percentage": 200,
                "payback_months": 6
            },
            ExceptionCategory.VENDOR_POLICY: {
                "automation_potential": 80,
                "implementation_cost": 25000,
                "annual_savings": 50000,
                "roi_percentage": 200,
                "payback_months": 6
            },
            ExceptionCategory.DATA_QUALITY: {
                "automation_potential": 75,
                "implementation_cost": 20000,
                "annual_savings": 35000,
                "roi_percentage": 175,
                "payback_months": 7
            },
            ExceptionCategory.SYSTEM: {
                "automation_potential": 70,
                "implementation_cost": 35000,
                "annual_savings": 60000,
                "roi_percentage": 171,
                "payback_months": 7
            }
        }

        return automation_rois.get(category, automation_rois[ExceptionCategory.DATA_QUALITY])

    def _calculate_training_roi(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Calculate ROI for staff training investments."""
        training_rois = {
            ExceptionCategory.DUPLICATE: {
                "training_cost": 5000,
                "annual_savings": 20000,
                "roi_percentage": 400,
                "payback_months": 3
            },
            ExceptionCategory.MATH: {
                "training_cost": 2000,
                "annual_savings": 8000,
                "roi_percentage": 400,
                "payback_months": 3
            },
            ExceptionCategory.MATCHING: {
                "training_cost": 4000,
                "annual_savings": 15000,
                "roi_percentage": 375,
                "payback_months": 3
            },
            ExceptionCategory.VENDOR_POLICY: {
                "training_cost": 3000,
                "annual_savings": 12000,
                "roi_percentage": 400,
                "payback_months": 3
            },
            ExceptionCategory.DATA_QUALITY: {
                "training_cost": 2500,
                "annual_savings": 10000,
                "roi_percentage": 400,
                "payback_months": 3
            },
            ExceptionCategory.SYSTEM: {
                "training_cost": 3500,
                "annual_savings": 14000,
                "roi_percentage": 400,
                "payback_months": 3
            }
        }

        return training_rois.get(category, training_rois[ExceptionCategory.DATA_QUALITY])

    def _calculate_tech_investment_roi(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Calculate ROI for technology investments."""
        tech_rois = {
            ExceptionCategory.DUPLICATE: {
                "tech_investment": 75000,
                "annual_savings": 180000,
                "roi_percentage": 240,
                "payback_months": 5
            },
            ExceptionCategory.MATH: {
                "tech_investment": 25000,
                "annual_savings": 60000,
                "roi_percentage": 240,
                "payback_months": 5
            },
            ExceptionCategory.MATCHING: {
                "tech_investment": 60000,
                "annual_savings": 120000,
                "roi_percentage": 200,
                "payback_months": 6
            },
            ExceptionCategory.VENDOR_POLICY: {
                "tech_investment": 40000,
                "annual_savings": 80000,
                "roi_percentage": 200,
                "payback_months": 6
            },
            ExceptionCategory.DATA_QUALITY: {
                "tech_investment": 30000,
                "annual_savings": 55000,
                "roi_percentage": 183,
                "payback_months": 7
            },
            ExceptionCategory.SYSTEM: {
                "tech_investment": 50000,
                "annual_savings": 90000,
                "roi_percentage": 180,
                "payback_months": 7
            }
        }

        return tech_rois.get(category, tech_rois[ExceptionCategory.DATA_QUALITY])

    def _calculate_process_improvement_roi(self, category: ExceptionCategory) -> Dict[str, Any]:
        """Calculate ROI for process improvement investments."""
        process_rois = {
            ExceptionCategory.DUPLICATE: {
                "process_improvement_cost": 15000,
                "annual_savings": 45000,
                "roi_percentage": 300,
                "payback_months": 4
            },
            ExceptionCategory.MATH: {
                "process_improvement_cost": 5000,
                "annual_savings": 15000,
                "roi_percentage": 300,
                "payback_months": 4
            },
            ExceptionCategory.MATCHING: {
                "process_improvement_cost": 12000,
                "annual_savings": 35000,
                "roi_percentage": 292,
                "payback_months": 4
            },
            ExceptionCategory.VENDOR_POLICY: {
                "process_improvement_cost": 8000,
                "annual_savings": 25000,
                "roi_percentage": 313,
                "payback_months": 4
            },
            ExceptionCategory.DATA_QUALITY: {
                "process_improvement_cost": 6000,
                "annual_savings": 18000,
                "roi_percentage": 300,
                "payback_months": 4
            },
            ExceptionCategory.SYSTEM: {
                "process_improvement_cost": 10000,
                "annual_savings": 30000,
                "roi_percentage": 300,
                "payback_months": 4
            }
        }

        return process_rois.get(category, process_rois[ExceptionCategory.DATA_QUALITY])

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

    async def create_cfo_grade_exception(
        self,
        invoice_id: str,
        validation_issues: List[ValidationIssue],
        invoice_data: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ) -> List[ExceptionResponse]:
        """
        Create CFO-graded exception records with enhanced financial insights.

        This method extends the standard exception creation process with CFO-level grading,
        business priority assessment, financial materiality evaluation, and working capital
        implications analysis.
        """
        logger.info(f"Creating CFO-graded exceptions for invoice {invoice_id} from {len(validation_issues)} validation issues")

        exceptions = []
        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._process_cfo_grade_exceptions(invoice_id, validation_issues, invoice_data, session)
        else:
            return await self._process_cfo_grade_exceptions(invoice_id, validation_issues, invoice_data, session)

    async def _process_cfo_grade_exceptions(
        self,
        invoice_id: str,
        validation_issues: List[ValidationIssue],
        invoice_data: Optional[Dict[str, Any]],
        session: AsyncSession
    ) -> List[ExceptionResponse]:
        """Process validation issues and create CFO-graded exception records."""
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

            # Generate CFO-grade insights
            cfo_insights = self._generate_cfo_insights(category, severity, invoice_data, group)

            # Save to database with CFO enhancements
            db_exception = ExceptionModel(
                id=uuid.uuid4(),
                invoice_id=uuid.UUID(invoice_id),
                reason_code=exception_data.reason_code,
                details_json={
                    "category": category.value,
                    "severity": severity.value,
                    "issues": [issue.model_dump() for issue in group],
                    "handler_data": exception_data.details,
                    "auto_resolution_possible": exception_data.auto_resolution_possible,
                    "suggested_actions": exception_data.suggested_actions,
                    # CFO-grade fields
                    "cfo_grade": cfo_insights["cfo_grade"],
                    "business_priority": cfo_insights["business_priority"],
                    "financial_materiality": cfo_insights["financial_materiality"],
                    "working_capital_impact": cfo_insights["working_capital_impact"],
                    "financial_impact_assessment": cfo_insights["financial_impact_assessment"],
                    "business_risk_level": cfo_insights["business_risk_level"],
                    "executive_summary": cfo_insights["executive_summary"],
                    "recommended_actions": cfo_insights["recommended_actions"],
                    "cfo_justification": cfo_insights["cfo_justification"]
                },
                resolved_at=None,
                resolved_by=None,
                resolution_notes=None,
            )

            session.add(db_exception)
            await session.flush()
            await session.refresh(db_exception)

            # Create response with CFO enhancements
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

        # Send enhanced notifications for CFO-graded exceptions
        await self._send_cfo_grade_notifications(exceptions, session)

        logger.info(f"Created {len(exceptions)} CFO-graded exceptions for invoice {invoice_id}")
        return exceptions

    def _generate_cfo_insights(
        self,
        category: ExceptionCategory,
        severity: ExceptionSeverity,
        invoice_data: Optional[Dict[str, Any]],
        issues: List[ValidationIssue]
    ) -> Dict[str, Any]:
        """
        Generate CFO-level insights for exception classification.

        This method provides executive-level classification and insights for
        business decision making and resource allocation.
        """
        # Determine CFO grade
        cfo_grade = self._assign_cfo_grade(category, severity)

        # Assess business priority
        business_priority = self._assess_business_priority(category, severity, invoice_data)

        # Evaluate financial materiality
        financial_materiality = self._evaluate_financial_materiality(category, severity, invoice_data)

        # Assess working capital impact
        working_capital_impact = self._assess_working_capital_impact(category, severity, invoice_data)

        # Generate financial impact assessment
        financial_impact_assessment = self._generate_financial_impact_assessment(category, severity, invoice_data)

        # Assess business risk level
        business_risk_level = self._assess_business_risk_level(category, severity, invoice_data)

        # Create executive summary
        executive_summary = self._create_executive_summary(category, severity, invoice_data)

        # Generate recommended actions
        recommended_actions = self._generate_cfo_recommended_actions(category, severity, invoice_data)

        # Provide CFO justification
        cfo_justification = self._provide_cfo_justification(category, severity, invoice_data, cfo_grade)

        return {
            "cfo_grade": cfo_grade,
            "business_priority": business_priority,
            "financial_materiality": financial_materiality,
            "working_capital_impact": working_capital_impact,
            "financial_impact_assessment": financial_impact_assessment,
            "business_risk_level": business_risk_level,
            "executive_summary": executive_summary,
            "recommended_actions": recommended_actions,
            "cfo_justification": cfo_justification
        }

    def _assign_cfo_grade(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Assign CFO grade based on category and severity."""
        # CFO grade matrix for executive prioritization
        grade_matrix = {
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.ERROR): "CRITICAL",
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.WARNING): "HIGH",
            (ExceptionCategory.MATH, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.MATH, ExceptionSeverity.WARNING): "MEDIUM",
            (ExceptionCategory.MATCHING, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.MATCHING, ExceptionSeverity.WARNING): "MEDIUM",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.WARNING): "MEDIUM",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.ERROR): "MEDIUM",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.WARNING): "LOW",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.ERROR): "MEDIUM",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.WARNING): "LOW",
        }

        return grade_matrix.get((category, severity), "LOW")

    def _assess_business_priority(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                invoice_data: Optional[Dict[str, Any]]) -> str:
        """Assess business priority for resource allocation."""
        base_priority = self._get_base_business_priority(category, severity)

        # Adjust based on invoice amount if available
        if invoice_data and "total_amount" in invoice_data:
            amount = float(invoice_data["total_amount"])
            if amount > 100000:  # High value invoice
                return self._elevate_priority(base_priority)
            elif amount > 10000:  # Medium value invoice
                return base_priority
            else:  # Low value invoice
                return self._maintain_priority(base_priority)

        return base_priority

    def _get_base_business_priority(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Get base business priority."""
        priority_matrix = {
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.ERROR): "CRITICAL",
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.WARNING): "HIGH",
            (ExceptionCategory.MATH, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.MATCHING, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.ERROR): "MEDIUM",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.ERROR): "MEDIUM",
        }
        return priority_matrix.get((category, severity), "MEDIUM")

    def _elevate_priority(self, current_priority: str) -> str:
        """Elevate priority by one level."""
        priority_hierarchy = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        current_index = priority_hierarchy.index(current_priority)
        return priority_hierarchy[min(current_index + 1, len(priority_hierarchy) - 1)]

    def _maintain_priority(self, current_priority: str) -> str:
        """Maintain current priority."""
        return current_priority

    def _evaluate_financial_materiality(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                      invoice_data: Optional[Dict[str, Any]]) -> str:
        """Evaluate financial materiality of exception."""
        if not invoice_data or "total_amount" not in invoice_data:
            return self._get_default_materiality(category, severity)

        amount = float(invoice_data["total_amount"])

        # Materiality thresholds
        if amount > 100000:
            return "MATERIAL"
        elif amount > 10000:
            return "MODERATE"
        else:
            return "LOW"

    def _get_default_materiality(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Get default materiality based on category and severity."""
        if category == ExceptionCategory.DUPLICATE:
            return "MATERIAL" if severity == ExceptionSeverity.ERROR else "MODERATE"
        elif severity == ExceptionSeverity.ERROR:
            return "MODERATE"
        else:
            return "LOW"

    def _assess_working_capital_impact(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                     invoice_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess working capital impact."""
        impact_matrix = {
            ExceptionCategory.DUPLICATE: {"level": "HIGH", "days_impacted": 45, "capital_tied_up": 1.0},
            ExceptionCategory.MATH: {"level": "LOW", "days_impacted": 2, "capital_tied_up": 0.15},
            ExceptionCategory.MATCHING: {"level": "MEDIUM", "days_impacted": 14, "capital_tied_up": 1.0},
            ExceptionCategory.VENDOR_POLICY: {"level": "MEDIUM", "days_impacted": 7, "capital_tied_up": 1.0},
            ExceptionCategory.DATA_QUALITY: {"level": "LOW", "days_impacted": 1, "capital_tied_up": 0.0},
            ExceptionCategory.SYSTEM: {"level": "MEDIUM", "days_impacted": 3, "capital_tied_up": 1.0},
        }

        base_impact = impact_matrix.get(category, impact_matrix[ExceptionCategory.DATA_QUALITY])

        # Calculate actual impact if invoice data available
        if invoice_data and "total_amount" in invoice_data:
            amount = float(invoice_data["total_amount"])
            capital_impacted = amount * base_impact["capital_tied_up"]
            daily_cost_of_capital = capital_impacted * 0.08 / 365  # 8% annual cost
            total_wc_cost = daily_cost_of_capital * base_impact["days_impacted"]

            return {
                **base_impact,
                "capital_impacted": capital_impacted,
                "daily_wc_cost": daily_cost_of_capital,
                "total_wc_cost": total_wc_cost,
                "impact_description": f"${total_wc_cost:,.2f} working capital cost over {base_impact['days_impacted']} days"
            }

        return base_impact

    def _generate_financial_impact_assessment(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                           invoice_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive financial impact assessment."""
        # Base impact percentages by category
        impact_percentages = {
            ExceptionCategory.DUPLICATE: 1.0,   # 100% potential loss
            ExceptionCategory.MATH: 0.15,      # 15% potential loss
            ExceptionCategory.MATCHING: 0.08,  # 8% potential loss
            ExceptionCategory.VENDOR_POLICY: 0.05,  # 5% potential loss
            ExceptionCategory.DATA_QUALITY: 0.02,   # 2% potential loss
            ExceptionCategory.SYSTEM: 0.03,    # 3% potential loss
        }

        base_percentage = impact_percentages.get(category, 0.02)
        severity_multiplier = 1.5 if severity == ExceptionSeverity.ERROR else 1.0

        if invoice_data and "total_amount" in invoice_data:
            amount = float(invoice_data["total_amount"])
            potential_loss = amount * base_percentage * severity_multiplier

            return {
                "potential_financial_loss": potential_loss,
                "loss_percentage": base_percentage * 100 * severity_multiplier,
                "confidence_level": "HIGH" if category == ExceptionCategory.DUPLICATE else "MEDIUM",
                "impact_description": f"Potential ${potential_loss:,.2f} financial impact",
                "materiality": "MATERIAL" if potential_loss > 10000 else "MODERATE" if potential_loss > 1000 else "LOW"
            }

        return {
            "potential_financial_loss": 0,
            "loss_percentage": base_percentage * 100 * severity_multiplier,
            "confidence_level": "MEDIUM",
            "impact_description": "Impact assessment pending invoice amount",
            "materiality": "TO_BE_DETERMINED"
        }

    def _assess_business_risk_level(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                  invoice_data: Optional[Dict[str, Any]]) -> str:
        """Assess overall business risk level."""
        risk_matrix = {
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.ERROR): "CRITICAL",
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.WARNING): "HIGH",
            (ExceptionCategory.MATH, ExceptionSeverity.ERROR): "MEDIUM",
            (ExceptionCategory.MATCHING, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.ERROR): "HIGH",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.ERROR): "MEDIUM",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.ERROR): "MEDIUM",
        }

        return risk_matrix.get((category, severity), "LOW")

    def _create_executive_summary(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                invoice_data: Optional[Dict[str, Any]]) -> str:
        """Create executive summary for CFO review."""
        category_descriptions = {
            ExceptionCategory.DUPLICATE: "Duplicate payment risk requiring immediate investigation",
            ExceptionCategory.MATH: "Calculation discrepancy that may result in overpayment",
            ExceptionCategory.MATCHING: "Document matching failure affecting payment timing",
            ExceptionCategory.VENDOR_POLICY: "Vendor policy compliance violation",
            ExceptionCategory.DATA_QUALITY: "Data quality issue affecting processing efficiency",
            ExceptionCategory.SYSTEM: "System processing error requiring technical intervention"
        }

        base_description = category_descriptions.get(category, "Exception requiring attention")

        if invoice_data and "total_amount" in invoice_data:
            amount = float(invoice_data["total_amount"])
            return f"{severity.value.title()} {base_description} involving ${amount:,.2f}"
        else:
            return f"{severity.value.title()} {base_description}"

    def _generate_cfo_recommended_actions(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                        invoice_data: Optional[Dict[str, Any]]) -> List[str]:
        """Generate CFO-level recommended actions."""
        action_matrix = {
            ExceptionCategory.DUPLICATE: [
                "Immediate payment hold on suspected duplicate invoice",
                "Comprehensive vendor payment audit for similar duplicates",
                "Review and strengthen duplicate detection controls",
                "Escalate to Finance Director for immediate review"
            ],
            ExceptionCategory.MATH: [
                "Review calculation validation procedures",
                "Implement pre-payment verification controls",
                "Staff training on calculation verification",
                "Enhance automated validation rules"
            ],
            ExceptionCategory.MATCHING: [
                "Review procurement-to-finance integration processes",
                "Strengthen three-way matching controls",
                "Vendor communication regarding documentation",
                "System integration improvement assessment"
            ],
            ExceptionCategory.VENDOR_POLICY: [
                "Vendor compliance review and policy enforcement",
                "Update vendor onboarding procedures",
                "Policy compliance monitoring enhancement",
                "Legal review of policy violations"
            ],
            ExceptionCategory.DATA_QUALITY: [
                "Data quality control process review",
                "Enhance validation rules and procedures",
                "Staff training on data entry standards",
                "Automated quality control implementation"
            ],
            ExceptionCategory.SYSTEM: [
                "Technical team assessment of system issues",
                "System reliability and performance review",
                "Error handling procedure enhancement",
                "Business continuity planning review"
            ]
        }

        return action_matrix.get(category, ["Standard exception resolution procedures"])

    def _provide_cfo_justification(self, category: ExceptionCategory, severity: ExceptionSeverity,
                                 invoice_data: Optional[Dict[str, Any]], cfo_grade: str) -> str:
        """Provide justification for CFO grade assignment."""
        justifications = {
            "CRITICAL": "Immediate financial risk requiring executive intervention and potential board notification",
            "HIGH": "Significant operational or financial impact requiring management attention and resource allocation",
            "MEDIUM": "Moderate impact requiring process improvement and monitoring",
            "LOW": "Minimal impact with standard resolution procedures and operational handling"
        }

        base_justification = justifications.get(cfo_grade, "Standard exception handling")

        category_context = {
            ExceptionCategory.DUPLICATE: "duplicate payment risk",
            ExceptionCategory.MATH: "calculation accuracy impact",
            ExceptionCategory.MATCHING: "payment processing efficiency",
            ExceptionCategory.VENDOR_POLICY: "compliance and relationship management",
            ExceptionCategory.DATA_QUALITY: "operational efficiency",
            ExceptionCategory.SYSTEM: "technical reliability"
        }

        context = category_context.get(category, "business operations")

        return f"{base_justification} based on {context} and {severity.value} severity level"

    async def _send_cfo_grade_notifications(self, exceptions: List[ExceptionResponse], session: AsyncSession) -> None:
        """Send enhanced notifications for CFO-graded exceptions."""
        critical_exceptions = [exc for exc in exceptions
                            if exc.severity == ExceptionSeverity.ERROR
                            or exc.category == ExceptionCategory.DUPLICATE]

        if not critical_exceptions:
            return

        # Enhanced notification logic for CFO-graded exceptions
        for exc in critical_exceptions:
            logger.info(f"CFO-GRADE NOTIFICATION: {exc.category.value} exception {exc.id} "
                       f"requires executive attention - Invoice: {exc.invoice_id}")

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