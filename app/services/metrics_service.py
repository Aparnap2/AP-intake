"""
Comprehensive metrics collection and SLO tracking service for AP Intake & Validation system.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.metrics import (
    SLODefinition,
    SLIMeasurement,
    SLOAlert,
    InvoiceMetric,
    SystemMetric,
    MetricsConfiguration,
    SLIType,
    SLOPeriod,
    AlertSeverity,
)
from app.models.invoice import Invoice, InvoiceStatus, Validation as ValidationModel

logger = logging.getLogger(__name__)


class MetricsService:
    """Comprehensive service for metrics collection, SLO tracking, and alerting."""

    def __init__(self):
        """Initialize the metrics service."""
        self.logger = logging.getLogger(__name__)

    async def initialize_default_slos(self) -> None:
        """Initialize default SLO definitions for the AP Intake system."""
        default_slos = [
            {
                "name": "Time-to-Ready Processing",
                "description": "Time from invoice upload to ready for approval",
                "sli_type": SLIType.TIME_TO_READY,
                "target_percentage": Decimal("95.00"),
                "target_value": Decimal("5.0"),
                "target_unit": "minutes",
                "error_budget_percentage": Decimal("5.00"),
                "alerting_threshold_percentage": Decimal("80.00"),
                "measurement_period": SLOPeriod.DAILY,
                "burn_rate_alert_threshold": Decimal("2.0"),
                "slos_owner": "AP Operations Team",
                "notification_channels": ["email", "slack"],
            },
            {
                "name": "Validation Pass Rate",
                "description": "Percentage of invoices that pass structural and math validation",
                "sli_type": SLIType.VALIDATION_PASS_RATE,
                "target_percentage": Decimal("90.00"),
                "target_value": Decimal("90.0"),
                "target_unit": "percentage",
                "error_budget_percentage": Decimal("10.00"),
                "alerting_threshold_percentage": Decimal("85.00"),
                "measurement_period": SLOPeriod.DAILY,
                "burn_rate_alert_threshold": Decimal("1.5"),
                "slos_owner": "Data Quality Team",
                "notification_channels": ["email"],
            },
            {
                "name": "Duplicate Detection Recall",
                "description": "Accuracy of duplicate invoice detection",
                "sli_type": SLIType.DUPLICATE_RECALL,
                "target_percentage": Decimal("98.00"),
                "target_value": Decimal("98.0"),
                "target_unit": "percentage",
                "error_budget_percentage": Decimal("2.00"),
                "alerting_threshold_percentage": Decimal("95.00"),
                "measurement_period": SLOPeriod.WEEKLY,
                "burn_rate_alert_threshold": Decimal("2.0"),
                "slos_owner": "Data Engineering Team",
                "notification_channels": ["email", "slack"],
            },
            {
                "name": "Approval Latency",
                "description": "Time from ready for approval to approved",
                "sli_type": SLIType.APPROVAL_LATENCY,
                "target_percentage": Decimal("90.00"),
                "target_value": Decimal("2.0"),
                "target_unit": "hours",
                "error_budget_percentage": Decimal("10.00"),
                "alerting_threshold_percentage": Decimal("85.00"),
                "measurement_period": SLOPeriod.DAILY,
                "burn_rate_alert_threshold": Decimal("1.5"),
                "slos_owner": "AP Operations Team",
                "notification_channels": ["email"],
            },
            {
                "name": "Processing Success Rate",
                "description": "Overall success rate of invoice processing workflow",
                "sli_type": SLIType.PROCESSING_SUCCESS_RATE,
                "target_percentage": Decimal("95.00"),
                "target_value": Decimal("95.0"),
                "target_unit": "percentage",
                "error_budget_percentage": Decimal("5.00"),
                "alerting_threshold_percentage": Decimal("90.00"),
                "measurement_period": SLOPeriod.HOURLY,
                "burn_rate_alert_threshold": Decimal("2.0"),
                "slos_owner": "Platform Engineering",
                "notification_channels": ["slack", "email"],
            },
            {
                "name": "Extraction Accuracy",
                "description": "Average confidence score for document extraction",
                "sli_type": SLIType.EXTRACTION_ACCURACY,
                "target_percentage": Decimal("92.00"),
                "target_value": Decimal("0.92"),
                "target_unit": "confidence",
                "error_budget_percentage": Decimal("8.00"),
                "alerting_threshold_percentage": Decimal("88.00"),
                "measurement_period": SLOPeriod.DAILY,
                "burn_rate_alert_threshold": Decimal("1.5"),
                "slos_owner": "Data Science Team",
                "notification_channels": ["email"],
            },
            {
                "name": "Exception Resolution Time",
                "description": "Average time to resolve processing exceptions",
                "sli_type": SLIType.EXCEPTION_RESOLUTION_TIME,
                "target_percentage": Decimal("85.00"),
                "target_value": Decimal("4.0"),
                "target_unit": "hours",
                "error_budget_percentage": Decimal("15.00"),
                "alerting_threshold_percentage": Decimal("80.00"),
                "measurement_period": SLOPeriod.DAILY,
                "burn_rate_alert_threshold": Decimal("1.5"),
                "slos_owner": "AP Operations Team",
                "notification_channels": ["email"],
            },
        ]

        try:
            async with AsyncSessionLocal() as session:
                for slo_config in default_slos:
                    # Check if SLO already exists
                    existing = await session.execute(
                        select(SLODefinition).where(SLODefinition.name == slo_config["name"])
                    )
                    if existing.scalar_one_or_none() is None:
                        slo = SLODefinition(**slo_config)
                        session.add(slo)
                        self.logger.info(f"Created default SLO: {slo_config['name']}")

                await session.commit()
                self.logger.info("Default SLOs initialization completed")

        except Exception as e:
            self.logger.error(f"Failed to initialize default SLOs: {e}")
            raise

    async def record_invoice_metric(
        self,
        invoice_id: UUID,
        workflow_data: Dict[str, Any],
        extraction_data: Optional[Dict[str, Any]] = None,
        validation_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record detailed metrics for an invoice processing event."""
        try:
            async with AsyncSessionLocal() as session:
                # Get invoice data
                invoice_query = select(Invoice).where(Invoice.id == invoice_id)
                invoice_result = await session.execute(invoice_query)
                invoice = invoice_result.scalar_one_or_none()

                if not invoice:
                    self.logger.warning(f"Invoice {invoice_id} not found for metrics recording")
                    return

                # Extract timing data from workflow
                processing_history = workflow_data.get("processing_history", [])
                step_timings = workflow_data.get("step_timings", {})

                # Calculate timing metrics
                received_at = invoice.created_at
                processing_started_at = self._get_step_timestamp(processing_history, "receive")
                parsing_completed_at = self._get_step_timestamp(processing_history, "parse")
                validation_completed_at = self._get_step_timestamp(processing_history, "validate")
                ready_for_approval_at = self._get_step_timestamp(processing_history, "triage")
                approved_at = self._get_step_timestamp(processing_history, "stage_export")

                # Calculate duration metrics
                time_to_ready_seconds = None
                if received_at and ready_for_approval_at:
                    time_to_ready_seconds = (ready_for_approval_at - received_at).total_seconds()

                approval_latency_seconds = None
                if ready_for_approval_at and approved_at:
                    approval_latency_seconds = (approved_at - ready_for_approval_at).total_seconds()

                total_processing_time_seconds = sum(
                    step.get("duration_ms", 0) for step in processing_history
                ) / 1000.0  # Convert to seconds

                # Extract quality metrics
                extraction_confidence = workflow_data.get("confidence_score", 0.0)
                validation_passed = validation_data.get("passed", False) if validation_data else None
                exception_count = len(workflow_data.get("exceptions", []))
                requires_human_review = workflow_data.get("requires_human_review", False)
                duplicate_detected = False  # TODO: Implement duplicate detection logic

                # Extract technical metrics
                processing_step_count = len(processing_history)
                retry_count = workflow_data.get("retry_count", 0)
                file_size_bytes = None  # TODO: Get from storage service
                page_count = extraction_data.get("metadata", {}).get("page_count", 0) if extraction_data else 0

                # Create metric record
                metric = InvoiceMetric(
                    invoice_id=invoice_id,
                    received_at=received_at,
                    processing_started_at=processing_started_at,
                    parsing_completed_at=parsing_completed_at,
                    validation_completed_at=validation_completed_at,
                    ready_for_approval_at=ready_for_approval_at,
                    approved_at=approved_at,
                    time_to_ready_seconds=time_to_ready_seconds,
                    approval_latency_seconds=approval_latency_seconds,
                    total_processing_time_seconds=total_processing_time_seconds,
                    extraction_confidence=extraction_confidence,
                    validation_passed=validation_passed,
                    exception_count=exception_count,
                    duplicate_detected=duplicate_detected,
                    requires_human_review=requires_human_review,
                    processing_step_count=processing_step_count,
                    retry_count=retry_count,
                    file_size_bytes=file_size_bytes,
                    page_count=page_count,
                    workflow_id=workflow_data.get("workflow_id"),
                    processing_metadata={
                        "step_timings": step_timings,
                        "performance_metrics": workflow_data.get("performance_metrics", {}),
                        "validation_issues": validation_data.get("issues", []) if validation_data else [],
                    },
                )

                session.add(metric)
                await session.commit()

                self.logger.debug(f"Recorded metrics for invoice {invoice_id}")

        except Exception as e:
            self.logger.error(f"Failed to record invoice metrics for {invoice_id}: {e}")
            # Don't raise - metrics failure shouldn't break main workflow

    def _get_step_timestamp(self, processing_history: List[Dict[str, Any]], step_name: str) -> Optional[datetime]:
        """Extract timestamp for a specific processing step."""
        for step in processing_history:
            if step.get("step") == step_name and step.get("status") == "completed":
                timestamp_str = step.get("timestamp")
                if timestamp_str:
                    try:
                        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        continue
        return None

    async def calculate_sli_measurements(self, period: SLOPeriod, period_start: datetime, period_end: datetime) -> List[SLIMeasurement]:
        """Calculate SLI measurements for the specified period."""
        measurements = []

        try:
            async with AsyncSessionLocal() as session:
                # Get active SLO definitions
                slo_query = select(SLODefinition).where(
                    and_(
                        SLODefinition.is_active == True,
                        SLODefinition.measurement_period == period
                    )
                )
                slo_result = await session.execute(slo_query)
                slo_definitions = slo_result.scalars().all()

                for slo_def in slo_definitions:
                    measurement = await self._calculate_sli_for_slo(
                        session, slo_def, period_start, period_end
                    )
                    if measurement:
                        measurements.append(measurement)

                # Bulk insert measurements
                if measurements:
                    session.add_all(measurements)
                    await session.commit()
                    self.logger.info(f"Created {len(measurements)} SLI measurements for {period.value} period")

        except Exception as e:
            self.logger.error(f"Failed to calculate SLI measurements: {e}")
            raise

        return measurements

    async def _calculate_sli_for_slo(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[SLIMeasurement]:
        """Calculate SLI measurement for a specific SLO definition."""
        try:
            if slo_def.sli_type == SLIType.TIME_TO_READY:
                return await self._calculate_time_to_ready_sli(
                    session, slo_def, period_start, period_end
                )
            elif slo_def.sli_type == SLIType.VALIDATION_PASS_RATE:
                return await self._calculate_validation_pass_rate_sli(
                    session, slo_def, period_start, period_end
                )
            elif slo_def.sli_type == SLIType.DUPLICATE_RECALL:
                return await self._calculate_duplicate_recall_sli(
                    session, slo_def, period_start, period_end
                )
            elif slo_def.sli_type == SLIType.APPROVAL_LATENCY:
                return await self._calculate_approval_latency_sli(
                    session, slo_def, period_start, period_end
                )
            elif slo_def.sli_type == SLIType.PROCESSING_SUCCESS_RATE:
                return await self._calculate_processing_success_rate_sli(
                    session, slo_def, period_start, period_end
                )
            elif slo_def.sli_type == SLIType.EXTRACTION_ACCURACY:
                return await self._calculate_extraction_accuracy_sli(
                    session, slo_def, period_start, period_end
                )
            elif slo_def.sli_type == SLIType.EXCEPTION_RESOLUTION_TIME:
                return await self._calculate_exception_resolution_time_sli(
                    session, slo_def, period_start, period_end
                )

        except Exception as e:
            self.logger.error(f"Failed to calculate SLI for {slo_def.name}: {e}")

        return None

    async def _calculate_time_to_ready_sli(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> SLIMeasurement:
        """Calculate time-to-ready SLI measurement."""
        target_minutes = float(slo_def.target_value)
        target_seconds = target_minutes * 60

        # Query invoices processed in the period
        query = select(InvoiceMetric).where(
            and_(
                InvoiceMetric.ready_for_approval_at >= period_start,
                InvoiceMetric.ready_for_approval_at < period_end,
                InvoiceMetric.time_to_ready_seconds.isnot(None)
            )
        )
        result = await session.execute(query)
        metrics = result.scalars().all()

        if not metrics:
            # No data for this period
            return SLIMeasurement(
                slo_definition_id=slo_def.id,
                period_start=period_start,
                period_end=period_end,
                measurement_period=slo_def.measurement_period,
                actual_value=Decimal("0.0"),
                target_value=Decimal(str(target_seconds)),
                achieved_percentage=Decimal("0.0"),
                good_events_count=0,
                total_events_count=0,
                error_budget_consumed=Decimal("0.0"),
                measurement_metadata={"no_data": True},
            )

        # Calculate good events (within target)
        good_events = sum(1 for m in metrics if m.time_to_ready_seconds <= target_seconds)
        total_events = len(metrics)

        # Calculate achieved percentage
        achieved_percentage = (good_events / total_events) * 100 if total_events > 0 else 0
        error_budget_consumed = max(0, 100 - achieved_percentage)

        # Calculate average actual value
        avg_time_to_ready = sum(m.time_to_ready_seconds for m in metrics) / total_events

        return SLIMeasurement(
            slo_definition_id=slo_def.id,
            period_start=period_start,
            period_end=period_end,
            measurement_period=slo_def.measurement_period,
            actual_value=Decimal(str(avg_time_to_ready)),
            target_value=Decimal(str(target_seconds)),
            achieved_percentage=Decimal(str(achieved_percentage)),
            good_events_count=good_events,
            total_events_count=total_events,
            error_budget_consumed=Decimal(str(error_budget_consumed)),
            measurement_metadata={
                "average_minutes": avg_time_to_ready / 60,
                "sample_size": total_events,
                "target_minutes": target_minutes,
            },
        )

    async def _calculate_validation_pass_rate_sli(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> SLIMeasurement:
        """Calculate validation pass rate SLI measurement."""
        target_percentage = float(slo_def.target_value)

        # Query validation results in the period
        query = select(InvoiceMetric).where(
            and_(
                InvoiceMetric.validation_completed_at >= period_start,
                InvoiceMetric.validation_completed_at < period_end,
                InvoiceMetric.validation_passed.isnot(None)
            )
        )
        result = await session.execute(query)
        metrics = result.scalars().all()

        if not metrics:
            return SLIMeasurement(
                slo_definition_id=slo_def.id,
                period_start=period_start,
                period_end=period_end,
                measurement_period=slo_def.measurement_period,
                actual_value=Decimal("0.0"),
                target_value=Decimal(str(target_percentage)),
                achieved_percentage=Decimal("0.0"),
                good_events_count=0,
                total_events_count=0,
                error_budget_consumed=Decimal("0.0"),
                measurement_metadata={"no_data": True},
            )

        # Calculate pass rate
        good_events = sum(1 for m in metrics if m.validation_passed)
        total_events = len(metrics)

        achieved_percentage = (good_events / total_events) * 100 if total_events > 0 else 0
        error_budget_consumed = max(0, 100 - achieved_percentage)

        return SLIMeasurement(
            slo_definition_id=slo_def.id,
            period_start=period_start,
            period_end=period_end,
            measurement_period=slo_def.measurement_period,
            actual_value=Decimal(str(achieved_percentage)),
            target_value=Decimal(str(target_percentage)),
            achieved_percentage=Decimal(str(achieved_percentage)),
            good_events_count=good_events,
            total_events_count=total_events,
            error_budget_consumed=Decimal(str(error_budget_consumed)),
            measurement_metadata={
                "pass_rate": achieved_percentage,
                "sample_size": total_events,
                "target_percentage": target_percentage,
            },
        )

    async def _calculate_processing_success_rate_sli(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> SLIMeasurement:
        """Calculate processing success rate SLI measurement."""
        target_percentage = float(slo_def.target_value)

        # Query invoices with ready status (successful processing)
        query = select(Invoice).where(
            and_(
                Invoice.created_at >= period_start,
                Invoice.created_at < period_end,
                Invoice.status.in_([InvoiceStatus.READY, InvoiceStatus.STAGED, InvoiceStatus.DONE])
            )
        )
        result = await session.execute(query)
        successful_invoices = len(result.scalars().all())

        # Query total invoices processed in period
        total_query = select(func.count(Invoice.id)).where(
            and_(
                Invoice.created_at >= period_start,
                Invoice.created_at < period_end
            )
        )
        total_result = await session.execute(total_query)
        total_events = total_result.scalar() or 0

        if total_events == 0:
            return SLIMeasurement(
                slo_definition_id=slo_def.id,
                period_start=period_start,
                period_end=period_end,
                measurement_period=slo_def.measurement_period,
                actual_value=Decimal("0.0"),
                target_value=Decimal(str(target_percentage)),
                achieved_percentage=Decimal("0.0"),
                good_events_count=0,
                total_events_count=0,
                error_budget_consumed=Decimal("0.0"),
                measurement_metadata={"no_data": True},
            )

        achieved_percentage = (successful_invoices / total_events) * 100
        error_budget_consumed = max(0, 100 - achieved_percentage)

        return SLIMeasurement(
            slo_definition_id=slo_def.id,
            period_start=period_start,
            period_end=period_end,
            measurement_period=slo_def.measurement_period,
            actual_value=Decimal(str(achieved_percentage)),
            target_value=Decimal(str(target_percentage)),
            achieved_percentage=Decimal(str(achieved_percentage)),
            good_events_count=successful_invoices,
            total_events_count=total_events,
            error_budget_consumed=Decimal(str(error_budget_consumed)),
            measurement_metadata={
                "success_rate": achieved_percentage,
                "sample_size": total_events,
                "target_percentage": target_percentage,
            },
        )

    async def _calculate_extraction_accuracy_sli(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> SLIMeasurement:
        """Calculate extraction accuracy SLI measurement."""
        target_confidence = float(slo_def.target_value)

        # Query extraction metrics in the period
        query = select(InvoiceMetric).where(
            and_(
                InvoiceMetric.parsing_completed_at >= period_start,
                InvoiceMetric.parsing_completed_at < period_end,
                InvoiceMetric.extraction_confidence.isnot(None)
            )
        )
        result = await session.execute(query)
        metrics = result.scalars().all()

        if not metrics:
            return SLIMeasurement(
                slo_definition_id=slo_def.id,
                period_start=period_start,
                period_end=period_end,
                measurement_period=slo_def.measurement_period,
                actual_value=Decimal("0.0"),
                target_value=Decimal(str(target_confidence)),
                achieved_percentage=Decimal("0.0"),
                good_events_count=0,
                total_events_count=0,
                error_budget_consumed=Decimal("0.0"),
                measurement_metadata={"no_data": True},
            )

        # Calculate average confidence
        avg_confidence = sum(m.extraction_confidence for m in metrics) / len(metrics)
        achieved_percentage = (avg_confidence / target_confidence) * 100 if target_confidence > 0 else 0
        error_budget_consumed = max(0, 100 - achieved_percentage)

        return SLIMeasurement(
            slo_definition_id=slo_def.id,
            period_start=period_start,
            period_end=period_end,
            measurement_period=slo_def.measurement_period,
            actual_value=Decimal(str(avg_confidence)),
            target_value=Decimal(str(target_confidence)),
            achieved_percentage=Decimal(str(achieved_percentage)),
            good_events_count=len(metrics),
            total_events_count=len(metrics),
            error_budget_consumed=Decimal(str(error_budget_consumed)),
            measurement_metadata={
                "average_confidence": avg_confidence,
                "sample_size": len(metrics),
                "target_confidence": target_confidence,
            },
        )

    async def _calculate_approval_latency_sli(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> SLIMeasurement:
        """Calculate approval latency SLI measurement."""
        target_hours = float(slo_def.target_value)
        target_seconds = target_hours * 3600

        # Query approved invoices in the period
        query = select(InvoiceMetric).where(
            and_(
                InvoiceMetric.approved_at >= period_start,
                InvoiceMetric.approved_at < period_end,
                InvoiceMetric.ready_for_approval_at.isnot(None),
                InvoiceMetric.approval_latency_seconds.isnot(None)
            )
        )
        result = await session.execute(query)
        metrics = result.scalars().all()

        if not metrics:
            return SLIMeasurement(
                slo_definition_id=slo_def.id,
                period_start=period_start,
                period_end=period_end,
                measurement_period=slo_def.measurement_period,
                actual_value=Decimal("0.0"),
                target_value=Decimal(str(target_seconds)),
                achieved_percentage=Decimal("0.0"),
                good_events_count=0,
                total_events_count=0,
                error_budget_consumed=Decimal("0.0"),
                measurement_metadata={"no_data": True},
            )

        # Calculate good events (within target)
        good_events = sum(1 for m in metrics if m.approval_latency_seconds <= target_seconds)
        total_events = len(metrics)

        # Calculate achieved percentage
        achieved_percentage = (good_events / total_events) * 100 if total_events > 0 else 0
        error_budget_consumed = max(0, 100 - achieved_percentage)

        # Calculate average actual value
        avg_approval_latency = sum(m.approval_latency_seconds for m in metrics) / total_events

        return SLIMeasurement(
            slo_definition_id=slo_def.id,
            period_start=period_start,
            period_end=period_end,
            measurement_period=slo_def.measurement_period,
            actual_value=Decimal(str(avg_approval_latency)),
            target_value=Decimal(str(target_seconds)),
            achieved_percentage=Decimal(str(achieved_percentage)),
            good_events_count=good_events,
            total_events_count=total_events,
            error_budget_consumed=Decimal(str(error_budget_consumed)),
            measurement_metadata={
                "average_hours": avg_approval_latency / 3600,
                "sample_size": total_events,
                "target_hours": target_hours,
            },
        )

    async def _calculate_duplicate_recall_sli(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> SLIMeasurement:
        """Calculate duplicate detection recall SLI measurement."""
        target_percentage = float(slo_def.target_value)

        # TODO: Implement duplicate detection logic
        # For now, return a placeholder measurement
        return SLIMeasurement(
            slo_definition_id=slo_def.id,
            period_start=period_start,
            period_end=period_end,
            measurement_period=slo_def.measurement_period,
            actual_value=Decimal("0.0"),
            target_value=Decimal(str(target_percentage)),
            achieved_percentage=Decimal("0.0"),
            good_events_count=0,
            total_events_count=0,
            error_budget_consumed=Decimal("0.0"),
            measurement_metadata={"status": "not_implemented"},
        )

    async def _calculate_exception_resolution_time_sli(
        self,
        session: AsyncSession,
        slo_def: SLODefinition,
        period_start: datetime,
        period_end: datetime,
    ) -> SLIMeasurement:
        """Calculate exception resolution time SLI measurement."""
        target_hours = float(slo_def.target_value)
        target_seconds = target_hours * 3600

        # TODO: Implement exception resolution time tracking
        # For now, return a placeholder measurement
        return SLIMeasurement(
            slo_definition_id=slo_def.id,
            period_start=period_start,
            period_end=period_end,
            measurement_period=slo_def.measurement_period,
            actual_value=Decimal("0.0"),
            target_value=Decimal(str(target_seconds)),
            achieved_percentage=Decimal("0.0"),
            good_events_count=0,
            total_events_count=0,
            error_budget_consumed=Decimal("0.0"),
            measurement_metadata={"status": "not_implemented"},
        )

    async def check_and_create_alerts(self, measurement: SLIMeasurement) -> List[SLOAlert]:
        """Check if alerts should be created for a measurement."""
        alerts = []

        try:
            async with AsyncSessionLocal() as session:
                # Get SLO definition
                slo_query = select(SLODefinition).where(SLODefinition.id == measurement.slo_definition_id)
                slo_result = await session.execute(slo_query)
                slo_def = slo_result.scalar_one_or_none()

                if not slo_def:
                    return alerts

                # Check for error budget alerts
                if measurement.error_budget_consumed >= slo_def.error_budget_percentage:
                    alert = SLOAlert(
                        slo_definition_id=measurement.slo_definition_id,
                        measurement_id=measurement.id,
                        alert_type="error_budget_exhausted",
                        severity=AlertSeverity.CRITICAL,
                        title=f"Error Budget Exhausted: {slo_def.name}",
                        message=f"SLO '{slo_def.name}' has exhausted its error budget ({measurement.error_budget_consumed:.2f}% >= {slo_def.error_budget_percentage:.2f}%)",
                        current_value=measurement.actual_value,
                        target_value=measurement.target_value,
                        breached_at=datetime.now(timezone.utc),
                    )
                    alerts.append(alert)

                # Check for burn rate alerts
                if measurement.error_budget_consumed >= slo_def.alerting_threshold_percentage:
                    alert = SLOAlert(
                        slo_definition_id=measurement.slo_definition_id,
                        measurement_id=measurement.id,
                        alert_type="burn_rate_warning",
                        severity=AlertSeverity.WARNING,
                        title=f"High Burn Rate: {slo_def.name}",
                        message=f"SLO '{slo_def.name}' has high burn rate ({measurement.error_budget_consumed:.2f}% >= {slo_def.alerting_threshold_percentage:.2f}%)",
                        current_value=measurement.actual_value,
                        target_value=measurement.target_value,
                        breached_at=datetime.now(timezone.utc),
                    )
                    alerts.append(alert)

                # Check for critical performance degradation
                if measurement.achieved_percentage < 50:
                    alert = SLOAlert(
                        slo_definition_id=measurement.slo_definition_id,
                        measurement_id=measurement.id,
                        alert_type="critical_performance",
                        severity=AlertSeverity.CRITICAL,
                        title=f"Critical Performance Issue: {slo_def.name}",
                        message=f"SLO '{slo_def.name}' has critical performance degradation ({measurement.achieved_percentage:.2f}% achieved)",
                        current_value=measurement.actual_value,
                        target_value=measurement.target_value,
                        breached_at=datetime.now(timezone.utc),
                    )
                    alerts.append(alert)

                # Store alerts
                if alerts:
                    session.add_all(alerts)
                    await session.commit()
                    self.logger.info(f"Created {len(alerts)} alerts for SLO {slo_def.name}")

        except Exception as e:
            self.logger.error(f"Failed to create alerts for measurement {measurement.id}: {e}")

        return alerts

    async def get_slo_dashboard_data(
        self,
        time_range_days: int = 30,
        slo_types: Optional[List[SLIType]] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive SLO dashboard data."""
        try:
            async with AsyncSessionLocal() as session:
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=time_range_days)

                # Get active SLO definitions
                slo_query = select(SLODefinition).where(SLODefinition.is_active == True)
                if slo_types:
                    slo_query = slo_query.where(SLODefinition.sli_type.in_(slo_types))

                slo_result = await session.execute(slo_query)
                slo_definitions = slo_result.scalars().all()

                dashboard_data = {
                    "time_range": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "days": time_range_days,
                    },
                    "slos": [],
                    "summary": {
                        "total_slos": len(slo_definitions),
                        "healthy_slos": 0,
                        "warning_slos": 0,
                        "critical_slos": 0,
                    },
                    "alerts": [],
                }

                # Get latest measurements for each SLO
                for slo_def in slo_definitions:
                    # Get latest measurement
                    latest_measurement_query = select(SLIMeasurement).where(
                        and_(
                            SLIMeasurement.slo_definition_id == slo_def.id,
                            SLIMeasurement.period_start >= start_date,
                        )
                    ).order_by(desc(SLIMeasurement.period_start)).limit(1)

                    latest_result = await session.execute(latest_measurement_query)
                    latest_measurement = latest_result.scalar_one_or_none()

                    # Get recent alerts
                    alerts_query = select(SLOAlert).where(
                        and_(
                            SLOAlert.slo_definition_id == slo_def.id,
                            SLOAlert.created_at >= start_date,
                            SLOAlert.resolved_at.is_(None)
                        )
                    ).order_by(desc(SLOAlert.created_at))

                    alerts_result = await session.execute(alerts_query)
                    recent_alerts = alerts_result.scalars().all()

                    # Determine SLO status
                    status = "healthy"
                    if latest_measurement:
                        if latest_measurement.error_budget_consumed >= slo_def.error_budget_percentage:
                            status = "critical"
                        elif latest_measurement.error_budget_consumed >= slo_def.alerting_threshold_percentage:
                            status = "warning"
                        elif latest_measurement.achieved_percentage < 50:
                            status = "critical"

                    # Update summary counts
                    if status == "healthy":
                        dashboard_data["summary"]["healthy_slos"] += 1
                    elif status == "warning":
                        dashboard_data["summary"]["warning_slos"] += 1
                    elif status == "critical":
                        dashboard_data["summary"]["critical_slos"] += 1

                    slo_data = {
                        "id": str(slo_def.id),
                        "name": slo_def.name,
                        "description": slo_def.description,
                        "sli_type": slo_def.sli_type.value,
                        "target_percentage": float(slo_def.target_percentage),
                        "target_value": float(slo_def.target_value),
                        "target_unit": slo_def.target_unit,
                        "status": status,
                        "latest_measurement": {
                            "period_start": latest_measurement.period_start.isoformat() if latest_measurement else None,
                            "period_end": latest_measurement.period_end.isoformat() if latest_measurement else None,
                            "achieved_percentage": float(latest_measurement.achieved_percentage) if latest_measurement else None,
                            "actual_value": float(latest_measurement.actual_value) if latest_measurement else None,
                            "error_budget_consumed": float(latest_measurement.error_budget_consumed) if latest_measurement else None,
                            "good_events_count": latest_measurement.good_events_count if latest_measurement else 0,
                            "total_events_count": latest_measurement.total_events_count if latest_measurement else 0,
                        } if latest_measurement else None,
                        "recent_alerts": [
                            {
                                "id": str(alert.id),
                                "type": alert.alert_type,
                                "severity": alert.severity.value,
                                "title": alert.title,
                                "created_at": alert.created_at.isoformat(),
                            } for alert in recent_alerts[:5]  # Limit to 5 most recent
                        ],
                        "alert_count": len(recent_alerts),
                    }

                    dashboard_data["slos"].append(slo_data)

                # Get all recent critical alerts
                critical_alerts_query = select(SLOAlert).where(
                    and_(
                        SLOAlert.severity == AlertSeverity.CRITICAL,
                        SLOAlert.created_at >= start_date,
                        SLOAlert.resolved_at.is_(None)
                    )
                ).order_by(desc(SLOAlert.created_at)).limit(10)

                critical_alerts_result = await session.execute(critical_alerts_query)
                critical_alerts = critical_alerts_result.scalars().all()

                dashboard_data["alerts"] = [
                    {
                        "id": str(alert.id),
                        "slo_name": alert.slo_definition.name if alert.slo_definition else "Unknown",
                        "type": alert.alert_type,
                        "severity": alert.severity.value,
                        "title": alert.title,
                        "message": alert.message,
                        "created_at": alert.created_at.isoformat(),
                    } for alert in critical_alerts
                ]

                return dashboard_data

        except Exception as e:
            self.logger.error(f"Failed to get SLO dashboard data: {e}")
            raise

    async def record_system_metric(
        self,
        metric_name: str,
        metric_category: str,
        value: float,
        unit: Optional[str] = None,
        dimensions: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        data_source: str = "manual",
        confidence_score: Optional[float] = None,
    ) -> None:
        """Record a system-level metric."""
        try:
            async with AsyncSessionLocal() as session:
                metric = SystemMetric(
                    metric_name=metric_name,
                    metric_category=metric_category,
                    measurement_timestamp=datetime.now(timezone.utc),
                    value=Decimal(str(value)),
                    unit=unit,
                    dimensions=dimensions,
                    tags=tags,
                    metadata=metadata,
                    data_source=data_source,
                    confidence_score=Decimal(str(confidence_score)) if confidence_score else None,
                )

                session.add(metric)
                await session.commit()

                self.logger.debug(f"Recorded system metric: {metric_name} = {value}")

        except Exception as e:
            self.logger.error(f"Failed to record system metric {metric_name}: {e}")
            # Don't raise - metrics failure shouldn't break main operations

    async def get_kpi_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get summary of key performance indicators."""
        try:
            async with AsyncSessionLocal() as session:
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=days)

                # Get invoice volume and processing metrics
                invoice_query = select(func.count(Invoice.id)).where(
                    Invoice.created_at >= start_date
                )
                invoice_result = await session.execute(invoice_query)
                total_invoices = invoice_result.scalar() or 0

                # Get successfully processed invoices
                success_query = select(func.count(Invoice.id)).where(
                    and_(
                        Invoice.created_at >= start_date,
                        Invoice.status.in_([InvoiceStatus.READY, InvoiceStatus.STAGED, InvoiceStatus.DONE])
                    )
                )
                success_result = await session.execute(success_query)
                successful_invoices = success_result.scalar() or 0

                # Get average processing time
                avg_time_query = select(func.avg(InvoiceMetric.time_to_ready_seconds)).where(
                    and_(
                        InvoiceMetric.ready_for_approval_at >= start_date,
                        InvoiceMetric.time_to_ready_seconds.isnot(None)
                    )
                )
                avg_time_result = await session.execute(avg_time_query)
                avg_processing_time = avg_time_result.scalar() or 0

                # Get average extraction confidence
                avg_confidence_query = select(func.avg(InvoiceMetric.extraction_confidence)).where(
                    and_(
                        InvoiceMetric.parsing_completed_at >= start_date,
                        InvoiceMetric.extraction_confidence.isnot(None)
                    )
                )
                avg_confidence_result = await session.execute(avg_confidence_query)
                avg_confidence = avg_confidence_result.scalar() or 0

                # Get exception rate
                exception_query = select(func.count(InvoiceMetric.id)).where(
                    and_(
                        InvoiceMetric.received_at >= start_date,
                        InvoiceMetric.exception_count > 0
                    )
                )
                exception_result = await session.execute(exception_query)
                invoices_with_exceptions = exception_result.scalar() or 0

                # Calculate rates
                processing_success_rate = (successful_invoices / total_invoices * 100) if total_invoices > 0 else 0
                exception_rate = (invoices_with_exceptions / total_invoices * 100) if total_invoices > 0 else 0

                return {
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "days": days,
                    },
                    "volume": {
                        "total_invoices": total_invoices,
                        "successful_invoices": successful_invoices,
                        "invoices_with_exceptions": invoices_with_exceptions,
                    },
                    "performance": {
                        "processing_success_rate": round(processing_success_rate, 2),
                        "exception_rate": round(exception_rate, 2),
                        "average_processing_time_seconds": round(float(avg_processing_time), 2),
                        "average_processing_time_minutes": round(float(avg_processing_time) / 60, 2),
                        "average_extraction_confidence": round(float(avg_confidence), 4),
                    },
                    "summary": {
                        "daily_average_invoices": round(total_invoices / days, 1),
                        "success_rate_grade": "A" if processing_success_rate >= 95 else "B" if processing_success_rate >= 90 else "C",
                        "performance_trend": "improving",  # TODO: Calculate actual trend
                    },
                }

        except Exception as e:
            self.logger.error(f"Failed to get KPI summary: {e}")
            raise


# Singleton instance
metrics_service = MetricsService()