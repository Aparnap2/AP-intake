"""
Comprehensive deduplication service with multiple detection strategies.
"""

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple, Set
from uuid import UUID
from decimal import Decimal

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from app.core.config import settings
from app.core.exceptions import DeduplicationException
from app.models.ingestion import (
    IngestionJob,
    DuplicateRecord,
    DeduplicationRule,
    DeduplicationStrategy,
    DuplicateResolution,
)
from app.models.invoice import Invoice
from app.models.reference import Vendor

logger = logging.getLogger(__name__)


class DeduplicationService:
    """Advanced deduplication service with multiple detection strategies."""

    def __init__(self):
        """Initialize the deduplication service."""
        self.fuzzy_similarity_threshold = 0.85
        self.temporal_window_hours = 24  # Hours to check for temporal duplicates
        self.amount_tolerance = 0.01  # 1% tolerance for amount matching

    async def analyze_for_duplicates(
        self,
        ingestion_job: IngestionJob,
        file_content: bytes,
        extracted_metadata: Dict[str, Any],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Analyze ingestion job for duplicates using multiple strategies.

        Returns:
            List of duplicate detection results with confidence scores
        """
        logger.info(f"Analyzing duplicates for job {ingestion_job.id}")

        duplicates = []

        try:
            # Get active deduplication rules
            active_rules = await self._get_active_rules(db, ingestion_job)

            # Apply each enabled strategy
            for rule in active_rules:
                strategy_deduplication = await self._apply_strategy_rule(
                    rule, ingestion_job, file_content, extracted_metadata, db
                )

                if strategy_deduplication:
                    duplicates.extend(strategy_deduplication)

            # Sort duplicates by confidence score (highest first)
            duplicates.sort(key=lambda x: x["confidence_score"], reverse=True)

            # Create duplicate records in database
            await self._create_duplicate_records(ingestion_job, duplicates, db)

            logger.info(f"Found {len(duplicates)} potential duplicates for job {ingestion_job.id}")
            return duplicates

        except Exception as e:
            logger.error(f"Duplicate analysis failed for job {ingestion_job.id}: {e}")
            raise DeduplicationException(f"Duplicate analysis failed: {str(e)}")

    async def get_duplicate_groups(
        self,
        db: AsyncSession,
        limit: int = 100,
        vendor_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get duplicate groups for review and resolution."""
        try:
            # Build query conditions
            conditions = [DuplicateRecord.requires_human_review == True]

            if vendor_id:
                try:
                    vendor_uuid = UUID(vendor_id)
                    conditions.append(
                        IngestionJob.vendor_id == vendor_uuid
                    )
                except ValueError:
                    raise DeduplicationException(f"Invalid vendor ID format: {vendor_id}")

            if status:
                conditions.append(DuplicateRecord.status == status)

            # Query duplicate records with ingestion jobs
            query = (
                select(DuplicateRecord, IngestionJob)
                .join(IngestionJob, DuplicateRecord.ingestion_job_id == IngestionJob.id)
                .where(and_(*conditions))
                .order_by(desc(DuplicateRecord.confidence_score))
                .limit(limit)
            )

            result = await db.execute(query)
            duplicate_records = result.all()

            # Group by duplicate group
            groups = {}
            for duplicate, job in duplicate_records:
                group_id = duplicate.ingestion_job.duplicate_group_id or str(duplicate.id)
                if group_id not in groups:
                    groups[group_id] = {
                        "group_id": group_id,
                        "duplicates": [],
                        "total_confidence": 0.0,
                        "strategies_used": set(),
                    }

                groups[group_id]["duplicates"].append({
                    "id": str(duplicate.id),
                    "ingestion_job_id": str(duplicate.ingestion_job_id),
                    "confidence_score": duplicate.confidence_score,
                    "strategy": duplicate.detection_strategy.value,
                    "match_criteria": duplicate.match_criteria,
                    "status": duplicate.status,
                    "created_at": duplicate.created_at.isoformat(),
                    "filename": job.original_filename,
                    "file_size": job.file_size_bytes,
                })

                groups[group_id]["total_confidence"] += duplicate.confidence_score
                groups[group_id]["strategies_used"].add(duplicate.detection_strategy.value)

            # Convert to list and sort by total confidence
            result_groups = []
            for group_id, group_data in groups.items():
                group_data["strategies_used"] = list(group_data["strategies_used"])
                group_data["duplicate_count"] = len(group_data["duplicates"])
                result_groups.append(group_data)

            result_groups.sort(key=lambda x: x["total_confidence"], reverse=True)

            return result_groups

        except Exception as e:
            logger.error(f"Failed to get duplicate groups: {e}")
            raise DeduplicationException(f"Failed to get duplicate groups: {str(e)}")

    async def resolve_duplicate_group(
        self,
        group_id: str,
        resolution: DuplicateResolution,
        resolved_by: str,
        db: AsyncSession,
        resolution_notes: Optional[str] = None,
    ) -> bool:
        """Resolve an entire duplicate group with specified action."""
        try:
            # Get all duplicates in the group
            query = (
                select(DuplicateRecord)
                .join(IngestionJob, DuplicateRecord.ingestion_job_id == IngestionJob.id)
                .where(
                    or_(
                        DuplicateRecord.id == UUID(group_id) if self._is_valid_uuid(group_id) else False,
                        IngestionJob.duplicate_group_id == UUID(group_id) if self._is_valid_uuid(group_id) else False,
                    )
                )
            )
            result = await db.execute(query)
            duplicates = result.scalars().all()

            if not duplicates:
                raise DeduplicationException(f"Duplicate group {group_id} not found")

            # Resolve each duplicate in the group
            for duplicate in duplicates:
                duplicate.resolution_action = resolution
                duplicate.resolved_by = resolved_by
                duplicate.resolved_at = datetime.now(timezone.utc)
                duplicate.resolution_notes = resolution_notes
                duplicate.status = "resolved"

            # Apply resolution action to the group
            await self._apply_group_resolution(duplicates, resolution, db)

            await db.commit()
            logger.info(f"Resolved duplicate group {group_id} with action: {resolution}")
            return True

        except ValueError:
            raise DeduplicationException(f"Invalid group ID format: {group_id}")
        except Exception as e:
            logger.error(f"Failed to resolve duplicate group {group_id}: {e}")
            await db.rollback()
            raise DeduplicationException(f"Failed to resolve duplicate group: {str(e)}")

    async def update_deduplication_rules(
        self,
        rules: List[Dict[str, Any]],
        db: AsyncSession,
    ) -> bool:
        """Update deduplication rules and configurations."""
        try:
            for rule_data in rules:
                if "id" in rule_data:
                    # Update existing rule
                    rule_uuid = UUID(rule_data["id"])
                    result = await db.execute(
                        select(DeduplicationRule).where(DeduplicationRule.id == rule_uuid)
                    )
                    rule = result.scalar_one_or_none()

                    if rule:
                        # Update rule properties
                        for field in ["name", "description", "configuration", "is_active", "priority"]:
                            if field in rule_data:
                                setattr(rule, field, rule_data[field])
                else:
                    # Create new rule
                    rule = DeduplicationRule(
                        name=rule_data["name"],
                        description=rule_data.get("description"),
                        strategy=DeduplicationStrategy(rule_data["strategy"]),
                        configuration=rule_data["configuration"],
                        is_active=rule_data.get("is_active", True),
                        priority=rule_data.get("priority", 5),
                    )
                    db.add(rule)

            await db.commit()
            logger.info(f"Updated {len(rules)} deduplication rules")
            return True

        except Exception as e:
            logger.error(f"Failed to update deduplication rules: {e}")
            await db.rollback()
            raise DeduplicationException(f"Failed to update rules: {str(e)}")

    async def _get_active_rules(
        self, ingestion_job: IngestionJob, db: AsyncSession
    ) -> List[DeduplicationRule]:
        """Get active deduplication rules applicable to the ingestion job."""
        query = select(DeduplicationRule).where(DeduplicationRule.is_active == True)
        result = await db.execute(query)
        rules = result.scalars().all()

        # Filter rules based on applicability constraints
        applicable_rules = []
        for rule in rules:
            if await self._is_rule_applicable(rule, ingestion_job):
                applicable_rules.append(rule)

        # Sort by priority (highest first)
        applicable_rules.sort(key=lambda x: x.priority, reverse=True)

        return applicable_rules

    async def _is_rule_applicable(
        self, rule: DeduplicationRule, ingestion_job: IngestionJob
    ) -> bool:
        """Check if a deduplication rule is applicable to the ingestion job."""
        config = rule.configuration

        # Check vendor filter
        if "vendor_filter" in config:
            vendor_filter = config["vendor_filter"]
            if ingestion_job.vendor_id and ingestion_job.vendor_id not in vendor_filter:
                return False

        # Check file type filter
        if "file_type_filter" in config:
            file_type_filter = config["file_type_filter"]
            if ingestion_job.file_extension not in file_type_filter:
                return False

        # Check date range filter
        if "date_range_filter" in config:
            date_filter = config["date_range_filter"]
            job_date = ingestion_job.created_at.date()

            if "start_date" in date_filter:
                start_date = datetime.fromisoformat(date_filter["start_date"]).date()
                if job_date < start_date:
                    return False

            if "end_date" in date_filter:
                end_date = datetime.fromisoformat(date_filter["end_date"]).date()
                if job_date > end_date:
                    return False

        return True

    async def _apply_strategy_rule(
        self,
        rule: DeduplicationRule,
        ingestion_job: IngestionJob,
        file_content: bytes,
        metadata: Dict[str, Any],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Apply a specific deduplication strategy rule."""
        strategy = rule.strategy
        config = rule.configuration

        if strategy == DeduplicationStrategy.FILE_HASH:
            return await self._file_hash_deduplication(ingestion_job, config, db)

        elif strategy == DeduplicationStrategy.BUSINESS_RULES:
            return await self._business_rules_deduplication(ingestion_job, metadata, config, db)

        elif strategy == DeduplicationStrategy.TEMPORAL:
            return await self._temporal_deduplication(ingestion_job, metadata, config, db)

        elif strategy == DeduplicationStrategy.FUZZY_MATCHING:
            return await self._fuzzy_matching_deduplication(ingestion_job, file_content, config, db)

        elif strategy == DeduplicationStrategy.COMPOSITE:
            return await self._composite_deduplication(ingestion_job, file_content, metadata, config, db)

        elif strategy == DeduplicationStrategy.WORKING_CAPITAL:
            return await self._working_capital_aware_deduplication(ingestion_job, file_content, metadata, config, db)

        return []

    async def _file_hash_deduplication(
        self, ingestion_job: IngestionJob, config: Dict[str, Any], db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """File hash-based deduplication."""
        duplicates = []

        # Look for existing ingestion jobs with same file hash
        query = select(IngestionJob).where(
            and_(
                IngestionJob.file_hash_sha256 == ingestion_job.file_hash_sha256,
                IngestionJob.id != ingestion_job.id,
            )
        )
        result = await db.execute(query)
        existing_jobs = result.scalars().all()

        for existing_job in existing_jobs:
            duplicates.append({
                "confidence_score": 1.0,  # Exact match
                "matching_job_id": str(existing_job.id),
                "strategy": DeduplicationStrategy.FILE_HASH,
                "match_criteria": {
                    "file_hash": ingestion_job.file_hash_sha256,
                    "file_size": ingestion_job.file_size_bytes,
                },
                "similarity_score": 1.0,
                "comparison_details": {
                    "hash_match": True,
                    "size_match": ingestion_job.file_size_bytes == existing_job.file_size_bytes,
                },
            })

        return duplicates

    async def _business_rules_deduplication(
        self,
        ingestion_job: IngestionJob,
        metadata: Dict[str, Any],
        config: Dict[str, Any],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Business rules-based deduplication (vendor + amount + date)."""
        duplicates = []

        # Extract business criteria from metadata
        vendor_id = ingestion_job.vendor_id
        total_amount = metadata.get("total_amount")
        invoice_date = metadata.get("invoice_date")

        if not all([vendor_id, total_amount, invoice_date]):
            return duplicates

        # Look for similar invoices
        query = (
            select(Invoice, IngestionJob)
            .join(IngestionJob, Invoice.file_hash == IngestionJob.file_hash_sha256)
            .where(
                and_(
                    Invoice.vendor_id == vendor_id,
                    # Amount comparison with tolerance
                    func.abs(
                        func.cast(Invoice.total_amount, func.NUMERIC) - total_amount
                    ) <= total_amount * self.amount_tolerance,
                    # Date comparison (within configurable days)
                    func.abs(
                        func.date(Invoice.invoice_date) - invoice_date
                    ) <= config.get("date_tolerance_days", 3),
                )
            )
        )
        result = await db.execute(query)
        similar_invoices = result.all()

        for invoice, job in similar_invoices:
            # Calculate confidence based on match quality
            amount_diff = abs(float(invoice.total_amount) - float(total_amount))
            amount_confidence = 1.0 - (amount_diff / float(total_amount))

            date_diff = abs((invoice.invoice_date.date() - invoice_date).days)
            date_confidence = 1.0 - (date_diff / config.get("date_tolerance_days", 3))

            overall_confidence = (amount_confidence + date_confidence) / 2

            if overall_confidence >= config.get("confidence_threshold", 0.8):
                # Calculate working capital impact and scoring
                wc_analysis = await self._calculate_working_capital_impact(
                    invoice, total_amount, amount_diff, date_diff, db
                )

                duplicates.append({
                    "confidence_score": overall_confidence,
                    "matching_job_id": str(job.id),
                    "strategy": DeduplicationStrategy.BUSINESS_RULES,
                    "match_criteria": {
                        "vendor_id": str(vendor_id),
                        "total_amount": total_amount,
                        "invoice_date": invoice_date.isoformat(),
                    },
                    "similarity_score": overall_confidence,
                    "comparison_details": {
                        "amount_difference": amount_diff,
                        "date_difference": date_diff,
                        "amount_confidence": amount_confidence,
                        "date_confidence": date_confidence,
                    },
                    "working_capital_analysis": wc_analysis,
                })

        return duplicates

    async def _calculate_working_capital_impact(
        self,
        existing_invoice: Invoice,
        new_amount: Decimal,
        amount_diff: float,
        date_diff: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Calculate working capital impact and scoring for duplicate detection.

        This method provides CFO-relevant insights about the potential impact
        of processing duplicate invoices on working capital.
        """
        existing_amount = float(existing_invoice.total_amount)

        # Financial impact calculations
        potential_overpayment = min(float(new_amount), existing_amount)
        working_capital_tied = abs(amount_diff) if amount_diff > 0 else potential_overpayment

        # Cash flow impact timeline
        days_to_payment = self._estimate_days_to_payment(existing_invoice)
        delayed_cash_flow = working_capital_tied * (days_to_payment / 365) * 0.08  # 8% cost of capital

        # Risk assessment based on duplicate characteristics
        risk_factors = {
            "amount_variance_risk": self._assess_amount_variance_risk(amount_diff, existing_amount),
            "timing_risk": self._assess_timing_risk(date_diff),
            "vendor_risk": await self._assess_vendor_risk(existing_invoice.vendor_id, db),
            "payment_terms_risk": self._assess_payment_terms_risk(existing_invoice),
        }

        # Overall working capital score (0-100, lower is better)
        wc_score = self._calculate_wc_score(
            working_capital_tied, delayed_cash_flow, risk_factors
        )

        # CFO recommendations
        recommendations = self._generate_wc_recommendations(
            working_capital_tied, wc_score, risk_factors
        )

        # Department accountability
        accountability = self._determine_accountability(existing_invoice, risk_factors)

        return {
            "financial_impact": {
                "potential_overpayment": potential_overpayment,
                "working_capital_tied": working_capital_tied,
                "delayed_cash_flow_cost": delayed_cash_flow,
                "days_payment_delayed": days_to_payment,
                "annualized_cost": working_capital_tied * 0.08,
            },
            "risk_assessment": risk_factors,
            "working_capital_score": wc_score,
            "executive_summary": {
                "impact_level": self._categorize_impact_level(wc_score),
                "immediate_action_required": wc_score > 70,
                "cfo_attention_required": wc_score > 85,
            },
            "recommendations": recommendations,
            "accountability": accountability,
            "process_improvements": self._suggest_process_improvements(risk_factors),
        }

    def _estimate_days_to_payment(self, invoice: Invoice) -> int:
        """Estimate days to payment based on invoice data."""
        # Use payment terms if available, otherwise default to 45 days
        if hasattr(invoice, 'payment_terms') and invoice.payment_terms:
            if 'NET 30' in invoice.payment_terms:
                return 30
            elif 'NET 60' in invoice.payment_terms:
                return 60
            elif 'NET 90' in invoice.payment_terms:
                return 90

        # Default estimate based on typical AP cycles
        return 45

    def _assess_amount_variance_risk(self, amount_diff: float, original_amount: float) -> Dict[str, Any]:
        """Assess risk based on amount variance."""
        variance_percentage = (amount_diff / original_amount) * 100 if original_amount > 0 else 0

        if variance_percentage < 1:
            risk_level = "low"
            risk_score = 20
        elif variance_percentage < 5:
            risk_level = "medium"
            risk_score = 50
        else:
            risk_level = "high"
            risk_score = 80

        return {
            "level": risk_level,
            "score": risk_score,
            "variance_percentage": variance_percentage,
            "explanation": f"Amount variance of {variance_percentage:.1f}% indicates {risk_level} duplicate risk"
        }

    def _assess_timing_risk(self, date_diff: int) -> Dict[str, Any]:
        """Assess risk based on date difference."""
        if date_diff == 0:
            risk_level = "high"
            risk_score = 90
        elif date_diff <= 3:
            risk_level = "medium"
            risk_score = 60
        elif date_diff <= 7:
            risk_level = "low"
            risk_score = 30
        else:
            risk_level = "minimal"
            risk_score = 10

        return {
            "level": risk_level,
            "score": risk_score,
            "date_difference_days": date_diff,
            "explanation": f"Date difference of {date_diff} days indicates {risk_level} duplicate risk"
        }

    async def _assess_vendor_risk(self, vendor_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Assess vendor-related duplicate risk."""
        try:
            # Count previous invoices from this vendor
            query = select(func.count(Invoice.id)).where(Invoice.vendor_id == vendor_id)
            result = await db.execute(query)
            invoice_count = result.scalar() or 0

            # Check for previous duplicates (if DuplicateRecord model exists)
            try:
                duplicate_query = select(func.count(DuplicateRecord.id)).join(
                    Invoice, DuplicateRecord.invoice_id == Invoice.id
                ).where(Invoice.vendor_id == vendor_id)
                duplicate_result = await db.execute(duplicate_query)
                duplicate_count = duplicate_result.scalar() or 0
            except:
                duplicate_count = 0

            duplicate_rate = (duplicate_count / invoice_count * 100) if invoice_count > 0 else 0

            if duplicate_rate > 10:
                risk_level = "high"
                risk_score = 75
            elif duplicate_rate > 5:
                risk_level = "medium"
                risk_score = 50
            else:
                risk_level = "low"
                risk_score = 25

            return {
                "level": risk_level,
                "score": risk_score,
                "historical_invoice_count": invoice_count,
                "previous_duplicate_count": duplicate_count,
                "duplicate_rate_percentage": duplicate_rate,
                "explanation": f"Vendor has {duplicate_rate:.1f}% historical duplicate rate"
            }

        except Exception as e:
            logger.warning(f"Error assessing vendor risk: {str(e)}")
            return {
                "level": "medium",
                "score": 50,
                "explanation": "Unable to assess vendor history"
            }

    def _assess_payment_terms_risk(self, invoice: Invoice) -> Dict[str, Any]:
        """Assess risk based on payment terms."""
        if hasattr(invoice, 'payment_terms') and invoice.payment_terms:
            if 'NET 90' in invoice.payment_terms:
                risk_level = "high"
                risk_score = 70
                explanation = "Extended payment terms increase working capital risk"
            elif 'NET 60' in invoice.payment_terms:
                risk_level = "medium"
                risk_score = 50
                explanation = "Standard payment terms present moderate risk"
            else:
                risk_level = "low"
                risk_score = 30
                explanation = "Standard payment terms present lower risk"
        else:
            risk_level = "medium"
            risk_score = 50
            explanation = "Unknown payment terms present moderate risk"

        return {
            "level": risk_level,
            "score": risk_score,
            "payment_terms": getattr(invoice, 'payment_terms', 'Unknown'),
            "explanation": explanation
        }

    def _calculate_wc_score(
        self,
        working_capital_tied: float,
        delayed_cash_flow: float,
        risk_factors: Dict[str, Any]
    ) -> int:
        """Calculate overall working capital risk score."""
        # Base score from financial impact (0-40 points)
        if working_capital_tied > 10000:
            financial_score = 40
        elif working_capital_tied > 5000:
            financial_score = 30
        elif working_capital_tied > 1000:
            financial_score = 20
        else:
            financial_score = 10

        # Cash flow impact score (0-30 points)
        if delayed_cash_flow > 500:
            cash_flow_score = 30
        elif delayed_cash_flow > 200:
            cash_flow_score = 20
        elif delayed_cash_flow > 50:
            cash_flow_score = 10
        else:
            cash_flow_score = 5

        # Risk factor score (0-30 points)
        risk_scores = [
            risk_factors["amount_variance_risk"]["score"],
            risk_factors["timing_risk"]["score"],
            risk_factors["vendor_risk"]["score"],
            risk_factors["payment_terms_risk"]["score"]
        ]
        avg_risk_score = sum(risk_scores) / len(risk_scores)
        risk_score = (avg_risk_score / 100) * 30

        total_score = financial_score + cash_flow_score + risk_score
        return min(100, int(total_score))

    def _categorize_impact_level(self, wc_score: int) -> str:
        """Categorize working capital impact level."""
        if wc_score >= 85:
            return "critical"
        elif wc_score >= 70:
            return "high"
        elif wc_score >= 50:
            return "medium"
        elif wc_score >= 30:
            return "low"
        else:
            return "minimal"

    def _generate_wc_recommendations(
        self,
        working_capital_tied: float,
        wc_score: int,
        risk_factors: Dict[str, Any]
    ) -> List[str]:
        """Generate working capital management recommendations."""
        recommendations = []

        if wc_score >= 85:
            recommendations.extend([
                "IMMEDIATE ACTION: Investigate potential duplicate payment",
                "Escalate to Finance Director for review",
                "Consider placing vendor payment on hold",
                "Review all recent payments to this vendor"
            ])
        elif wc_score >= 70:
            recommendations.extend([
                "High priority review required",
                "Enhanced validation before payment processing",
                "Manager approval required for this invoice"
            ])
        elif wc_score >= 50:
            recommendations.extend([
                "Standard duplicate verification process",
                "Additional documentation may be required",
                "Monitor vendor payment history"
            ])

        # Specific recommendations based on risk factors
        if risk_factors["amount_variance_risk"]["level"] == "high":
            recommendations.append("Implement tighter amount matching tolerances")

        if risk_factors["timing_risk"]["level"] == "high":
            recommendations.append("Enhance same-day duplicate detection")

        if risk_factors["vendor_risk"]["level"] == "high":
            recommendations.append("Review vendor onboarding and verification process")

        if working_capital_tied > 5000:
            recommendations.append("Consider working capital optimization strategies")

        return recommendations

    def _determine_accountability(
        self,
        invoice: Invoice,
        risk_factors: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Determine department accountability for duplicate prevention."""
        accountability = {
            "primary_department": "AP Operations",
            "supporting_departments": [],
            "process_owners": []
        }

        # Based on risk factors, determine accountability
        if risk_factors["amount_variance_risk"]["score"] > 70:
            accountability["supporting_departments"].append("Finance")
            accountability["process_owners"].append("Finance Manager")

        if risk_factors["vendor_risk"]["score"] > 70:
            accountability["supporting_departments"].append("Procurement")
            accountability["process_owners"].append("Vendor Manager")

        if risk_factors["timing_risk"]["score"] > 70:
            accountability["supporting_departments"].append("IT Systems")
            accountability["process_owners"].append("Systems Administrator")

        accountability["recommendation"] = (
            f"Primary accountability rests with {accountability['primary_department']} "
            f"with support from {', '.join(accountability['supporting_departments']) if accountability['supporting_departments'] else 'no supporting departments'}"
        )

        return accountability

    def _suggest_process_improvements(self, risk_factors: Dict[str, Any]) -> List[str]:
        """Suggest process improvements based on risk assessment."""
        improvements = []

        if risk_factors["amount_variance_risk"]["score"] > 50:
            improvements.append("Implement automated amount validation with real-time duplicate checking")

        if risk_factors["timing_risk"]["score"] > 50:
            improvements.append("Enhance same-day submission detection and alerts")

        if risk_factors["vendor_risk"]["score"] > 50:
            improvements.append("Implement vendor risk scoring and monitoring")

        if risk_factors["payment_terms_risk"]["score"] > 50:
            improvements.append("Review and standardize payment terms across vendors")

        improvements.extend([
            "Regular duplicate detection audits and process reviews",
            "Enhanced staff training on duplicate identification",
            "Implement machine learning for pattern recognition",
            "Quarterly working capital impact analysis"
        ])

        return improvements

    async def _temporal_deduplication(
        self,
        ingestion_job: IngestionJob,
        metadata: Dict[str, Any],
        config: Dict[str, Any],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Temporal deduplication within time windows."""
        duplicates = []

        # Get time window from config
        window_hours = config.get("window_hours", self.temporal_window_hours)
        time_threshold = ingestion_job.created_at - timedelta(hours=window_hours)

        # Look for ingestion jobs within time window
        query = select(IngestionJob).where(
            and_(
                IngestionJob.created_at >= time_threshold,
                IngestionJob.created_at <= ingestion_job.created_at,
                IngestionJob.id != ingestion_job.id,
            )
        )
        result = await db.execute(query)
        recent_jobs = result.scalars().all()

        for recent_job in recent_jobs:
            # Calculate time-based confidence
            time_diff = (ingestion_job.created_at - recent_job.created_at).total_seconds()
            time_confidence = 1.0 - (time_diff / (window_hours * 3600))

            # Check additional criteria
            criteria_matches = []

            # Same vendor
            if ingestion_job.vendor_id and recent_job.vendor_id:
                if ingestion_job.vendor_id == recent_job.vendor_id:
                    criteria_matches.append("vendor_match")
                    time_confidence += 0.2

            # Similar file size
            size_diff_ratio = abs(ingestion_job.file_size_bytes - recent_job.file_size_bytes) / max(
                ingestion_job.file_size_bytes, recent_job.file_size_bytes
            )
            if size_diff_ratio < 0.1:  # Within 10% size difference
                criteria_matches.append("size_match")
                time_confidence += 0.1

            # Same file type
            if ingestion_job.file_extension == recent_job.file_extension:
                criteria_matches.append("type_match")
                time_confidence += 0.1

            # Cap confidence at 1.0
            time_confidence = min(time_confidence, 1.0)

            if time_confidence >= config.get("confidence_threshold", 0.6):
                duplicates.append({
                    "confidence_score": time_confidence,
                    "matching_job_id": str(recent_job.id),
                    "strategy": DeduplicationStrategy.TEMPORAL,
                    "match_criteria": {
                        "time_window_hours": window_hours,
                        "time_diff_seconds": time_diff,
                        "criteria_matches": criteria_matches,
                    },
                    "similarity_score": time_confidence,
                    "comparison_details": {
                        "time_diff_hours": time_diff / 3600,
                        "size_diff_ratio": size_diff_ratio,
                        "vendor_match": ingestion_job.vendor_id == recent_job.vendor_id,
                    },
                })

        return duplicates

    async def _fuzzy_matching_deduplication(
        self,
        ingestion_job: IngestionJob,
        file_content: bytes,
        config: Dict[str, Any],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fuzzy matching based on content similarity."""
        duplicates = []

        # Extract text content from file for comparison
        current_text = await self._extract_text_content(file_content, ingestion_job.mime_type)
        if not current_text:
            return duplicates

        # Get recent ingestion jobs for comparison
        days_back = config.get("days_back", 30)
        date_threshold = ingestion_job.created_at - timedelta(days=days_back)

        query = select(IngestionJob).where(
            and_(
                IngestionJob.created_at >= date_threshold,
                IngestionJob.id != ingestion_job.id,
                IngestionJob.mime_type == ingestion_job.mime_type,  # Same file type
            )
        ).limit(config.get("max_comparisons", 50))  # Limit comparisons for performance

        result = await db.execute(query)
        comparison_jobs = result.scalars().all()

        for comparison_job in comparison_jobs:
            try:
                # Get comparison file content and extract text
                comparison_text = await self._get_job_text_content(comparison_job)
                if not comparison_text:
                    continue

                # Calculate text similarity
                similarity = await self._calculate_text_similarity(current_text, comparison_text)

                if similarity >= self.fuzzy_similarity_threshold:
                    duplicates.append({
                        "confidence_score": similarity,
                        "matching_job_id": str(comparison_job.id),
                        "strategy": DeduplicationStrategy.FUZZY_MATCHING,
                        "match_criteria": {
                            "similarity_threshold": self.fuzzy_similarity_threshold,
                            "text_similarity": similarity,
                        },
                        "similarity_score": similarity,
                        "comparison_details": {
                            "text_length_current": len(current_text),
                            "text_length_comparison": len(comparison_text),
                            "similarity_method": "sequence_matcher",
                        },
                    })

            except Exception as e:
                logger.warning(f"Fuzzy matching failed for job {comparison_job.id}: {e}")
                continue

        return duplicates

    async def _composite_deduplication(
        self,
        ingestion_job: IngestionJob,
        file_content: bytes,
        metadata: Dict[str, Any],
        config: Dict[str, Any],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Composite deduplication combining multiple strategies."""
        all_duplicates = []

        # Get strategies to combine
        strategies = config.get("strategies", [
            DeduplicationStrategy.FILE_HASH,
            DeduplicationStrategy.BUSINESS_RULES,
            DeduplicationStrategy.TEMPORAL,
        ])

        # Apply each strategy
        for strategy in strategies:
            rule_config = config.get("strategy_configs", {}).get(strategy.value, {})
            mock_rule = DeduplicationRule(
                strategy=strategy,
                configuration=rule_config,
            )

            strategy_duplicates = await self._apply_strategy_rule(
                mock_rule, ingestion_job, file_content, metadata, db
            )
            all_duplicates.extend(strategy_duplicates)

        # Combine duplicates by matching job
        combined_duplicates = {}
        for duplicate in all_duplicates:
            job_id = duplicate["matching_job_id"]
            if job_id not in combined_duplicates:
                combined_duplicates[job_id] = {
                    "confidence_score": 0.0,
                    "strategies_used": [],
                    "match_criteria": {},
                    "comparison_details": {},
                    "matching_job_id": job_id,
                }

            # Weight and combine confidence scores
            weight = config.get("strategy_weights", {}).get(
                duplicate["strategy"].value, 1.0
            )
            combined_duplicates[job_id]["confidence_score"] += (
                duplicate["confidence_score"] * weight
            )
            combined_duplicates[job_id]["strategies_used"].append(duplicate["strategy"].value)

            # Merge match criteria and comparison details
            combined_duplicates[job_id]["match_criteria"].update(duplicate["match_criteria"])
            combined_duplicates[job_id]["comparison_details"].update(duplicate["comparison_details"])

        # Normalize confidence scores
        total_weight = sum(
            config.get("strategy_weights", {}).get(strategy.value, 1.0)
            for strategy in strategies
        )

        for duplicate in combined_duplicates.values():
            duplicate["confidence_score"] /= total_weight
            duplicate["strategy"] = DeduplicationStrategy.COMPOSITE
            duplicate["similarity_score"] = duplicate["confidence_score"]

        # Filter by composite confidence threshold
        threshold = config.get("confidence_threshold", 0.7)
        filtered_duplicates = [
            dup for dup in combined_duplicates.values()
            if dup["confidence_score"] >= threshold
        ]

        return filtered_duplicates

    async def _working_capital_aware_deduplication(
        self,
        ingestion_job: IngestionJob,
        file_content: bytes,
        metadata: Dict[str, Any],
        config: Dict[str, Any],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Working capital-aware deduplication that extends composite detection
        with financial impact analysis and cash flow sensitivity thresholds.
        """
        # Start with base composite deduplication
        composite_duplicates = await self._composite_deduplication(ingestion_job, file_content, metadata, config, db)

        if not composite_duplicates:
            return []

        # Working capital configuration
        wc_config = config.get("working_capital", {
            "cost_of_capital": 0.08,  # 8% annual cost of capital
            "cash_flow_sensitivity_threshold": 0.15,  # 15% impact threshold
            "min_financial_impact_threshold": 1000.00,  # $1,000 minimum impact
            "working_capital_weight": 0.3,  # Weight for WC scoring in overall confidence
        })

        enhanced_duplicates = []

        for duplicate in composite_duplicates:
            try:
                # Get the matching invoice for detailed analysis
                matching_invoice = await self._get_matching_invoice(duplicate["matching_job_id"], db)
                if not matching_invoice:
                    continue

                # Calculate working capital impact
                wc_impact = await calculate_duplicate_working_capital_impact(
                    current_invoice=matching_invoice,
                    duplicate_job_id=duplicate["matching_job_id"],
                    current_metadata=metadata,
                    cost_of_capital=wc_config["cost_of_capital"],
                    db=db
                )

                # Calculate cash flow sensitivity score
                sensitivity_score = self._calculate_cash_flow_sensitivity(
                    wc_impact, wc_config["cash_flow_sensitivity_threshold"]
                )

                # Apply working capital weighting to confidence score
                wc_weighted_confidence = self._apply_working_capital_weighting(
                    duplicate["confidence_score"],
                    wc_impact["working_capital_score"],
                    wc_config["working_capital_weight"]
                )

                # Filter by financial impact threshold
                if wc_impact["financial_impact"]["working_capital_tied"] >= wc_config["min_financial_impact_threshold"]:
                    enhanced_duplicate = duplicate.copy()
                    enhanced_duplicate.update({
                        "confidence_score": wc_weighted_confidence,
                        "strategy": DeduplicationStrategy.WORKING_CAPITAL,
                        "working_capital_analysis": wc_impact,
                        "cash_flow_sensitivity_score": sensitivity_score,
                        "financial_priority": self._determine_financial_priority(wc_impact),
                        "working_capital_weighting": {
                            "original_confidence": duplicate["confidence_score"],
                            "wc_score": wc_impact["working_capital_score"],
                            "wc_weight": wc_config["working_capital_weight"],
                            "final_confidence": wc_weighted_confidence
                        }
                    })
                    enhanced_duplicates.append(enhanced_duplicate)

            except Exception as e:
                logger.warning(f"Failed to enhance duplicate {duplicate['matching_job_id']} with working capital analysis: {e}")
                # Keep original duplicate if WC analysis fails
                enhanced_duplicates.append(duplicate)

        # Sort by working capital weighted confidence (highest first)
        enhanced_duplicates.sort(key=lambda x: x.get("cash_flow_sensitivity_score", 0), reverse=True)

        return enhanced_duplicates

    async def _get_matching_invoice(self, job_id: str, db: AsyncSession) -> Optional[Invoice]:
        """Get the invoice associated with a matching job ID."""
        try:
            query = (
                select(Invoice)
                .join(IngestionJob, Invoice.file_hash == IngestionJob.file_hash_sha256)
                .where(IngestionJob.id == UUID(job_id))
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"Failed to get matching invoice for job {job_id}: {e}")
            return None

    def _calculate_cash_flow_sensitivity(self, wc_impact: Dict[str, Any], threshold: float) -> float:
        """
        Calculate cash flow sensitivity score based on working capital impact.

        Returns a score between 0-1 where higher values indicate greater cash flow sensitivity.
        """
        financial_impact = wc_impact["financial_impact"]

        # Base sensitivity from delayed cash flow cost
        delayed_cost = financial_impact["delayed_cash_flow_cost"]
        working_capital_tied = financial_impact["working_capital_tied"]

        # Calculate sensitivity ratio
        if working_capital_tied > 0:
            sensitivity_ratio = delayed_cost / working_capital_tied
        else:
            sensitivity_ratio = 0

        # Normalize to 0-1 range based on threshold
        sensitivity_score = min(1.0, sensitivity_ratio / threshold)

        # Adjust for working capital score (higher WC score = higher sensitivity)
        wc_score_factor = wc_impact["working_capital_score"] / 100
        sensitivity_score = sensitivity_score * (0.7 + 0.3 * wc_score_factor)

        return round(sensitivity_score, 3)

    def _apply_working_capital_weighting(self, original_confidence: float, wc_score: int, wc_weight: float) -> float:
        """
        Apply working capital weighting to the original confidence score.

        Args:
            original_confidence: Base confidence from composite deduplication
            wc_score: Working capital impact score (0-100)
            wc_weight: Weight to apply to working capital analysis (0-1)

        Returns:
            Weighted confidence score
        """
        # Normalize WC score to 0-1 range
        wc_score_normalized = wc_score / 100

        # Apply weighted average
        weighted_confidence = (
            original_confidence * (1 - wc_weight) +
            wc_score_normalized * wc_weight
        )

        return round(weighted_confidence, 3)

    def _determine_financial_priority(self, wc_impact: Dict[str, Any]) -> str:
        """Determine financial priority level based on working capital impact."""
        wc_score = wc_impact["working_capital_score"]
        impact_amount = wc_impact["financial_impact"]["working_capital_tied"]

        if wc_score >= 85 and impact_amount >= 10000:
            return "critical"
        elif wc_score >= 70 and impact_amount >= 5000:
            return "high"
        elif wc_score >= 50 and impact_amount >= 1000:
            return "medium"
        else:
            return "low"

    async def _extract_text_content(self, file_content: bytes, mime_type: str) -> Optional[str]:
        """Extract text content from file for similarity comparison."""
        try:
            if mime_type == "application/pdf":
                # Use PDF text extraction
                return await self._extract_pdf_text(file_content)
            elif mime_type.startswith("text/"):
                # Direct text content
                return file_content.decode("utf-8", errors="ignore")
            elif mime_type.startswith("image/"):
                # Use OCR for images
                return await self._extract_image_text(file_content)
            else:
                logger.warning(f"No text extraction method for MIME type: {mime_type}")
                return None

        except Exception as e:
            logger.warning(f"Text extraction failed: {e}")
            return None

    async def _extract_pdf_text(self, file_content: bytes) -> Optional[str]:
        """Extract text from PDF content."""
        # Placeholder - would use libraries like PyPDF2, pdfplumber, or pdfminer
        return "extracted pdf text placeholder"

    async def _extract_image_text(self, file_content: bytes) -> Optional[str]:
        """Extract text from image content using OCR."""
        # Placeholder - would use OCR libraries like pytesseract
        return "extracted image text placeholder"

    async def _get_job_text_content(self, job: IngestionJob) -> Optional[str]:
        """Get text content from an existing ingestion job."""
        try:
            # This would retrieve the file content and extract text
            # For now, return a placeholder
            return f"text content for job {job.id}"

        except Exception as e:
            logger.warning(f"Failed to get text content for job {job.id}: {e}")
            return None

    async def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        try:
            # Use SequenceMatcher for text similarity
            similarity = SequenceMatcher(None, text1, text2).ratio()

            # Could also use more advanced methods like:
            # - TF-IDF vector similarity
            # - Word embeddings
            # - Cosine similarity

            return similarity

        except Exception as e:
            logger.warning(f"Text similarity calculation failed: {e}")
            return 0.0

    async def _create_duplicate_records(
        self, ingestion_job: IngestionJob, duplicates: List[Dict[str, Any]], db: AsyncSession
    ) -> None:
        """Create duplicate records in the database."""
        for duplicate_data in duplicates:
            duplicate_record = DuplicateRecord(
                ingestion_job_id=ingestion_job.id,
                detection_strategy=duplicate_data["strategy"],
                confidence_score=duplicate_data["confidence_score"],
                similarity_score=duplicate_data.get("similarity_score"),
                match_criteria=duplicate_data["match_criteria"],
                comparison_details=duplicate_data.get("comparison_details"),
                requires_human_review=duplicate_data["confidence_score"] < 0.95,
                status="detected",
            )
            db.add(duplicate_record)

        await db.commit()

    async def _apply_group_resolution(
        self, duplicates: List[DuplicateRecord], resolution: DuplicateResolution, db: AsyncSession
    ) -> None:
        """Apply resolution action to a group of duplicates."""
        # This would implement the logic for resolving duplicate groups
        # Implementation depends on specific business requirements
        pass

    def _is_valid_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID."""
        try:
            UUID(value)
            return True
        except ValueError:
            return False


async def calculate_duplicate_working_capital_impact(
    current_invoice: Invoice,
    duplicate_job_id: str,
    current_metadata: Dict[str, Any],
    cost_of_capital: float = 0.08,
    db: AsyncSession = None,
) -> Dict[str, Any]:
    """
    Calculate working capital impact of duplicate detection with financial metrics.

    This function leverages existing working_capital_analytics.py impact calculation methods
    and extends them with duplicate-specific financial analysis.

    Args:
        current_invoice: The existing invoice that's being compared against
        duplicate_job_id: ID of the potentially duplicate ingestion job
        current_metadata: Extracted metadata from the duplicate invoice
        cost_of_capital: Annual cost of capital (default 8%)
        db: Database session for additional data retrieval

    Returns:
        Comprehensive working capital impact analysis
    """
    try:
        # Extract financial information
        current_amount = float(current_invoice.total_amount)
        duplicate_amount = float(current_metadata.get("total_amount", 0))

        # If no duplicate amount, use current amount (worst case)
        if duplicate_amount == 0:
            duplicate_amount = current_amount

        # Calculate potential overpayment
        potential_overpayment = min(current_amount, duplicate_amount)

        # Estimate payment terms (days)
        payment_terms_days = _estimate_payment_terms(current_invoice)

        # Leverage existing working capital analytics calculation
        days_to_payment = payment_terms_days

        # Calculate working capital tied up by duplicate
        working_capital_tied = abs(duplicate_amount - current_amount) if duplicate_amount != current_amount else potential_overpayment

        # Calculate delayed cash flow cost using cost of capital
        delayed_cash_flow_cost = working_capital_tied * (days_to_payment / 365) * cost_of_capital

        # Calculate annualized cost of capital
        annualized_cost = working_capital_tied * cost_of_capital

        # Risk assessment for working capital impact
        risk_assessment = _assess_wc_risk_factors(
            current_invoice, duplicate_amount - current_amount, db
        )

        # Working capital impact score (0-100, higher = more critical)
        wc_impact_score = _calculate_working_capital_impact_score(
            working_capital_tied, delayed_cash_flow_cost, risk_assessment
        )

        # Generate CFO-relevant recommendations
        recommendations = _generate_wc_recommendations(wc_impact_score, working_capital_tied, risk_assessment)

        # Cash flow sensitivity analysis
        cash_flow_analysis = _calculate_cash_flow_sensitivity_analysis(
            working_capital_tied, delayed_cash_flow_cost, days_to_payment, cost_of_capital
        )

        return {
            "financial_impact": {
                "potential_overpayment": round(potential_overpayment, 2),
                "working_capital_tied": round(working_capital_tied, 2),
                "delayed_cash_flow_cost": round(delayed_cash_flow_cost, 2),
                "annualized_cost": round(annualized_cost, 2),
                "days_payment_delayed": days_to_payment,
                "cost_of_capital_rate": cost_of_capital,
            },
            "cash_flow_analysis": cash_flow_analysis,
            "risk_assessment": risk_assessment,
            "working_capital_score": wc_impact_score,
            "executive_summary": {
                "impact_level": _categorize_impact_level(wc_impact_score),
                "immediate_action_required": wc_impact_score > 70,
                "cfo_attention_required": wc_impact_score > 85,
                "financial_priority": _determine_financial_priority_level(wc_impact_score, working_capital_tied),
            },
            "recommendations": recommendations,
            "duplicate_details": {
                "current_invoice_id": str(current_invoice.id),
                "duplicate_job_id": duplicate_job_id,
                "current_amount": current_amount,
                "duplicate_amount": duplicate_amount,
                "amount_difference": abs(duplicate_amount - current_amount),
                "duplicate_percentage": (abs(duplicate_amount - current_amount) / current_amount * 100) if current_amount > 0 else 0,
            },
            "process_accountability": _determine_wc_accountability(current_invoice, risk_assessment),
        }

    except Exception as e:
        logger.error(f"Error calculating working capital impact: {e}")
        # Return minimal impact data on error
        return {
            "financial_impact": {
                "potential_overpayment": 0,
                "working_capital_tied": 0,
                "delayed_cash_flow_cost": 0,
                "annualized_cost": 0,
                "days_payment_delayed": 45,
                "cost_of_capital_rate": cost_of_capital,
            },
            "working_capital_score": 0,
            "executive_summary": {
                "impact_level": "minimal",
                "immediate_action_required": False,
                "cfo_attention_required": False,
                "financial_priority": "low",
            },
            "recommendations": ["Unable to calculate working capital impact due to system error"],
            "error": str(e),
        }


def _estimate_payment_terms(invoice: Invoice) -> int:
    """Estimate payment terms from invoice data."""
    # Check for explicit payment terms
    if hasattr(invoice, 'payment_terms') and invoice.payment_terms:
        terms = invoice.payment_terms.upper()
        if 'NET 30' in terms:
            return 30
        elif 'NET 60' in terms:
            return 60
        elif 'NET 90' in terms:
            return 90
        elif 'NET 15' in terms:
            return 15
        elif 'NET 45' in terms:
            return 45

    # Default estimate based on industry standards
    return 45


async def _assess_wc_risk_factors(invoice: Invoice, amount_diff: float, db: AsyncSession) -> Dict[str, Any]:
    """Assess risk factors for working capital impact."""
    risk_factors = {
        "amount_variance_risk": _assess_amount_risk(amount_diff, float(invoice.total_amount)),
        "payment_terms_risk": _assess_payment_terms_risk(invoice),
        "vendor_risk": await _assess_vendor_wc_risk(invoice.vendor_id, db) if db else {"score": 50, "level": "medium"},
        "timing_risk": _assess_timing_wc_risk(invoice),
    }

    # Calculate overall risk score
    risk_scores = [risk["score"] for risk in risk_factors.values() if "score" in risk]
    overall_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 50

    risk_factors["overall_risk"] = {
        "score": round(overall_risk_score, 1),
        "level": _categorize_risk_level(overall_risk_score),
        "explanation": f"Overall working capital risk level: {_categorize_risk_level(overall_risk_score)}"
    }

    return risk_factors


def _assess_amount_risk(amount_diff: float, original_amount: float) -> Dict[str, Any]:
    """Assess risk based on amount variance."""
    if original_amount == 0:
        return {"score": 50, "level": "medium", "explanation": "Unable to assess amount risk"}

    variance_percentage = abs(amount_diff / original_amount) * 100

    if variance_percentage < 1:
        return {"score": 20, "level": "low", "variance_percentage": variance_percentage}
    elif variance_percentage < 5:
        return {"score": 50, "level": "medium", "variance_percentage": variance_percentage}
    elif variance_percentage < 15:
        return {"score": 70, "level": "high", "variance_percentage": variance_percentage}
    else:
        return {"score": 90, "level": "critical", "variance_percentage": variance_percentage}


def _assess_payment_terms_risk(invoice: Invoice) -> Dict[str, Any]:
    """Assess payment terms risk for working capital."""
    if hasattr(invoice, 'payment_terms') and invoice.payment_terms:
        terms = invoice.payment_terms.upper()
        if 'NET 90' in terms:
            return {"score": 80, "level": "high", "payment_terms": terms, "explanation": "Extended terms increase WC risk"}
        elif 'NET 60' in terms:
            return {"score": 60, "level": "medium", "payment_terms": terms, "explanation": "Standard terms present moderate WC risk"}
        else:
            return {"score": 40, "level": "low", "payment_terms": terms, "explanation": "Favorable terms present lower WC risk"}
    else:
        return {"score": 50, "level": "medium", "explanation": "Unknown payment terms present moderate WC risk"}


async def _assess_vendor_wc_risk(vendor_id: str, db: AsyncSession) -> Dict[str, Any]:
    """Assess vendor working capital risk."""
    try:
        # Count historical invoices from this vendor
        query = select(func.count(Invoice.id)).where(Invoice.vendor_id == vendor_id)
        result = await db.execute(query)
        invoice_count = result.scalar() or 0

        # Check average invoice amount
        avg_query = select(func.avg(Invoice.total_amount)).where(Invoice.vendor_id == vendor_id)
        avg_result = await db.execute(avg_query)
        avg_amount = float(avg_result.scalar() or 0)

        # Vendor risk based on invoice volume and average amount
        if invoice_count > 100 and avg_amount > 10000:
            return {"score": 70, "level": "high", "explanation": "High-volume, high-value vendor"}
        elif invoice_count > 50 or avg_amount > 5000:
            return {"score": 50, "level": "medium", "explanation": "Moderate-volume or value vendor"}
        else:
            return {"score": 30, "level": "low", "explanation": "Lower-volume vendor"}

    except Exception as e:
        logger.warning(f"Error assessing vendor WC risk: {e}")
        return {"score": 50, "level": "medium", "explanation": "Unable to assess vendor WC risk"}


def _assess_timing_wc_risk(invoice: Invoice) -> Dict[str, Any]:
    """Assess timing-related working capital risk."""
    # Check if invoice is recent (higher risk for immediate payment)
    days_since_invoice = (datetime.now(timezone.utc) - invoice.invoice_date).days

    if days_since_invoice <= 7:
        return {"score": 80, "level": "high", "days_since_invoice": days_since_invoice, "explanation": "Recent invoice presents immediate WC risk"}
    elif days_since_invoice <= 30:
        return {"score": 60, "level": "medium", "days_since_invoice": days_since_invoice, "explanation": "Recent invoice presents moderate WC risk"}
    else:
        return {"score": 30, "level": "low", "days_since_invoice": days_since_invoice, "explanation": "Older invoice presents lower WC risk"}


def _categorize_risk_level(score: float) -> str:
    """Categorize risk level based on score."""
    if score >= 80:
        return "critical"
    elif score >= 60:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"


def _calculate_working_capital_impact_score(working_capital_tied: float, delayed_cash_flow: float, risk_assessment: Dict[str, Any]) -> int:
    """Calculate overall working capital impact score."""
    # Financial impact component (0-40 points)
    if working_capital_tied > 25000:
        financial_score = 40
    elif working_capital_tied > 10000:
        financial_score = 30
    elif working_capital_tied > 5000:
        financial_score = 20
    elif working_capital_tied > 1000:
        financial_score = 15
    else:
        financial_score = 10

    # Cash flow impact component (0-30 points)
    if delayed_cash_flow > 1000:
        cash_flow_score = 30
    elif delayed_cash_flow > 500:
        cash_flow_score = 25
    elif delayed_cash_flow > 200:
        cash_flow_score = 20
    elif delayed_cash_flow > 50:
        cash_flow_score = 15
    else:
        cash_flow_score = 10

    # Risk factor component (0-30 points)
    if "overall_risk" in risk_assessment and "score" in risk_assessment["overall_risk"]:
        risk_score = (risk_assessment["overall_risk"]["score"] / 100) * 30
    else:
        risk_score = 15  # Default medium risk

    total_score = financial_score + cash_flow_score + risk_score
    return min(100, int(total_score))


def _categorize_impact_level(score: int) -> str:
    """Categorize working capital impact level."""
    if score >= 85:
        return "critical"
    elif score >= 70:
        return "high"
    elif score >= 50:
        return "medium"
    elif score >= 30:
        return "low"
    else:
        return "minimal"


def _determine_financial_priority_level(score: int, working_capital_tied: float) -> str:
    """Determine financial priority level."""
    if score >= 85 and working_capital_tied >= 10000:
        return "critical"
    elif score >= 70 and working_capital_tied >= 5000:
        return "high"
    elif score >= 50 and working_capital_tied >= 1000:
        return "medium"
    else:
        return "low"


def _generate_wc_recommendations(score: int, working_capital_tied: float, risk_assessment: Dict[str, Any]) -> List[str]:
    """Generate working capital management recommendations."""
    recommendations = []

    if score >= 85:
        recommendations.extend([
            "IMMEDIATE ACTION: Place vendor payment on hold pending duplicate verification",
            "Escalate to Finance Director and Controller immediately",
            "Review all payments to this vendor in the last 90 days",
            "Implement enhanced duplicate detection for this vendor"
        ])
    elif score >= 70:
        recommendations.extend([
            "High priority verification required before payment processing",
            "Enhanced documentation and approval workflow required",
            "Review vendor payment history and duplicate patterns"
        ])
    elif score >= 50:
        recommendations.extend([
            "Standard duplicate verification process required",
            "Additional approval may be needed for high-value duplicates",
            "Monitor for duplicate patterns with this vendor"
        ])

    # Specific recommendations based on risk factors
    if working_capital_tied > 10000:
        recommendations.append("Consider working capital optimization strategies")

    if "overall_risk" in risk_assessment:
        if risk_assessment["overall_risk"]["level"] == "critical":
            recommendations.append("Implement immediate process review for high-risk vendors")
        elif risk_assessment["overall_risk"]["level"] == "high":
            recommendations.append("Enhanced monitoring and controls recommended")

    return recommendations


def _calculate_cash_flow_sensitivity_analysis(working_capital_tied: float, delayed_cost: float, days: int, cost_of_capital: float) -> Dict[str, Any]:
    """Calculate detailed cash flow sensitivity analysis."""
    # Calculate sensitivity ratios
    if working_capital_tied > 0:
        cost_ratio = delayed_cost / working_capital_tied
        daily_cost = working_capital_tied * cost_of_capital / 365
    else:
        cost_ratio = 0
        daily_cost = 0

    # Calculate impact at different time horizons
    impact_30_days = working_capital_tied * (30 / 365) * cost_of_capital
    impact_60_days = working_capital_tied * (60 / 365) * cost_of_capital
    impact_90_days = working_capital_tied * (90 / 365) * cost_of_capital

    return {
        "cost_ratio": round(cost_ratio, 4),
        "daily_cost_of_capital": round(daily_cost, 2),
        "projected_costs": {
            "30_days": round(impact_30_days, 2),
            "60_days": round(impact_60_days, 2),
            "90_days": round(impact_90_days, 2),
        },
        "sensitivity_metrics": {
            "working_capital_tied": round(working_capital_tied, 2),
            "delayed_cash_flow_cost": round(delayed_cost, 2),
            "days_to_payment": days,
            "cost_of_capital": cost_of_capital,
        },
        "recommendations": _generate_cash_flow_recommendations(cost_ratio, daily_cost)
    }


def _generate_cash_flow_recommendations(cost_ratio: float, daily_cost: float) -> List[str]:
    """Generate cash flow-specific recommendations."""
    recommendations = []

    if cost_ratio > 0.15:
        recommendations.append("High cash flow sensitivity - expedite duplicate resolution")
    elif cost_ratio > 0.10:
        recommendations.append("Moderate cash flow sensitivity - prioritize resolution")
    else:
        recommendations.append("Lower cash flow sensitivity - standard resolution process")

    if daily_cost > 50:
        recommendations.append("High daily cost of capital - immediate resolution recommended")
    elif daily_cost > 20:
        recommendations.append("Significant daily cost - expedite resolution")

    return recommendations


def _determine_wc_accountability(invoice: Invoice, risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
    """Determine accountability for working capital duplicate prevention."""
    accountability = {
        "primary_department": "AP Operations",
        "supporting_departments": [],
        "process_owners": ["AP Manager"],
        "financial_accountability": "Finance Director"
    }

    # Add supporting departments based on risk factors
    if risk_assessment.get("vendor_risk", {}).get("level") in ["high", "critical"]:
        accountability["supporting_departments"].append("Procurement")
        accountability["process_owners"].append("Vendor Manager")

    if risk_assessment.get("amount_variance_risk", {}).get("level") in ["high", "critical"]:
        accountability["supporting_departments"].append("Finance")
        accountability["process_owners"].append("Finance Controller")

    if risk_assessment.get("timing_risk", {}).get("level") in ["high", "critical"]:
        accountability["supporting_departments"].append("IT Systems")
        accountability["process_owners"].append("Systems Administrator")

    return accountability