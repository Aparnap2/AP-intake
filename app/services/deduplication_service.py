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
        limit: int = 100,
        vendor_id: Optional[str] = None,
        status: Optional[str] = None,
        db: AsyncSession,
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
        resolution_notes: Optional[str] = None,
        db: AsyncSession,
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
                })

        return duplicates

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