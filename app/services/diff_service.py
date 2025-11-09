"""
Diff generation service for comparing export data and changes.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DiffException

logger = logging.getLogger(__name__)


@dataclass
class DiffChange:
    """Represents a single change in a diff comparison."""
    field_path: str
    change_type: str  # added, removed, modified, moved
    old_value: Any
    new_value: Any
    change_magnitude: Optional[float] = None
    significance: str = "medium"  # low, medium, high, critical


@dataclass
class DiffSummary:
    """Summary of diff comparison."""
    total_changes: int
    added_fields: int
    removed_fields: int
    modified_fields: int
    critical_changes: int
    high_changes: int
    medium_changes: int
    low_changes: int
    overall_significance: str


class DiffEngine:
    """Engine for generating and analyzing diffs."""

    def __init__(self):
        """Initialize the diff engine."""
        self.significance_rules = {
            # Header fields - high importance
            'header.invoice_no': 'critical',
            'header.vendor_name': 'critical',
            'header.total': 'high',
            'header.currency': 'high',
            'header.invoice_date': 'high',
            'header.due_date': 'medium',
            'header.po_no': 'medium',

            # Line items - medium to high importance
            'lines.*.description': 'medium',
            'lines.*.amount': 'high',
            'lines.*.quantity': 'medium',
            'lines.*.unit_price': 'high',

            # Calculated fields - critical if they change
            'header.subtotal': 'high',
            'header.tax': 'medium',

            # Default significance
            'default': 'medium'
        }

    def generate_diff(
        self,
        original_data: Dict[str, Any],
        modified_data: Dict[str, Any],
        comparison_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a comprehensive diff comparison."""
        logger.info(f"Generating diff for: {comparison_name}")

        try:
            # Generate changes
            changes = self._compare_dicts(original_data, modified_data, "")

            # Analyze significance
            analyzed_changes = self._analyze_changes(changes)

            # Create summary
            summary = self._create_summary(analyzed_changes)

            # Generate diff data
            diff_data = {
                "comparison_id": str(uuid.uuid4()),
                "comparison_name": comparison_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "original_data": original_data,
                "modified_data": modified_data,
                "changes": [self._serialize_change(change) for change in analyzed_changes],
                "summary": self._serialize_summary(summary),
                "context": context or {}
            }

            # Store diff if configured
            if settings.STORE_DIFFS:
                self._store_diff(diff_data)

            logger.info(f"Diff generated: {summary.total_changes} changes")
            return diff_data

        except Exception as e:
            logger.error(f"Failed to generate diff: {e}")
            raise DiffException(f"Failed to generate diff: {str(e)}")

    def _compare_dicts(
        self,
        original: Dict[str, Any],
        modified: Dict[str, Any],
        path: str = ""
    ) -> List[DiffChange]:
        """Compare two dictionaries and return list of changes."""
        changes = []

        # Get all unique keys
        all_keys = set(original.keys()) | set(modified.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key

            if key not in original:
                # Field was added
                changes.append(DiffChange(
                    field_path=current_path,
                    change_type="added",
                    old_value=None,
                    new_value=modified[key]
                ))
            elif key not in modified:
                # Field was removed
                changes.append(DiffChange(
                    field_path=current_path,
                    change_type="removed",
                    old_value=original[key],
                    new_value=None
                ))
            else:
                # Compare field values
                field_changes = self._compare_values(
                    original[key],
                    modified[key],
                    current_path
                )
                changes.extend(field_changes)

        return changes

    def _compare_values(
        self,
        original: Any,
        modified: Any,
        path: str
    ) -> List[DiffChange]:
        """Compare two values and return changes."""
        changes = []

        if isinstance(original, dict) and isinstance(modified, dict):
            # Both are dictionaries, compare recursively
            return self._compare_dicts(original, modified, path)

        elif isinstance(original, list) and isinstance(modified, list):
            # Both are lists, compare items
            return self._compare_lists(original, modified, path)

        elif original != modified:
            # Simple value change
            change_magnitude = self._calculate_change_magnitude(original, modified)

            changes.append(DiffChange(
                field_path=path,
                change_type="modified",
                old_value=original,
                new_value=modified,
                change_magnitude=change_magnitude
            ))

        return changes

    def _compare_lists(
        self,
        original: List[Any],
        modified: List[Any],
        path: str
    ) -> List[DiffChange]:
        """Compare two lists and return changes."""
        changes = []

        # Handle simple lists (primitive values)
        if all(not isinstance(item, (dict, list)) for item in original + modified):
            added_items = set(modified) - set(original)
            removed_items = set(original) - set(modified)

            for item in added_items:
                changes.append(DiffChange(
                    field_path=path,
                    change_type="added",
                    old_value=None,
                    new_value=item
                ))

            for item in removed_items:
                changes.append(DiffChange(
                    field_path=path,
                    change_type="removed",
                    old_value=item,
                    new_value=None
                ))

        else:
            # Handle complex lists (objects)
            original_count = len(original)
            modified_count = len(modified)

            if original_count != modified_count:
                changes.append(DiffChange(
                    field_path=f"{path}.count",
                    change_type="modified",
                    old_value=original_count,
                    new_value=modified_count,
                    significance="medium"
                ))

            # Compare items if counts are the same
            if original_count == modified_count and original_count > 0:
                for i, (orig_item, mod_item) in enumerate(zip(original, modified)):
                    item_path = f"{path}[{i}]"
                    if isinstance(orig_item, dict) and isinstance(mod_item, dict):
                        changes.extend(self._compare_dicts(orig_item, mod_item, item_path))
                    elif orig_item != mod_item:
                        changes.append(DiffChange(
                            field_path=item_path,
                            change_type="modified",
                            old_value=orig_item,
                            new_value=mod_item
                        ))

        return changes

    def _calculate_change_magnitude(self, original: Any, modified: Any) -> Optional[float]:
        """Calculate the magnitude of change between two values."""
        try:
            # Handle numeric values
            if isinstance(original, (int, float)) and isinstance(modified, (int, float)):
                if original == 0:
                    return abs(modified) * 100  # Infinite percentage change
                return abs((modified - original) / original) * 100

            # Handle string values
            if isinstance(original, str) and isinstance(modified, str):
                original_words = len(original.split())
                modified_words = len(modified.split())

                if original_words == 0:
                    return modified_words * 10
                return abs((modified_words - original_words) / original_words) * 100

        except (ValueError, ZeroDivisionError):
            pass

        return None

    def _analyze_changes(self, changes: List[DiffChange]) -> List[DiffChange]:
        """Analyze and classify the significance of changes."""
        for change in changes:
            change.significance = self._determine_significance(change)

        return changes

    def _determine_significance(self, change: DiffChange) -> str:
        """Determine the significance level of a change."""
        # Check field-specific rules
        for rule_path, significance in self.significance_rules.items():
            if self._matches_path(change.field_path, rule_path):
                return significance

        # Change-based significance
        if change.change_magnitude is not None:
            if change.change_magnitude > 50:
                return "critical"
            elif change.change_magnitude > 20:
                return "high"
            elif change.change_magnitude > 5:
                return "medium"

        # Field addition/removal significance
        if change.change_type in ["added", "removed"]:
            if "total" in change.field_path.lower() or "amount" in change.field_path.lower():
                return "high"
            return "medium"

        return self.significance_rules["default"]

    def _matches_path(self, field_path: str, rule_path: str) -> bool:
        """Check if a field path matches a rule pattern."""
        if rule_path == field_path:
            return True

        # Handle wildcards
        if "*" in rule_path:
            rule_parts = rule_path.split(".")
            field_parts = field_path.split(".")

            if len(rule_parts) == len(field_parts):
                for rule_part, field_part in zip(rule_parts, field_parts):
                    if rule_part != "*" and rule_part != field_part:
                        return False
                return True

        return False

    def _create_summary(self, changes: List[DiffChange]) -> DiffSummary:
        """Create a summary of the diff changes."""
        total_changes = len(changes)
        added_fields = sum(1 for c in changes if c.change_type == "added")
        removed_fields = sum(1 for c in changes if c.change_type == "removed")
        modified_fields = sum(1 for c in changes if c.change_type == "modified")

        critical_changes = sum(1 for c in changes if c.significance == "critical")
        high_changes = sum(1 for c in changes if c.significance == "high")
        medium_changes = sum(1 for c in changes if c.significance == "medium")
        low_changes = sum(1 for c in changes if c.significance == "low")

        # Determine overall significance
        if critical_changes > 0:
            overall_significance = "critical"
        elif high_changes > 0:
            overall_significance = "high"
        elif medium_changes > 0:
            overall_significance = "medium"
        else:
            overall_significance = "low"

        return DiffSummary(
            total_changes=total_changes,
            added_fields=added_fields,
            removed_fields=removed_fields,
            modified_fields=modified_fields,
            critical_changes=critical_changes,
            high_changes=high_changes,
            medium_changes=medium_changes,
            low_changes=low_changes,
            overall_significance=overall_significance
        )

    def _serialize_change(self, change: DiffChange) -> Dict[str, Any]:
        """Serialize a DiffChange to dictionary."""
        return {
            "field_path": change.field_path,
            "change_type": change.change_type,
            "old_value": change.old_value,
            "new_value": change.new_value,
            "change_magnitude": change.change_magnitude,
            "significance": change.significance
        }

    def _serialize_summary(self, summary: DiffSummary) -> Dict[str, Any]:
        """Serialize a DiffSummary to dictionary."""
        return {
            "total_changes": summary.total_changes,
            "added_fields": summary.added_fields,
            "removed_fields": summary.removed_fields,
            "modified_fields": summary.modified_fields,
            "critical_changes": summary.critical_changes,
            "high_changes": summary.high_changes,
            "medium_changes": summary.medium_changes,
            "low_changes": summary.low_changes,
            "overall_significance": summary.overall_significance
        }

    def _store_diff(self, diff_data: Dict[str, Any]) -> None:
        """Store diff comparison in database if configured."""
        # Implementation would depend on database models for diff storage
        logger.info(f"Storing diff comparison: {diff_data['comparison_id']}")


class DiffService:
    """Service for generating and managing diff comparisons."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize the diff service."""
        self.db = db
        self.engine = DiffEngine()

    async def generate_export_diff(
        self,
        original_invoice: Dict[str, Any],
        modified_export: Dict[str, Any],
        comparison_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate diff for invoice export changes."""
        if not comparison_name:
            invoice_id = original_invoice.get("metadata", {}).get("invoice_id", "unknown")
            comparison_name = f"Export Changes - Invoice {invoice_id}"

        context = {
            "comparison_type": "export_modification",
            "invoice_id": original_invoice.get("metadata", {}).get("invoice_id"),
            "export_format": modified_export.get("metadata", {}).get("export_format")
        }

        return self.engine.generate_diff(
            original_invoice,
            modified_export,
            comparison_name,
            context
        )

    async def generate_approval_diff(
        self,
        staged_export_data: Dict[str, Any],
        approved_changes: Dict[str, Any],
        approver_id: str
    ) -> Dict[str, Any]:
        """Generate diff for approval changes."""
        comparison_name = f"Approval Changes - User {approver_id}"

        context = {
            "comparison_type": "approval_modification",
            "approver_id": approver_id,
            "staged_export_id": staged_export_data.get("metadata", {}).get("staged_export_id")
        }

        return self.engine.generate_diff(
            staged_export_data,
            approved_changes,
            comparison_name,
            context
        )

    async def generate_bulk_diff(
        self,
        original_items: List[Dict[str, Any]],
        modified_items: List[Dict[str, Any]],
        comparison_name: str
    ) -> List[Dict[str, Any]]:
        """Generate diffs for multiple items."""
        diffs = []

        # Ensure same number of items
        if len(original_items) != len(modified_items):
            raise DiffException("Cannot generate bulk diff: different number of items")

        for i, (original, modified) in enumerate(zip(original_items, modified_items)):
            item_name = f"{comparison_name} - Item {i + 1}"
            diff = self.engine.generate_diff(original, modified, item_name)
            diffs.append(diff)

        return diffs

    def get_diff_summary(self, diff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of diff data."""
        summary = diff_data.get("summary", {})
        changes = diff_data.get("changes", [])

        # Additional summary calculations
        fields_affected = set(change["field_path"] for change in changes)

        # Group changes by type
        changes_by_type = {}
        for change in changes:
            change_type = change["change_type"]
            if change_type not in changes_by_type:
                changes_by_type[change_type] = []
            changes_by_type[change_type].append(change)

        # Group changes by significance
        changes_by_significance = {}
        for change in changes:
            significance = change["significance"]
            if significance not in changes_by_significance:
                changes_by_significance[significance] = []
            changes_by_significance[significance].append(change)

        return {
            **summary,
            "unique_fields_affected": len(fields_affected),
            "changes_by_type": {k: len(v) for k, v in changes_by_type.items()},
            "changes_by_significance": {k: len(v) for k, v in changes_by_significance.items()},
            "most_critical_changes": [
                change for change in changes
                if change["significance"] == "critical"
            ][:5]
        }

    def filter_changes(
        self,
        diff_data: Dict[str, Any],
        significance_filter: Optional[List[str]] = None,
        field_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Filter diff changes based on criteria."""
        changes = diff_data.get("changes", [])

        filtered_changes = []
        for change in changes:
            # Filter by significance
            if significance_filter and change["significance"] not in significance_filter:
                continue

            # Filter by field path
            if field_filter:
                if not any(pattern in change["field_path"] for pattern in field_filter):
                    continue

            filtered_changes.append(change)

        # Update diff data with filtered changes
        filtered_diff = diff_data.copy()
        filtered_diff["changes"] = filtered_changes

        # Recalculate summary
        if filtered_changes:
            engine_changes = [DiffChange(**change) for change in filtered_changes]
            summary = self.engine._create_summary(engine_changes)
            filtered_diff["summary"] = self.engine._serialize_summary(summary)
        else:
            filtered_diff["summary"] = {
                "total_changes": 0,
                "added_fields": 0,
                "removed_fields": 0,
                "modified_fields": 0,
                "critical_changes": 0,
                "high_changes": 0,
                "medium_changes": 0,
                "low_changes": 0,
                "overall_significance": "low"
            }

        return filtered_diff

    async def get_field_change_history(
        self,
        field_path: str,
        entity_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get history of changes for a specific field."""
        # This would query the diff history from database
        # Implementation depends on diff storage model
        logger.info(f"Getting change history for field: {field_path}, entity: {entity_id}")

        # Mock implementation
        return []

    def validate_export_changes(self, diff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if export changes are acceptable."""
        summary = diff_data.get("summary", {})
        changes = diff_data.get("changes", [])

        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "blocking_changes": []
        }

        # Check for critical changes that might block export
        critical_changes = [
            change for change in changes
            if change["significance"] == "critical"
        ]

        if critical_changes:
            validation_result["warnings"].append(
                f"{len(critical_changes)} critical changes detected"
            )

        # Check for changes to key fields
        key_fields = ["invoice_no", "vendor_name", "total", "currency"]
        key_field_changes = [
            change for change in changes
            if any(field in change["field_path"] for field in key_fields)
        ]

        if key_field_changes:
            validation_result["warnings"].append(
                f"{len(key_field_changes)} changes to key business fields"
            )

        # Check for large percentage changes
        large_changes = [
            change for change in changes
            if change.get("change_magnitude", 0) > 25
        ]

        if large_changes:
            validation_result["warnings"].append(
                f"{len(large_changes)} changes with magnitude > 25%"
            )

        # Overall significance check
        if summary.get("overall_significance") == "critical":
            validation_result["warnings"].append(
                "Overall change significance is critical - manual review recommended"
            )

        return validation_result