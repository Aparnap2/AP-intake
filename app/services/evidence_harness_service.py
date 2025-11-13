"""
Evidence Harness Service for Working Capital Copilot.

This service provides comprehensive seed data generation for training and testing
duplicate detection and exception handling systems with CFO-relevant insights.
"""

import asyncio
import hashlib
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import EvidenceHarnessException
from app.models.working_capital import (
    DuplicateType,
    ExceptionScenarioType,
    SeedDuplicateRecord,
    SeedExceptionRecord,
    EvidenceHarnessJob,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ar import ARInvoice
from app.services.deduplication_service import DeduplicationService
from app.services.exception_service import ExceptionService

logger = logging.getLogger(__name__)


class EvidenceHarnessService:
    """Comprehensive evidence harness service for seed data generation."""

    def __init__(self):
        """Initialize the evidence harness service."""
        self.deduplication_service = DeduplicationService()
        self.exception_service = ExceptionService()

        # Generation parameters
        self.default_duplicate_counts = {
            DuplicateType.EXACT: 15,
            DuplicateType.AMOUNT_SHIFT: 12,
            DuplicateType.DATE_SHIFT: 10,
            DuplicateType.FORMAT_CHANGE: 8,
            DuplicateType.VENDOR_VARIATION: 8,
            DuplicateType.INVOICE_NUMBER_VARIATION: 7,
        }

        self.default_exception_counts = {
            ExceptionScenarioType.MATH_ERROR: 8,
            ExceptionScenarioType.DUPLICATE_PAYMENT: 10,
            ExceptionScenarioType.MATCHING_FAILURE: 12,
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: 6,
            ExceptionScenarioType.DATA_QUALITY: 8,
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: 10,
            ExceptionScenarioType.INVALID_FORMAT: 6,
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: 8,
        }

    async def create_seed_duplicate_dataset(
        self,
        db: AsyncSession,
        target_count: int = 75,
        variation_types: Optional[List[DuplicateType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        job_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a comprehensive seed duplicate dataset.

        Args:
            db: Database session
            target_count: Target number of duplicate records to generate
            variation_types: Types of duplicates to generate
            start_date: Start date for base invoices
            end_date: End date for base invoices
            job_name: Name for the generation job

        Returns:
            Dictionary with generation results and statistics
        """
        if not job_name:
            job_name = f"Seed Duplicate Generation {datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Create job tracking
        job = EvidenceHarnessJob(
            job_name=job_name,
            job_type="duplicate_generation",
            target_count=target_count,
            parameters={
                "variation_types": [vt.value for vt in variation_types] if variation_types else None,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            }
        )
        db.add(job)
        await db.commit()

        try:
            job.start_job()
            logger.info(f"Starting seed duplicate generation: {job_name}")

            # Get base invoices for duplication
            base_invoices = await self._get_base_invoices_for_duplication(
                db, start_date, end_date, target_count
            )

            if not base_invoices:
                raise EvidenceHarnessException("No base invoices found for duplication")

            # Generate duplicates based on types
            if not variation_types:
                variation_types = list(DuplicateType)

            generated_duplicates = []
            total_generated = 0

            for duplicate_type in variation_types:
                type_count = self._calculate_type_count(
                    duplicate_type, target_count, len(variation_types)
                )

                logger.info(f"Generating {type_count} {duplicate_type.value} duplicates")

                for i in range(type_count):
                    if total_generated >= target_count:
                        break

                    base_invoice = random.choice(base_invoices)
                    duplicate_result = await self._generate_duplicate_record(
                        db, base_invoice, duplicate_type
                    )

                    if duplicate_result:
                        generated_duplicates.append(duplicate_result)
                        total_generated += 1

                        # Update job progress every 10 records
                        if total_generated % 10 == 0:
                            job.update_progress(generated=total_generated)
                            await db.commit()

            # Calculate quality metrics
            quality_metrics = await self._calculate_duplicate_quality_metrics(
                db, generated_duplicates
            )

            # Complete job
            job.update_progress(
                generated=total_generated,
                validated=quality_metrics["validated_count"],
                failed=quality_metrics["failed_count"]
            )
            job.average_quality_score = quality_metrics["average_quality_score"]
            job.diversity_score = quality_metrics["diversity_score"]
            job.coverage_score = quality_metrics["coverage_score"]
            job.complete_job(success=True)

            await db.commit()

            logger.info(f"Completed seed duplicate generation: {total_generated} records created")

            return {
                "job_id": str(job.id),
                "job_name": job_name,
                "total_generated": total_generated,
                "by_type": self._group_by_type(generated_duplicates),
                "quality_metrics": quality_metrics,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in seed duplicate generation: {str(e)}")
            job.complete_job(success=False, error_message=str(e))
            await db.commit()
            raise EvidenceHarnessException(f"Failed to generate seed duplicate dataset: {str(e)}")

    async def create_seed_exception_dataset(
        self,
        db: AsyncSession,
        target_count: int = 66,
        exception_types: Optional[List[ExceptionScenarioType]] = None,
        severity_distribution: Optional[Dict[str, int]] = None,
        job_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a comprehensive seed exception dataset.

        Args:
            db: Database session
            target_count: Target number of exception records to generate
            exception_types: Types of exceptions to generate
            severity_distribution: Distribution of exception severities
            job_name: Name for the generation job

        Returns:
            Dictionary with generation results and statistics
        """
        if not job_name:
            job_name = f"Seed Exception Generation {datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Create job tracking
        job = EvidenceHarnessJob(
            job_name=job_name,
            job_type="exception_generation",
            target_count=target_count,
            parameters={
                "exception_types": [et.value for et in exception_types] if exception_types else None,
                "severity_distribution": severity_distribution,
            }
        )
        db.add(job)
        await db.commit()

        try:
            job.start_job()
            logger.info(f"Starting seed exception generation: {job_name}")

            # Get base invoices for exception generation
            base_invoices = await self._get_base_invoices_for_exceptions(
                db, target_count
            )

            if not base_invoices:
                raise EvidenceHarnessException("No base invoices found for exception generation")

            # Generate exceptions based on types
            if not exception_types:
                exception_types = list(ExceptionScenarioType)

            if not severity_distribution:
                severity_distribution = {
                    "low": 20,
                    "medium": 35,
                    "high": 25,
                    "critical": 16,
                }

            generated_exceptions = []
            total_generated = 0

            for exception_type in exception_types:
                type_count = self._calculate_type_count(
                    exception_type, target_count, len(exception_types)
                )

                logger.info(f"Generating {type_count} {exception_type.value} exceptions")

                for i in range(type_count):
                    if total_generated >= target_count:
                        break

                    base_invoice = random.choice(base_invoices)
                    exception_result = await self._generate_exception_record(
                        db, base_invoice, exception_type, severity_distribution
                    )

                    if exception_result:
                        generated_exceptions.append(exception_result)
                        total_generated += 1

                        # Update job progress every 10 records
                        if total_generated % 10 == 0:
                            job.update_progress(generated=total_generated)
                            await db.commit()

            # Calculate quality metrics
            quality_metrics = await self._calculate_exception_quality_metrics(
                db, generated_exceptions
            )

            # Complete job
            job.update_progress(
                generated=total_generated,
                validated=quality_metrics["validated_count"],
                failed=quality_metrics["failed_count"]
            )
            job.average_quality_score = quality_metrics["average_quality_score"]
            job.diversity_score = quality_metrics["diversity_score"]
            job.coverage_score = quality_metrics["coverage_score"]
            job.complete_job(success=True)

            await db.commit()

            logger.info(f"Completed seed exception generation: {total_generated} records created")

            return {
                "job_id": str(job.id),
                "job_name": job_name,
                "total_generated": total_generated,
                "by_type": self._group_exceptions_by_type(generated_exceptions),
                "by_severity": self._group_exceptions_by_severity(generated_exceptions),
                "quality_metrics": quality_metrics,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in seed exception generation: {str(e)}")
            job.complete_job(success=False, error_message=str(e))
            await db.commit()
            raise EvidenceHarnessException(f"Failed to generate seed exception dataset: {str(e)}")

    async def _get_base_invoices_for_duplication(
        self,
        db: AsyncSession,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        target_count: int,
    ) -> List[ARInvoice]:
        """Get base invoices suitable for duplication scenarios."""
        query = select(ARInvoice).where(
            and_(
                ARInvoice.status == "active",
                ARInvoice.total_amount > 0,
            )
        )

        if start_date:
            query = query.where(ARInvoice.invoice_date >= start_date)
        if end_date:
            query = query.where(ARInvoice.invoice_date <= end_date)

        query = query.order_by(func.random()).limit(target_count * 2)  # Get more than needed

        result = await db.execute(query)
        return result.scalars().all()

    async def _get_base_invoices_for_exceptions(
        self,
        db: AsyncSession,
        target_count: int,
    ) -> List[ARInvoice]:
        """Get base invoices suitable for exception scenarios."""
        query = select(ARInvoice).where(
            and_(
                ARInvoice.status == "active",
                ARInvoice.total_amount > 0,
            )
        ).order_by(func.random()).limit(target_count * 2)

        result = await db.execute(query)
        return result.scalars().all()

    def _calculate_type_count(
        self,
        item_type: Union[DuplicateType, ExceptionScenarioType],
        target_count: int,
        num_types: int,
    ) -> int:
        """Calculate count for a specific type based on target and defaults."""
        if isinstance(item_type, DuplicateType):
            default_count = self.default_duplicate_counts.get(item_type, 10)
        else:
            default_count = self.default_exception_counts.get(item_type, 8)

        # Proportionally scale based on target count
        total_default = sum(
            self.default_duplicate_counts.values() if isinstance(item_type, DuplicateType)
            else self.default_exception_counts.values()
        )

        proportional_count = int((default_count / total_default) * target_count)
        return max(1, min(proportional_count, target_count // num_types))

    async def _generate_duplicate_record(
        self,
        db: AsyncSession,
        base_invoice: ARInvoice,
        duplicate_type: DuplicateType,
    ) -> Optional[SeedDuplicateRecord]:
        """Generate a duplicate record based on the specified type."""
        try:
            # Create duplicate invoice with variations
            duplicate_invoice = await self._create_duplicate_invoice(
                db, base_invoice, duplicate_type
            )

            if not duplicate_invoice:
                return None

            # Calculate similarity and working capital impact
            similarity_score = await self._calculate_similarity_score(
                base_invoice, duplicate_invoice, duplicate_type
            )

            working_capital_impact = await self._calculate_working_capital_impact(
                base_invoice, duplicate_invoice, duplicate_type
            )

            # Create seed duplicate record
            seed_duplicate = SeedDuplicateRecord(
                base_invoice_id=base_invoice.id,
                duplicate_invoice_id=duplicate_invoice.id,
                duplicate_type=duplicate_type,
                confidence_score=random.uniform(75, 95),
                similarity_score=similarity_score,
                working_capital_impact=working_capital_impact,
                detection_method=self._get_detection_method(duplicate_type),
                detection_confidence=random.uniform(70, 90),
                false_positive_risk=random.uniform(5, 25),
                is_labeled=True,
                labeled_by="evidence_harness",
                labeled_at=datetime.utcnow(),
                validation_status="validated",
                scenario_name=f"{duplicate_type.value}_{base_invoice.invoice_number[:8]}",
                scenario_description=self._get_scenario_description(duplicate_type),
                difficulty_level=self._get_difficulty_level(duplicate_type),
                business_context=self._get_business_context(duplicate_type),
            )

            db.add(seed_duplicate)
            await db.commit()

            return seed_duplicate

        except Exception as e:
            logger.error(f"Error generating duplicate record: {str(e)}")
            return None

    async def _create_duplicate_invoice(
        self,
        db: AsyncSession,
        base_invoice: ARInvoice,
        duplicate_type: DuplicateType,
    ) -> Optional[ARInvoice]:
        """Create a duplicate invoice with specified variations."""
        try:
            duplicate_invoice = ARInvoice(
                customer_id=base_invoice.customer_id,
                invoice_number=self._generate_duplicate_invoice_number(
                    base_invoice.invoice_number, duplicate_type
                ),
                invoice_date=self._generate_duplicate_invoice_date(
                    base_invoice.invoice_date, duplicate_type
                ),
                due_date=self._generate_duplicate_due_date(
                    base_invoice.due_date, base_invoice.invoice_date, duplicate_type
                ),
                total_amount=self._generate_duplicate_amount(
                    base_invoice.total_amount, duplicate_type
                ),
                status="pending",
                line_items=self._generate_duplicate_line_items(
                    base_invoice.line_items, duplicate_type
                ),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            db.add(duplicate_invoice)
            await db.commit()
            await db.refresh(duplicate_invoice)

            return duplicate_invoice

        except Exception as e:
            logger.error(f"Error creating duplicate invoice: {str(e)}")
            return None

    def _generate_duplicate_invoice_number(
        self, original_number: str, duplicate_type: DuplicateType
    ) -> str:
        """Generate duplicate invoice number based on type."""
        if duplicate_type == DuplicateType.EXACT:
            return original_number
        elif duplicate_type == DuplicateType.INVOICE_NUMBER_VARIATION:
            # Add prefix, suffix, or modify
            variations = [
                f"{original_number}-R",
                f"R-{original_number}",
                f"{original_number}REV",
                f"{original_number[:-1]}{random.randint(0, 9)}",
            ]
            return random.choice(variations)
        else:
            return original_number

    def _generate_duplicate_invoice_date(
        self, original_date: datetime, duplicate_type: DuplicateType
    ) -> datetime:
        """Generate duplicate invoice date based on type."""
        if duplicate_type == DuplicateType.DATE_SHIFT:
            # Shift by a few days
            days_shift = random.randint(-7, 7)
            return original_date + timedelta(days=days_shift)
        else:
            return original_date

    def _generate_duplicate_due_date(
        self, original_due: datetime, original_invoice: datetime, duplicate_type: DuplicateType
    ) -> datetime:
        """Generate duplicate due date based on type."""
        if duplicate_type == DuplicateType.DATE_SHIFT:
            # Shift by same amount as invoice date
            days_shift = random.randint(-7, 7)
            return original_due + timedelta(days=days_shift)
        else:
            return original_due

    def _generate_duplicate_amount(
        self, original_amount: Decimal, duplicate_type: DuplicateType
    ) -> Decimal:
        """Generate duplicate amount based on type."""
        if duplicate_type == DuplicateType.AMOUNT_SHIFT:
            # Small percentage variation
            percentage_change = Decimal(str(random.uniform(-0.05, 0.05)))  # ±5%
            return original_amount * (Decimal('1') + percentage_change)
        else:
            return original_amount

    def _generate_duplicate_line_items(
        self, original_items: List[Dict], duplicate_type: DuplicateType
    ) -> List[Dict]:
        """Generate duplicate line items based on type."""
        if duplicate_type == DuplicateType.FORMAT_CHANGE:
            # Reorder items, change descriptions slightly
            modified_items = []
            for item in original_items:
                modified_item = item.copy()
                if "description" in item:
                    # Slight description variations
                    variations = [
                        item["description"],
                        f"Rev: {item['description']}",
                        f"{item['description']} (Updated)",
                    ]
                    modified_item["description"] = random.choice(variations)
                modified_items.append(modified_item)

            # Randomly reorder
            random.shuffle(modified_items)
            return modified_items
        else:
            return original_items

    async def _calculate_similarity_score(
        self, base_invoice: ARInvoice, duplicate_invoice: ARInvoice, duplicate_type: DuplicateType
    ) -> Decimal:
        """Calculate similarity score between base and duplicate invoices."""
        if duplicate_type == DuplicateType.EXACT:
            return Decimal('100.0')

        similarity = Decimal('100.0')

        # Check invoice number similarity
        if base_invoice.invoice_number != duplicate_invoice.invoice_number:
            similarity -= Decimal('15.0')

        # Check date similarity
        date_diff = abs((base_invoice.invoice_date - duplicate_invoice.invoice_date).days)
        if date_diff > 0:
            similarity -= Decimal('10.0') * min(date_diff / 30, Decimal('1.0'))

        # Check amount similarity
        amount_diff = abs(base_invoice.total_amount - duplicate_invoice.total_amount)
        if amount_diff > 0:
            percentage_diff = amount_diff / base_invoice.total_amount
            similarity -= Decimal('25.0') * min(percentage_diff * 10, Decimal('1.0'))

        return max(Decimal('0.0'), similarity)

    async def _calculate_working_capital_impact(
        self, base_invoice: ARInvoice, duplicate_invoice: ARInvoice, duplicate_type: DuplicateType
    ) -> Decimal:
        """Calculate working capital impact of potential duplicate payment."""
        # For duplicates, the impact is typically the duplicate amount
        if duplicate_type == DuplicateType.EXACT:
            return abs(duplicate_invoice.total_amount)
        else:
            # For near-duplicates, calculate the potential overpayment
            return abs(duplicate_invoice.total_amount)

    def _get_detection_method(self, duplicate_type: DuplicateType) -> str:
        """Get the primary detection method for duplicate type."""
        method_mapping = {
            DuplicateType.EXACT: "hash",
            DuplicateType.AMOUNT_SHIFT: "business_rules",
            DuplicateType.DATE_SHIFT: "fuzzy",
            DuplicateType.FORMAT_CHANGE: "business_rules",
            DuplicateType.VENDOR_VARIATION: "fuzzy",
            DuplicateType.INVOICE_NUMBER_VARIATION: "fuzzy",
        }
        return method_mapping.get(duplicate_type, "business_rules")

    def _get_scenario_description(self, duplicate_type: DuplicateType) -> str:
        """Get scenario description for duplicate type."""
        descriptions = {
            DuplicateType.EXACT: "Exact duplicate invoice with identical data",
            DuplicateType.AMOUNT_SHIFT: "Duplicate with slight amount variation",
            DuplicateType.DATE_SHIFT: "Duplicate with shifted invoice date",
            DuplicateType.FORMAT_CHANGE: "Duplicate with changed formatting or layout",
            DuplicateType.VENDOR_VARIATION: "Duplicate with vendor name variation",
            DuplicateType.INVOICE_NUMBER_VARIATION: "Duplicate with modified invoice number",
        }
        return descriptions.get(duplicate_type, "Unknown duplicate scenario")

    def _get_difficulty_level(self, duplicate_type: DuplicateType) -> str:
        """Get difficulty level for detecting duplicate type."""
        difficulty_mapping = {
            DuplicateType.EXACT: "easy",
            DuplicateType.AMOUNT_SHIFT: "medium",
            DuplicateType.DATE_SHIFT: "medium",
            DuplicateType.FORMAT_CHANGE: "hard",
            DuplicateType.VENDOR_VARIATION: "hard",
            DuplicateType.INVOICE_NUMBER_VARIATION: "medium",
        }
        return difficulty_mapping.get(duplicate_type, "medium")

    def _get_business_context(self, duplicate_type: DuplicateType) -> Dict[str, Any]:
        """Get business context for duplicate type."""
        contexts = {
            DuplicateType.EXACT: {
                "common_causes": ["System resubmission", "Vendor error", "Multiple uploads"],
                "risk_level": "high",
                "department": "AP Operations"
            },
            DuplicateType.AMOUNT_SHIFT: {
                "common_causes": ["Tax calculation", "Rounding differences", "Partial payments"],
                "risk_level": "medium",
                "department": "Finance"
            },
            DuplicateType.DATE_SHIFT: {
                "common_causes": ["Date entry errors", "Time zone differences", "Period adjustments"],
                "risk_level": "medium",
                "department": "AP Operations"
            },
            DuplicateType.FORMAT_CHANGE: {
                "common_causes": ["System migration", "Template changes", "Export variations"],
                "risk_level": "high",
                "department": "Technical Support"
            },
            DuplicateType.VENDOR_VARIATION: {
                "common_causes": ["Vendor name changes", "DBA variations", "Merger/acquisition"],
                "risk_level": "high",
                "department": "Vendor Management"
            },
            DuplicateType.INVOICE_NUMBER_VARIATION: {
                "common_causes": ["Revisions", "Corrections", "System prefixes"],
                "risk_level": "medium",
                "department": "AP Operations"
            },
        }
        return contexts.get(duplicate_type, {})

    async def _generate_exception_record(
        self,
        db: AsyncSession,
        base_invoice: ARInvoice,
        exception_type: ExceptionScenarioType,
        severity_distribution: Dict[str, int],
    ) -> Optional[SeedExceptionRecord]:
        """Generate an exception record based on the specified type."""
        try:
            severity = self._select_severity(severity_distribution)

            # Generate exception details
            exception_details = self._generate_exception_details(base_invoice, exception_type)

            # Calculate financial impact
            financial_impact = self._calculate_exception_financial_impact(
                base_invoice, exception_type, severity
            )

            # Generate CFO insights
            cfo_insights = self._generate_cfo_insights(base_invoice, exception_type, financial_impact)

            # Create seed exception record
            seed_exception = SeedExceptionRecord(
                invoice_id=base_invoice.id,
                exception_type=exception_type,
                severity=severity,
                exception_details=exception_details,
                detection_rules=self._get_detection_rules(exception_type),
                business_impact=self._get_business_impact(exception_type, severity),
                financial_impact=financial_impact,
                resolution_cost=self._calculate_resolution_cost(exception_type, severity),
                opportunity_cost=self._calculate_opportunity_cost(exception_type, severity),
                cfo_insights=cfo_insights,
                risk_assessment=self._generate_risk_assessment(exception_type, severity),
                working_capital_implications=self._generate_wc_implications(exception_type),
                is_labeled=True,
                labeled_by="evidence_harness",
                labeled_at=datetime.utcnow(),
                validation_status="validated",
                scenario_name=f"{exception_type.value}_{base_invoice.invoice_number[:8]}",
                scenario_description=self._get_exception_scenario_description(exception_type),
                occurrence_frequency=self._get_occurrence_frequency(exception_type),
                resolution_complexity=self._get_resolution_complexity(exception_type),
                resolution_time_hours=self._estimate_resolution_time(exception_type, severity),
                resolution_success_rate=self._estimate_success_rate(exception_type, severity),
                repeat_occurrence=self._should_be_repeat_issue(exception_type),
            )

            db.add(seed_exception)
            await db.commit()

            return seed_exception

        except Exception as e:
            logger.error(f"Error generating exception record: {str(e)}")
            return None

    def _select_severity(self, severity_distribution: Dict[str, int]) -> str:
        """Select severity based on distribution."""
        severities = []
        weights = []

        for severity, weight in severity_distribution.items():
            severities.append(severity)
            weights.append(weight)

        return random.choices(severities, weights=weights)[0]

    def _generate_exception_details(
        self, invoice: ARInvoice, exception_type: ExceptionScenarioType
    ) -> Dict[str, Any]:
        """Generate exception details based on type."""
        details_templates = {
            ExceptionScenarioType.MATH_ERROR: {
                "error_type": "calculation_mismatch",
                "expected_total": float(invoice.total_amount + Decimal('100.00')),
                "actual_total": float(invoice.total_amount),
                "discrepancy": 100.00,
                "line_items_affected": random.randint(1, 3),
                "calculation_step": "line_item_summation"
            },
            ExceptionScenarioType.DUPLICATE_PAYMENT: {
                "error_type": "potential_duplicate",
                "duplicate_invoice_id": str(uuid4()),
                "duplicate_amount": float(invoice.total_amount),
                "duplicate_date": (invoice.invoice_date + timedelta(days=1)).isoformat(),
                "similarity_score": random.uniform(0.85, 0.98),
                "confidence_level": "high"
            },
            ExceptionScenarioType.MATCHING_FAILURE: {
                "error_type": "three_way_match_failure",
                "po_number": f"PO-{random.randint(10000, 99999)}",
                "receipt_mismatch": True,
                "quantity_variance": random.randint(-5, 5),
                "price_variance_percentage": random.uniform(-0.10, 0.10),
                "missing_goods_receipt": random.choice([True, False])
            },
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: {
                "error_type": "policy_violation",
                "violated_policy": "payment_terms",
                "required_terms": "NET 30",
                "actual_terms": "NET 60",
                "approval_required": True,
                "risk_level": "medium"
            },
            ExceptionScenarioType.DATA_QUALITY: {
                "error_type": "data_inconsistency",
                "field_affected": random.choice(["vendor_name", "tax_id", "address"]),
                "confidence_score": random.uniform(0.3, 0.7),
                "validation_errors": 2,
                "data_source": "ocr_extraction"
            },
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: {
                "error_type": "required_field_missing",
                "missing_fields": [random.choice(["purchase_order", "approval_code", "cost_center"])],
                "impact_on_processing": "blocks_approval",
                "can_be_derived": random.choice([True, False])
            },
            ExceptionScenarioType.INVALID_FORMAT: {
                "error_type": "format_validation_failure",
                "format_type": random.choice(["date", "currency", "invoice_number"]),
                "expected_format": "YYYY-MM-DD",
                "actual_format": "DD/MM/YYYY",
                "auto_correction_possible": random.choice([True, False])
            },
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: {
                "error_type": "business_rule_breach",
                "violated_rule": random.choice(["invoice_limit", "approval_hierarchy", "budget_exceeded"]),
                "rule_threshold": float(random.uniform(1000, 10000)),
                "actual_value": float(random.uniform(10000, 50000)),
                "excess_percentage": random.uniform(0.1, 0.5)
            },
        }

        return details_templates.get(exception_type, {"error_type": "unknown"})

    def _calculate_exception_financial_impact(
        self, invoice: ARInvoice, exception_type: ExceptionScenarioType, severity: str
    ) -> Decimal:
        """Calculate financial impact of exception."""
        base_impact = abs(invoice.total_amount)

        # Adjust based on exception type
        type_multipliers = {
            ExceptionScenarioType.MATH_ERROR: Decimal('0.05'),  # 5% of invoice amount
            ExceptionScenarioType.DUPLICATE_PAYMENT: Decimal('1.0'),  # Full invoice amount
            ExceptionScenarioType.MATCHING_FAILURE: Decimal('0.1'),  # 10% of invoice amount
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: Decimal('0.02'),  # 2% of invoice amount
            ExceptionScenarioType.DATA_QUALITY: Decimal('0.01'),  # 1% of invoice amount
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: Decimal('0.03'),  # 3% of invoice amount
            ExceptionScenarioType.INVALID_FORMAT: Decimal('0.01'),  # 1% of invoice amount
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: Decimal('0.15'),  # 15% of invoice amount
        }

        # Adjust based on severity
        severity_multipliers = {
            "low": Decimal('0.5'),
            "medium": Decimal('1.0'),
            "high": Decimal('2.0'),
            "critical": Decimal('5.0'),
        }

        type_multiplier = type_multipliers.get(exception_type, Decimal('0.1'))
        severity_multiplier = severity_multipliers.get(severity, Decimal('1.0'))

        return base_impact * type_multiplier * severity_multiplier

    def _generate_cfo_insights(
        self, invoice: ARInvoice, exception_type: ExceptionScenarioType, financial_impact: Decimal
    ) -> Dict[str, Any]:
        """Generate CFO-relevant insights."""
        return {
            "executive_summary": {
                "exception_type": exception_type.value,
                "financial_exposure": float(financial_impact),
                "working_capital_impact": float(financial_impact),
                "risk_category": self._get_risk_category(exception_type),
            },
            "cash_flow_impact": {
                "immediate_impact": float(financial_impact),
                "potential_savings": float(financial_impact * Decimal('0.8')),  # 80% can be recovered
                "timeline_to_resolution": self._get_resolution_timeline(exception_type),
            },
            "strategic_implications": {
                "process_improvement_opportunity": self._get_process_impact(exception_type),
                "technology_investment_needed": self._get_tech_investment(exception_type),
                "training_requirements": self._get_training_needs(exception_type),
            },
            "actionable_recommendations": self._get_cfo_recommendations(exception_type),
            "kpi_impact": {
                "days_sales_outstanding": self._get_dso_impact(exception_type),
                "payment_cycle_efficiency": self._get_payment_cycle_impact(exception_type),
                "cost_to_serve": self._get_cost_to_serve_impact(exception_type),
            }
        }

    def _get_risk_category(self, exception_type: ExceptionScenarioType) -> str:
        """Get risk category for exception type."""
        risk_mapping = {
            ExceptionScenarioType.MATH_ERROR: "financial_accuracy",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "payment_leakage",
            ExceptionScenarioType.MATCHING_FAILURE: "procurement_compliance",
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: "vendor_risk",
            ExceptionScenarioType.DATA_QUALITY: "data_integrity",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "process_compliance",
            ExceptionScenarioType.INVALID_FORMAT: "system_integration",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "governance",
        }
        return risk_mapping.get(exception_type, "general")

    def _get_detection_rules(self, exception_type: ExceptionScenarioType) -> Dict[str, Any]:
        """Get detection rules for exception type."""
        rules = {
            ExceptionScenarioType.MATH_ERROR: {
                "rule_name": "calculation_validation",
                "condition": "line_item_total != header_total",
                "threshold": 0.01,
            },
            ExceptionScenarioType.DUPLICATE_PAYMENT: {
                "rule_name": "duplicate_detection",
                "condition": "vendor + amount + date combination",
                "time_window": "30_days",
            },
            ExceptionScenarioType.MATCHING_FAILURE: {
                "rule_name": "three_way_match",
                "condition": "po != invoice or receipt != invoice",
                "tolerance": "5_percent",
            },
        }
        return rules.get(exception_type, {"rule_name": "generic_validation"})

    def _get_business_impact(self, exception_type: ExceptionScenarioType, severity: str) -> Dict[str, Any]:
        """Get business impact assessment."""
        return {
            "operational_impact": self._get_operational_impact(exception_type),
            "financial_risk": severity,
            "compliance_impact": self._get_compliance_impact(exception_type),
            "customer_impact": self._get_customer_impact(exception_type),
            "reputation_risk": self._get_reputation_risk(exception_type, severity),
        }

    def _calculate_resolution_cost(self, exception_type: ExceptionScenarioType, severity: str) -> Decimal:
        """Calculate resolution cost for exception."""
        base_costs = {
            ExceptionScenarioType.MATH_ERROR: Decimal('50'),
            ExceptionScenarioType.DUPLICATE_PAYMENT: Decimal('200'),
            ExceptionScenarioType.MATCHING_FAILURE: Decimal('100'),
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: Decimal('150'),
            ExceptionScenarioType.DATA_QUALITY: Decimal('75'),
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: Decimal('60'),
            ExceptionScenarioType.INVALID_FORMAT: Decimal('40'),
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: Decimal('120'),
        }

        severity_multipliers = {
            "low": Decimal('1.0'),
            "medium": Decimal('1.5'),
            "high": Decimal('2.5'),
            "critical": Decimal('5.0'),
        }

        base_cost = base_costs.get(exception_type, Decimal('100'))
        severity_multiplier = severity_multipliers.get(severity, Decimal('1.0'))

        return base_cost * severity_multiplier

    def _calculate_opportunity_cost(self, exception_type: ExceptionScenarioType, severity: str) -> Decimal:
        """Calculate opportunity cost for exception."""
        # Opportunity cost is typically the time value of money and staff time
        base_opportunity = Decimal('25')  # Base opportunity cost per hour

        # Estimate hours to resolve
        resolution_hours = {
            ExceptionScenarioType.MATH_ERROR: 2,
            ExceptionScenarioType.DUPLICATE_PAYMENT: 8,
            ExceptionScenarioType.MATCHING_FAILURE: 4,
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: 6,
            ExceptionScenarioType.DATA_QUALITY: 3,
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: 1,
            ExceptionScenarioType.INVALID_FORMAT: 1,
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: 5,
        }

        hours = resolution_hours.get(exception_type, 3)
        return base_opportunity * hours

    def _generate_risk_assessment(self, exception_type: ExceptionScenarioType, severity: str) -> Dict[str, Any]:
        """Generate risk assessment for exception."""
        return {
            "likelihood": self._get_likelihood(exception_type),
            "impact": severity,
            "risk_score": self._calculate_risk_score(exception_type, severity),
            "mitigation_strategy": self._get_mitigation_strategy(exception_type),
            "monitoring_required": self._get_monitoring_needs(exception_type),
        }

    def _generate_wc_implications(self, exception_type: ExceptionScenarioType) -> Dict[str, Any]:
        """Generate working capital implications."""
        return {
            "days_sales_outstanding_impact": self._get_dso_impact(exception_type),
            "cash_conversion_cycle_impact": self._get_ccc_impact(exception_type),
            "payment_terms_impact": self._get_payment_terms_impact(exception_type),
            "vendor_relationship_impact": self._get_vendor_impact(exception_type),
        }

    def _get_resolution_timeline(self, exception_type: ExceptionScenarioType) -> str:
        """Get typical resolution timeline."""
        timelines = {
            ExceptionScenarioType.MATH_ERROR: "1-2 days",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "3-5 days",
            ExceptionScenarioType.MATCHING_FAILURE: "2-4 days",
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: "5-7 days",
            ExceptionScenarioType.DATA_QUALITY: "2-3 days",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "1 day",
            ExceptionScenarioType.INVALID_FORMAT: "1 day",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "3-5 days",
        }
        return timelines.get(exception_type, "2-3 days")

    def _get_process_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get process improvement opportunity."""
        impacts = {
            ExceptionScenarioType.MATH_ERROR: "Implement automated validation",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "Enhance duplicate detection",
            ExceptionScenarioType.MATCHING_FAILURE: "Improve PO matching",
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: "Strengthen vendor onboarding",
            ExceptionScenarioType.DATA_QUALITY: "Improve data validation",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "Enhance field requirements",
            ExceptionScenarioType.INVALID_FORMAT: "Standardize formats",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "Implement business rules engine",
        }
        return impacts.get(exception_type, "Process review needed")

    def _get_tech_investment(self, exception_type: ExceptionScenarioType) -> str:
        """Get technology investment needed."""
        investments = {
            ExceptionScenarioType.MATH_ERROR: "Calculation validation engine",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "Advanced duplicate detection",
            ExceptionScenarioType.MATCHING_FAILURE: "Three-way matching automation",
            ExceptionScenarioType.DATA_QUALITY: "Data quality monitoring tools",
            ExceptionScenarioType.INVALID_FORMAT: "Format validation middleware",
        }
        return investments.get(exception_type, "System enhancements")

    def _get_training_needs(self, exception_type: ExceptionScenarioType) -> str:
        """Get training requirements."""
        needs = {
            ExceptionScenarioType.MATH_ERROR: "Financial validation training",
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: "Vendor management training",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "Compliance training",
        }
        return needs.get(exception_type, "General process training")

    def _get_cfo_recommendations(self, exception_type: ExceptionScenarioType) -> List[str]:
        """Get CFO-level recommendations."""
        recommendations = {
            ExceptionScenarioType.MATH_ERROR: [
                "Implement automated calculation validation",
                "Add pre-payment verification steps",
                "Review current calculation processes"
            ],
            ExceptionScenarioType.DUPLICATE_PAYMENT: [
                "Invest in advanced duplicate detection",
                "Implement real-time payment validation",
                "Establish vendor verification protocols"
            ],
            ExceptionScenarioType.MATCHING_FAILURE: [
                "Automate three-way matching process",
                "Improve procurement-to-finance integration",
                "Regular vendor communication protocols"
            ],
        }
        return recommendations.get(exception_type, ["Review and improve current processes"])

    def _get_dso_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get DSO impact."""
        impacts = {
            ExceptionScenarioType.DUPLICATE_PAYMENT: "Significant negative impact",
            ExceptionScenarioType.MATCHING_FAILURE: "Moderate negative impact",
            ExceptionScenarioType.MATH_ERROR: "Minor negative impact",
        }
        return impacts.get(exception_type, "Minimal impact")

    def _get_payment_cycle_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get payment cycle efficiency impact."""
        return self._get_dso_impact(exception_type)

    def _get_cost_to_serve_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get cost to serve impact."""
        impacts = {
            ExceptionScenarioType.DUPLICATE_PAYMENT: "High increase in cost to serve",
            ExceptionScenarioType.MATCHING_FAILURE: "Moderate increase in cost to serve",
            ExceptionScenarioType.DATA_QUALITY: "Low increase in cost to serve",
        }
        return impacts.get(exception_type, "Minimal impact")

    def _get_operational_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get operational impact."""
        impacts = {
            ExceptionScenarioType.DUPLICATE_PAYMENT: "Requires immediate investigation",
            ExceptionScenarioType.MATCHING_FAILURE: "Requires procurement involvement",
            ExceptionScenarioType.MATH_ERROR: "Requires finance review",
        }
        return impacts.get(exception_type, "Standard processing impact")

    def _get_compliance_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get compliance impact."""
        high_compliance = {
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION,
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION,
        }
        return "High compliance risk" if exception_type in high_compliance else "Standard compliance"

    def _get_customer_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get customer impact."""
        return "Direct customer impact" if exception_type == ExceptionScenarioType.VENDOR_POLICY_VIOLATION else "Minimal customer impact"

    def _get_reputation_risk(self, exception_type: ExceptionScenarioType, severity: str) -> str:
        """Get reputation risk."""
        if severity == "critical":
            return "High reputation risk"
        elif exception_type == ExceptionScenarioType.DUPLICATE_PAYMENT:
            return "Medium reputation risk"
        else:
            return "Low reputation risk"

    def _get_likelihood(self, exception_type: ExceptionScenarioType) -> str:
        """Get likelihood of occurrence."""
        likelihoods = {
            ExceptionScenarioType.MATH_ERROR: "medium",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "low",
            ExceptionScenarioType.MATCHING_FAILURE: "high",
            ExceptionScenarioType.DATA_QUALITY: "high",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "medium",
            ExceptionScenarioType.INVALID_FORMAT: "medium",
        }
        return likelihoods.get(exception_type, "medium")

    def _calculate_risk_score(self, exception_type: ExceptionScenarioType, severity: str) -> int:
        """Calculate risk score (1-100)."""
        likelihood_scores = {
            "low": 25,
            "medium": 50,
            "high": 75,
        }

        severity_scores = {
            "low": 25,
            "medium": 50,
            "high": 75,
            "critical": 100,
        }

        likelihood = self._get_likelihood(exception_type)
        likelihood_score = likelihood_scores.get(likelihood, 50)
        severity_score = severity_scores.get(severity, 50)

        return int((likelihood_score + severity_score) / 2)

    def _get_mitigation_strategy(self, exception_type: ExceptionScenarioType) -> str:
        """Get mitigation strategy."""
        strategies = {
            ExceptionScenarioType.MATH_ERROR: "Automated validation controls",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "Enhanced duplicate detection",
            ExceptionScenarioType.MATCHING_FAILURE: "Process automation",
            ExceptionScenarioType.DATA_QUALITY: "Data quality controls",
        }
        return strategies.get(exception_type, "Process improvement")

    def _get_monitoring_needs(self, exception_type: ExceptionScenarioType) -> bool:
        """Get if monitoring is required."""
        high_monitoring = {
            ExceptionScenarioType.DUPLICATE_PAYMENT,
            ExceptionScenarioType.MATCHING_FAILURE,
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION,
        }
        return exception_type in high_monitoring

    def _get_ccc_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get cash conversion cycle impact."""
        impacts = {
            ExceptionScenarioType.DUPLICATE_PAYMENT: "Extends CCC by 5-10 days",
            ExceptionScenarioType.MATCHING_FAILURE: "Extends CCC by 2-5 days",
        }
        return impacts.get(exception_type, "Minimal CCC impact")

    def _get_payment_terms_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get payment terms impact."""
        if exception_type == ExceptionScenarioType.VENDOR_POLICY_VIOLATION:
            return "May violate negotiated terms"
        else:
            return "No impact on payment terms"

    def _get_vendor_impact(self, exception_type: ExceptionScenarioType) -> str:
        """Get vendor relationship impact."""
        if exception_type == ExceptionScenarioType.VENDOR_POLICY_VIOLATION:
            return "Could strain vendor relationship"
        elif exception_type == ExceptionScenarioType.DUPLICATE_PAYMENT:
            return "May require vendor communication"
        else:
            return "Minimal vendor impact"

    def _get_exception_scenario_description(self, exception_type: ExceptionScenarioType) -> str:
        """Get exception scenario description."""
        descriptions = {
            ExceptionScenarioType.MATH_ERROR: "Calculation errors in invoice totals",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "Potential duplicate invoice submissions",
            ExceptionScenarioType.MATCHING_FAILURE: "Failures in three-way matching process",
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: "Violations of vendor-specific policies",
            ExceptionScenarioType.DATA_QUALITY: "Poor data quality or inconsistencies",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "Missing mandatory invoice fields",
            ExceptionScenarioType.INVALID_FORMAT: "Invalid data formats in invoice",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "Violations of business rules",
        }
        return descriptions.get(exception_type, "Unknown exception scenario")

    def _get_occurrence_frequency(self, exception_type: ExceptionScenarioType) -> str:
        """Get occurrence frequency."""
        frequencies = {
            ExceptionScenarioType.MATH_ERROR: "occasional",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "rare",
            ExceptionScenarioType.MATCHING_FAILURE: "frequent",
            ExceptionScenarioType.DATA_QUALITY: "frequent",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "occasional",
            ExceptionScenarioType.INVALID_FORMAT: "occasional",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "occasional",
        }
        return frequencies.get(exception_type, "occasional")

    def _get_resolution_complexity(self, exception_type: ExceptionScenarioType) -> str:
        """Get resolution complexity."""
        complexities = {
            ExceptionScenarioType.MATH_ERROR: "simple",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "complex",
            ExceptionScenarioType.MATCHING_FAILURE: "moderate",
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: "moderate",
            ExceptionScenarioType.DATA_QUALITY: "simple",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "simple",
            ExceptionScenarioType.INVALID_FORMAT: "simple",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "moderate",
        }
        return complexities.get(exception_type, "moderate")

    def _estimate_resolution_time(self, exception_type: ExceptionScenarioType, severity: str) -> int:
        """Estimate resolution time in hours."""
        base_times = {
            ExceptionScenarioType.MATH_ERROR: 2,
            ExceptionScenarioType.DUPLICATE_PAYMENT: 8,
            ExceptionScenarioType.MATCHING_FAILURE: 4,
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: 6,
            ExceptionScenarioType.DATA_QUALITY: 3,
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: 1,
            ExceptionScenarioType.INVALID_FORMAT: 1,
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: 5,
        }

        severity_multipliers = {
            "low": 1.0,
            "medium": 1.5,
            "high": 2.0,
            "critical": 3.0,
        }

        base_time = base_times.get(exception_type, 3)
        multiplier = severity_multipliers.get(severity, 1.0)

        return int(base_time * multiplier)

    def _estimate_success_rate(self, exception_type: ExceptionScenarioType, severity: str) -> Decimal:
        """Estimate resolution success rate."""
        base_rates = {
            ExceptionScenarioType.MATH_ERROR: 95,
            ExceptionScenarioType.DUPLICATE_PAYMENT: 85,
            ExceptionScenarioType.MATCHING_FAILURE: 90,
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: 80,
            ExceptionScenarioType.DATA_QUALITY: 92,
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: 98,
            ExceptionScenarioType.INVALID_FORMAT: 95,
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: 88,
        }

        severity_adjustments = {
            "low": 5,
            "medium": 0,
            "high": -10,
            "critical": -20,
        }

        base_rate = base_rates.get(exception_type, 90)
        adjustment = severity_adjustments.get(severity, 0)

        return Decimal(str(max(0, min(100, base_rate + adjustment))))

    def _should_be_repeat_issue(self, exception_type: ExceptionScenarioType) -> bool:
        """Determine if this should be marked as a repeat issue."""
        repeat_types = {
            ExceptionScenarioType.MATCHING_FAILURE,
            ExceptionScenarioType.DATA_QUALITY,
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION,
        }
        return exception_type in repeat_types

    async def _calculate_duplicate_quality_metrics(
        self, db: AsyncSession, duplicates: List[SeedDuplicateRecord]
    ) -> Dict[str, Any]:
        """Calculate quality metrics for generated duplicates."""
        if not duplicates:
            return {
                "average_quality_score": 0,
                "diversity_score": 0,
                "coverage_score": 0,
                "validated_count": 0,
                "failed_count": 0,
            }

        # Average quality score
        avg_quality = sum(d.confidence_score or 0 for d in duplicates) / len(duplicates)

        # Diversity score - measure of different types represented
        type_diversity = len(set(d.duplicate_type for d in duplicates))
        max_types = len(DuplicateType)
        diversity_score = (type_diversity / max_types) * 100

        # Coverage score - coverage of difficulty levels
        difficulty_diversity = len(set(d.difficulty_level for d in duplicates))
        max_difficulties = 3  # easy, medium, hard
        coverage_score = (difficulty_diversity / max_difficulties) * 100

        return {
            "average_quality_score": avg_quality,
            "diversity_score": diversity_score,
            "coverage_score": coverage_score,
            "validated_count": sum(1 for d in duplicates if d.validation_status == "validated"),
            "failed_count": sum(1 for d in duplicates if d.validation_status == "rejected"),
        }

    async def _calculate_exception_quality_metrics(
        self, db: AsyncSession, exceptions: List[SeedExceptionRecord]
    ) -> Dict[str, Any]:
        """Calculate quality metrics for generated exceptions."""
        if not exceptions:
            return {
                "average_quality_score": 0,
                "diversity_score": 0,
                "coverage_score": 0,
                "validated_count": 0,
                "failed_count": 0,
            }

        # Calculate average based on resolution success rate and CFO insights quality
        avg_success_rate = sum(e.resolution_success_rate or 0 for e in exceptions) / len(exceptions)
        avg_cfo_insights = sum(1 for e in exceptions if e.cfo_insights) / len(exceptions) * 100

        avg_quality = (avg_success_rate + avg_cfo_insights) / 2

        # Diversity score - measure of different types and severities
        type_diversity = len(set(e.exception_type for e in exceptions))
        max_types = len(ExceptionScenarioType)
        type_score = (type_diversity / max_types) * 100

        severity_diversity = len(set(e.severity for e in exceptions))
        max_severities = 4  # low, medium, high, critical
        severity_score = (severity_diversity / max_severities) * 100

        diversity_score = (type_score + severity_score) / 2

        # Coverage score - coverage of complexity and frequency
        complexity_diversity = len(set(e.resolution_complexity for e in exceptions))
        max_complexities = 3  # simple, moderate, complex
        complexity_score = (complexity_diversity / max_complexities) * 100

        frequency_diversity = len(set(e.occurrence_frequency for e in exceptions))
        max_frequencies = 3  # rare, occasional, frequent
        frequency_score = (frequency_diversity / max_frequencies) * 100

        coverage_score = (complexity_score + frequency_score) / 2

        return {
            "average_quality_score": avg_quality,
            "diversity_score": diversity_score,
            "coverage_score": coverage_score,
            "validated_count": sum(1 for e in exceptions if e.validation_status == "validated"),
            "failed_count": sum(1 for e in exceptions if e.validation_status == "rejected"),
        }

    def _group_by_type(self, duplicates: List[SeedDuplicateRecord]) -> Dict[str, int]:
        """Group duplicates by type."""
        grouped = {}
        for duplicate in duplicates:
            type_name = duplicate.duplicate_type.value
            grouped[type_name] = grouped.get(type_name, 0) + 1
        return grouped

    def _group_exceptions_by_type(self, exceptions: List[SeedExceptionRecord]) -> Dict[str, int]:
        """Group exceptions by type."""
        grouped = {}
        for exception in exceptions:
            type_name = exception.exception_type.value
            grouped[type_name] = grouped.get(type_name, 0) + 1
        return grouped

    def _group_exceptions_by_severity(self, exceptions: List[SeedExceptionRecord]) -> Dict[str, int]:
        """Group exceptions by severity."""
        grouped = {}
        for exception in exceptions:
            severity = exception.severity
            grouped[severity] = grouped.get(severity, 0) + 1
        return grouped

    async def generate_working_capital_benchmarks(
        self,
        vendor_id: Optional[str] = None,
        amount_range: Optional[float] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Generate working capital benchmarks for duplicate detection analysis.

        This method leverages seed data from Phase 1 to provide benchmark comparisons
        for working capital impact analysis, including industry standards and historical
        performance metrics.

        Args:
            vendor_id: Optional vendor ID for vendor-specific benchmarks
            amount_range: Amount range for contextual benchmarks
            db: Database session for data retrieval

        Returns:
            Comprehensive benchmark data for working capital analysis
        """
        try:
            # Generate industry benchmarks based on amount ranges
            industry_benchmarks = self._generate_industry_wc_benchmarks(amount_range)

            # Generate historical performance benchmarks from seed data
            historical_benchmarks = await self._generate_historical_wc_benchmarks(
                vendor_id, amount_range, db
            ) if db else {}

            # Generate vendor-specific benchmarks if vendor provided
            vendor_benchmarks = await self._generate_vendor_wc_benchmarks(
                vendor_id, db
            ) if vendor_id and db else {}

            # Generate duplicate pattern benchmarks
            duplicate_patterns = await self._generate_duplicate_pattern_benchmarks(db) if db else {}

            # Generate working capital efficiency benchmarks
            efficiency_benchmarks = self._generate_wc_efficiency_benchmarks(amount_range)

            # Compile comprehensive benchmark data
            benchmark_data = {
                "industry_standards": industry_benchmarks,
                "historical_performance": historical_benchmarks,
                "vendor_specific": vendor_benchmarks,
                "duplicate_patterns": duplicate_patterns,
                "efficiency_metrics": efficiency_benchmarks,
                "benchmarks_generated_at": datetime.utcnow().isoformat(),
                "analysis_metadata": {
                    "vendor_id": vendor_id,
                    "amount_range": amount_range,
                    "benchmark_version": "1.0.0"
                }
            }

            return benchmark_data

        except Exception as e:
            logger.error(f"Error generating working capital benchmarks: {e}")
            return {
                "error": "Unable to generate benchmarks",
                "fallback_data": self._generate_fallback_benchmarks(amount_range)
            }

    def _generate_industry_wc_benchmarks(self, amount_range: Optional[float]) -> Dict[str, Any]:
        """Generate industry standard working capital benchmarks."""
        # Industry benchmarks based on amount ranges
        if amount_range and amount_range > 50000:
            # Large enterprise benchmarks
            return {
                "average_duplicate_impact_score": 45,
                "industry_avg_working_capital_tied": 15000,
                "best_in_class_impact_score": 30,
                "industry_avg_cost_of_capital": 0.08,
                "average_resolution_time_days": 5,
                "duplicate_detection_accuracy": 0.92,
                "working_capital_efficiency": 0.87,
                "cash_flow_sensitivity_threshold": 0.12,
                "risk_tolerance_levels": {
                    "low": 30,
                    "medium": 60,
                    "high": 80
                }
            }
        elif amount_range and amount_range > 10000:
            # Mid-market benchmarks
            return {
                "average_duplicate_impact_score": 55,
                "industry_avg_working_capital_tied": 8000,
                "best_in_class_impact_score": 40,
                "industry_avg_cost_of_capital": 0.09,
                "average_resolution_time_days": 7,
                "duplicate_detection_accuracy": 0.88,
                "working_capital_efficiency": 0.82,
                "cash_flow_sensitivity_threshold": 0.15,
                "risk_tolerance_levels": {
                    "low": 35,
                    "medium": 65,
                    "high": 85
                }
            }
        else:
            # Small business benchmarks
            return {
                "average_duplicate_impact_score": 65,
                "industry_avg_working_capital_tied": 3500,
                "best_in_class_impact_score": 50,
                "industry_avg_cost_of_capital": 0.10,
                "average_resolution_time_days": 10,
                "duplicate_detection_accuracy": 0.85,
                "working_capital_efficiency": 0.78,
                "cash_flow_sensitivity_threshold": 0.18,
                "risk_tolerance_levels": {
                    "low": 40,
                    "medium": 70,
                    "high": 90
                }
            }

    async def _generate_historical_wc_benchmarks(
        self, vendor_id: Optional[str], amount_range: Optional[float], db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate historical performance benchmarks from seed data."""
        try:
            # Query historical duplicate records for benchmarking
            from app.models.ingestion import DuplicateRecord
            from sqlalchemy import select, func, and_

            # Build query for recent duplicates
            query = select(
                func.avg(DuplicateRecord.confidence_score).label('avg_confidence'),
                func.count(DuplicateRecord.id).label('total_duplicates'),
                func.avg(func.cast(DuplicateRecord.confidence_score, func.NUMERIC)).label('avg_impact_score')
            ).where(
                and_(
                    DuplicateRecord.created_at >= datetime.utcnow() - timedelta(days=90),
                    DuplicateRecord.status == 'resolved'
                )
            )

            result = await db.execute(query)
            historical_data = result.first()

            if historical_data and historical_data.total_duplicates > 0:
                return {
                    "historical_avg_impact_score": float(historical_data.avg_impact_score or 0),
                    "historical_avg_confidence": float(historical_data.avg_confidence or 0),
                    "total_duplicates_analyzed": historical_data.total_duplicates,
                    "trend_analysis": "improving" if historical_data.avg_confidence > 0.8 else "stable",
                    "performance_rating": "above_average" if historical_data.avg_impact_score < 50 else "average"
                }
            else:
                return {
                    "historical_avg_impact_score": 60,
                    "historical_avg_confidence": 0.75,
                    "total_duplicates_analyzed": 0,
                    "trend_analysis": "insufficient_data",
                    "performance_rating": "baseline"
                }

        except Exception as e:
            logger.warning(f"Error generating historical benchmarks: {e}")
            return {
                "historical_avg_impact_score": 60,
                "historical_avg_confidence": 0.75,
                "total_duplicates_analyzed": 0,
                "error": "Historical data unavailable"
            }

    async def _generate_vendor_wc_benchmarks(
        self, vendor_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate vendor-specific working capital benchmarks."""
        try:
            # Query vendor-specific duplicate patterns
            from app.models.invoice import Invoice
            from sqlalchemy import select, func

            query = select(
                func.count(Invoice.id).label('total_invoices'),
                func.avg(Invoice.total_amount).label('avg_invoice_amount'),
                func.max(Invoice.total_amount).label('max_invoice_amount')
            ).where(Invoice.vendor_id == vendor_id)

            result = await db.execute(query)
            vendor_data = result.first()

            if vendor_data and vendor_data.total_invoices > 0:
                # Calculate vendor-specific benchmarks
                avg_amount = float(vendor_data.avg_invoice_amount or 0)
                invoice_volume = vendor_data.total_invoices

                # Vendor risk assessment based on volume and average amount
                if invoice_volume > 100 and avg_amount > 10000:
                    risk_level = "high"
                    expected_impact_score = 40
                elif invoice_volume > 50 or avg_amount > 5000:
                    risk_level = "medium"
                    expected_impact_score = 55
                else:
                    risk_level = "low"
                    expected_impact_score = 70

                return {
                    "vendor_risk_level": risk_level,
                    "vendor_expected_impact_score": expected_impact_score,
                    "vendor_invoice_volume": invoice_volume,
                    "vendor_avg_invoice_amount": avg_amount,
                    "vendor_payment_patterns": self._estimate_vendor_payment_patterns(risk_level),
                    "vendor_specific_thresholds": {
                        "wc_impact_threshold": expected_impact_score - 10,
                        "cash_flow_sensitivity": 0.15 if risk_level == "high" else 0.20,
                        "recommended_review_frequency": "daily" if risk_level == "high" else "weekly"
                    }
                }
            else:
                return {
                    "vendor_risk_level": "unknown",
                    "vendor_expected_impact_score": 60,
                    "vendor_invoice_volume": 0,
                    "error": "Insufficient vendor data"
                }

        except Exception as e:
            logger.warning(f"Error generating vendor benchmarks: {e}")
            return {
                "vendor_risk_level": "unknown",
                "vendor_expected_impact_score": 60,
                "error": "Vendor data unavailable"
            }

    async def _generate_duplicate_pattern_benchmarks(self, db: AsyncSession) -> Dict[str, Any]:
        """Generate benchmarks based on duplicate pattern analysis."""
        try:
            from app.models.ingestion import DeduplicationStrategy, DuplicateRecord
            from sqlalchemy import select, func

            # Query duplicate detection patterns by strategy
            query = select(
                DuplicateRecord.detection_strategy,
                func.count(DuplicateRecord.id).label('count'),
                func.avg(DuplicateRecord.confidence_score).label('avg_confidence')
            ).group_by(DuplicateRecord.detection_strategy)

            result = await db.execute(query)
            pattern_data = result.all()

            if pattern_data:
                patterns = {}
                for strategy, count, avg_confidence in pattern_data:
                    patterns[strategy.value] = {
                        "frequency": count,
                        "average_confidence": float(avg_confidence or 0),
                        "effectiveness": "high" if avg_confidence > 0.8 else "medium" if avg_confidence > 0.6 else "low"
                    }

                return {
                    "detection_strategy_performance": patterns,
                    "most_common_strategy": max(patterns.items(), key=lambda x: x[1]["frequency"])[0],
                    "overall_detection_accuracy": sum(p["average_confidence"] * p["frequency"] for p in patterns.values()) / sum(p["frequency"] for p in patterns.values()),
                    "pattern_analysis": "diverse" if len(patterns) > 3 else "concentrated"
                }
            else:
                return {
                    "detection_strategy_performance": {},
                    "most_common_strategy": "composite",
                    "overall_detection_accuracy": 0.85,
                    "pattern_analysis": "baseline"
                }

        except Exception as e:
            logger.warning(f"Error generating pattern benchmarks: {e}")
            return {
                "detection_strategy_performance": {},
                "overall_detection_accuracy": 0.85,
                "error": "Pattern data unavailable"
            }

    def _generate_wc_efficiency_benchmarks(self, amount_range: Optional[float]) -> Dict[str, Any]:
        """Generate working capital efficiency benchmarks."""
        base_efficiency = 0.85  # Base efficiency score

        # Adjust based on amount range
        if amount_range and amount_range > 50000:
            efficiency_score = base_efficiency + 0.05  # Higher efficiency for large amounts
        elif amount_range and amount_range > 10000:
            efficiency_score = base_efficiency
        else:
            efficiency_score = base_efficiency - 0.05  # Lower efficiency for smaller amounts

        return {
            "working_capital_efficiency_score": round(efficiency_score, 3),
            "cash_conversion_cycle_days": 45,
            "duplicate_resolution_efficiency": 0.88,
            "cost_of_capital_utilization": 0.92,
            "working_capital_turnover_ratio": 6.5,
            "liquidity_coverage_ratio": 1.2,
            "operational_efficiency_metrics": {
                "duplicate_detection_time_hours": 2,
                "verification_process_time_hours": 4,
                "resolution_completion_time_hours": 8,
                "overall_process_efficiency": round(efficiency_score * 0.9, 3)
            }
        }

    def _estimate_vendor_payment_patterns(self, risk_level: str) -> Dict[str, Any]:
        """Estimate vendor payment patterns based on risk level."""
        patterns = {
            "high": {
                "average_payment_delay_days": 15,
                "payment_variance": "high",
                "duplicate_probability": 0.15,
                "payment_consistency_score": 0.65
            },
            "medium": {
                "average_payment_delay_days": 8,
                "payment_variance": "medium",
                "duplicate_probability": 0.08,
                "payment_consistency_score": 0.78
            },
            "low": {
                "average_payment_delay_days": 3,
                "payment_variance": "low",
                "duplicate_probability": 0.03,
                "payment_consistency_score": 0.92
            }
        }

        return patterns.get(risk_level, patterns["medium"])

    def _generate_fallback_benchmarks(self, amount_range: Optional[float]) -> Dict[str, Any]:
        """Generate fallback benchmarks when data is unavailable."""
        return {
            "industry_standards": self._generate_industry_wc_benchmarks(amount_range),
            "historical_performance": {
                "historical_avg_impact_score": 60,
                "historical_avg_confidence": 0.75,
                "total_duplicates_analyzed": 0,
                "trend_analysis": "baseline",
                "performance_rating": "baseline"
            },
            "vendor_specific": {
                "vendor_risk_level": "unknown",
                "vendor_expected_impact_score": 60,
                "error": "Vendor data unavailable"
            },
            "duplicate_patterns": {
                "overall_detection_accuracy": 0.85,
                "pattern_analysis": "baseline"
            },
            "efficiency_metrics": self._generate_wc_efficiency_benchmarks(amount_range),
            "benchmarks_generated_at": datetime.utcnow().isoformat(),
            "fallback_mode": True
        }