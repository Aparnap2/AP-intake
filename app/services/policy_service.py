"""
Policy evaluation engine for invoice processing with configurable rules.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.select import select, and_, or_

from app.models.rbac import (
    PolicyGate,
    PolicyEvaluation,
    PolicyAuditLog,
    PolicyGateType,
    PolicyAction,
    DEFAULT_POLICY_GATES
)
from app.models.invoice import Invoice
from app.models.vendor import Vendor
from app.models.validation import ValidationException
from app.models.approval_models import ApprovalRequest, ApprovalStatus

logger = logging.getLogger(__name__)


class PolicyEvaluationResult:
    """Result of a policy gate evaluation."""

    def __init__(
        self,
        gate: PolicyGate,
        triggered: bool,
        result: str,
        details: Dict[str, Any],
        evaluation_time: datetime,
        duration_ms: int
    ):
        self.gate = gate
        self.triggered = triggered
        self.result = result
        self.details = details
        self.evaluation_time = evaluation_time
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "gate_id": str(self.gate.id),
            "gate_name": self.gate.name,
            "gate_type": self.gate.gate_type,
            "triggered": self.triggered,
            "result": self.result,
            "action": self.gate.action,
            "required_role": self.gate.required_role,
            "approval_level": self.gate.approval_level,
            "details": self.details,
            "evaluation_time": self.evaluation_time.isoformat(),
            "duration_ms": self.duration_ms
        }


class PolicyEvaluationEngine:
    """Engine for evaluating policy gates against invoice data."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._operators = {
            "==": self._op_equals,
            "!=": self._op_not_equals,
            ">": self._op_greater_than,
            ">=": self._op_greater_equal,
            "<": self._op_less_than,
            "<=": self._op_less_equal,
            "in": self._op_in,
            "not_in": self._op_not_in,
            "contains": self._op_contains,
            "not_contains": self._op_not_contains,
            "regex": self._op_regex,
            "duplicate_check": self._op_duplicate_check,
            "variance_check": self._op_variance_check,
        }

    async def evaluate_invoice(
        self,
        invoice: Invoice,
        vendor: Optional[Vendor] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[PolicyEvaluationResult]:
        """
        Evaluate all applicable policy gates for an invoice.

        Args:
            invoice: The invoice to evaluate
            vendor: The vendor associated with the invoice
            context: Additional context for evaluation

        Returns:
            List of policy evaluation results
        """
        start_time = datetime.utcnow()
        results = []

        try:
            # Get all active policy gates ordered by priority
            gates = await self._get_active_policy_gates()

            # Prepare evaluation context
            eval_context = self._prepare_evaluation_context(invoice, vendor, context)

            # Evaluate each gate
            for gate in gates:
                if await self._should_evaluate_gate(gate, eval_context):
                    result = await self._evaluate_gate(gate, eval_context, invoice)
                    results.append(result)

                    # Log the evaluation
                    await self._log_policy_evaluation(gate, result, invoice)

            # Log overall evaluation
            await self._log_overall_evaluation(invoice, results, start_time)

        except Exception as e:
            logger.error(f"Error evaluating policies for invoice {invoice.id}: {e}")
            await self._log_evaluation_error(invoice, str(e), start_time)

        return results

    async def _get_active_policy_gates(self) -> List[PolicyGate]:
        """Get all active policy gates ordered by priority."""
        stmt = (
            select(PolicyGate)
            .where(PolicyGate.is_active == True)
            .order_by(PolicyGate.priority.desc(), PolicyGate.name)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    def _prepare_evaluation_context(
        self,
        invoice: Invoice,
        vendor: Optional[Vendor],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare the evaluation context with all available data."""
        eval_context = {
            "invoice": {
                "id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "total_amount": float(invoice.total_amount) if invoice.total_amount else 0.0,
                "currency": invoice.currency,
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "line_items": [
                    {
                        "description": item.description,
                        "amount": float(item.amount) if item.amount else 0.0,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price) if item.unit_price else 0.0
                    }
                    for item in invoice.line_items or []
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        if vendor:
            eval_context["vendor"] = {
                "id": str(vendor.id),
                "name": vendor.name,
                "vendor_number": vendor.vendor_number,
                "is_new": vendor.created_at >= datetime.utcnow() - timedelta(days=30)
            }

        if context:
            eval_context.update(context)

        return eval_context

    async def _should_evaluate_gate(
        self,
        gate: PolicyGate,
        context: Dict[str, Any]
    ) -> bool:
        """Check if a gate should be evaluated based on context."""
        # For now, all gates are evaluated
        # In the future, we might add conditions like "only for specific vendors"
        return True

    async def _evaluate_gate(
        self,
        gate: PolicyGate,
        context: Dict[str, Any],
        invoice: Invoice
    ) -> PolicyEvaluationResult:
        """Evaluate a single policy gate."""
        start_time = datetime.utcnow()

        try:
            triggered, details = await self._evaluate_conditions(gate.conditions, context)

            if triggered:
                result = self._determine_result(gate.action, details)
            else:
                result = "passed"
                details["reason"] = "Conditions not met"

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Save evaluation to database
            await self._save_policy_evaluation(
                gate_id=gate.id,
                invoice_id=invoice.id,
                triggered=triggered,
                result=result,
                details=details,
                evaluation_time=start_time,
                duration_ms=duration_ms,
                context_data=context
            )

            return PolicyEvaluationResult(
                gate=gate,
                triggered=triggered,
                result=result,
                details=details,
                evaluation_time=start_time,
                duration_ms=duration_ms
            )

        except Exception as e:
            logger.error(f"Error evaluating gate {gate.name}: {e}")
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            error_details = {
                "error": str(e),
                "gate_name": gate.name,
                "gate_type": gate.gate_type
            }

            await self._save_policy_evaluation(
                gate_id=gate.id,
                invoice_id=invoice.id,
                triggered=True,
                result="error",
                details=error_details,
                evaluation_time=start_time,
                duration_ms=duration_ms,
                context_data=context
            )

            return PolicyEvaluationResult(
                gate=gate,
                triggered=True,
                result="error",
                details=error_details,
                evaluation_time=start_time,
                duration_ms=duration_ms
            )

    async def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate policy conditions against context."""
        details = {"conditions_evaluated": []}

        for condition_name, condition_config in conditions.items():
            if condition_name == "field" and isinstance(condition_config, dict):
                # Single field condition
                triggered, condition_details = await self._evaluate_field_condition(
                    condition_config, context
                )
                details["conditions_evaluated"].append(condition_details)

                if triggered:
                    return True, details

            elif condition_name == "all" and isinstance(condition_config, list):
                # All conditions must be true (AND)
                all_triggered = True
                for condition in condition_config:
                    triggered, condition_details = await self._evaluate_field_condition(
                        condition, context
                    )
                    details["conditions_evaluated"].append(condition_details)
                    if not triggered:
                        all_triggered = False
                        break

                if all_triggered:
                    return True, details

            elif condition_name == "any" and isinstance(condition_config, list):
                # Any condition must be true (OR)
                for condition in condition_config:
                    triggered, condition_details = await self._evaluate_field_condition(
                        condition, context
                    )
                    details["conditions_evaluated"].append(condition_details)
                    if triggered:
                        return True, details

        return False, details

    async def _evaluate_field_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate a single field condition."""
        field_path = condition.get("field", "")
        operator = condition.get("operator", "==")
        expected_value = condition.get("value")

        # Get the actual value from context
        actual_value = self._get_field_value(field_path, context)

        # Evaluate the condition
        if operator in self._operators:
            triggered = self._operators[operator](actual_value, expected_value, condition, context)
        else:
            triggered = False

        details = {
            "field": field_path,
            "operator": operator,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "triggered": triggered
        }

        return triggered, details

    def _get_field_value(self, field_path: str, context: Dict[str, Any]) -> Any:
        """Get a field value from the context using dot notation."""
        if not field_path:
            return None

        parts = field_path.split(".")
        current = context

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None

        return current

    def _determine_result(self, action: str, details: Dict[str, Any]) -> str:
        """Determine the result based on the action and evaluation details."""
        if action == PolicyAction.BLOCK:
            return "blocked"
        elif action == PolicyAction.REQUIRE_APPROVAL:
            return "requires_approval"
        elif action == PolicyAction.ESCALATE:
            return "escalated"
        elif action == PolicyAction.FLAG:
            return "flagged"
        elif action == PolicyAction.ALLOW:
            return "allowed"
        else:
            return "flagged"  # Default to flagged for unknown actions

    # Operator implementations
    def _op_equals(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        return actual == expected

    def _op_not_equals(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        return actual != expected

    def _op_greater_than(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False

    def _op_greater_equal(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False

    def _op_less_than(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False

    def _op_less_equal(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False

    def _op_in(self, actual: Any, expected: List, condition: Dict, context: Dict) -> bool:
        return actual in expected

    def _op_not_in(self, actual: Any, expected: List, condition: Dict, context: Dict) -> bool:
        return actual not in expected

    def _op_contains(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        if isinstance(actual, (str, list)):
            return expected in actual
        return False

    def _op_not_contains(self, actual: Any, expected: Any, condition: Dict, context: Dict) -> bool:
        return not self._op_contains(actual, expected, condition, context)

    def _op_regex(self, actual: Any, expected: str, condition: Dict, context: Dict) -> bool:
        import re
        try:
            return bool(re.match(expected, str(actual)))
        except re.error:
            return False

    async def _op_duplicate_check(
        self,
        actual: Any,
        expected: Any,
        condition: Dict,
        context: Dict
    ) -> bool:
        """Check for duplicate invoices."""
        invoice_data = context.get("invoice", {})
        vendor_data = context.get("vendor", {})

        invoice_number = invoice_data.get("invoice_number")
        if not invoice_number:
            return False

        # Check for duplicate invoice numbers
        stmt = select(Invoice).where(
            Invoice.invoice_number == invoice_number,
            Invoice.id != invoice_data.get("id")
        )

        # Add vendor match if required
        if condition.get("vendor_match", True):
            stmt = stmt.where(Invoice.vendor_id == vendor_data.get("id"))

        # Add amount match if required
        if condition.get("amount_match", True):
            stmt = stmt.where(Invoice.total_amount == invoice_data.get("total_amount"))

        # Add date range check
        date_range_days = condition.get("date_range_days", 30)
        if date_range_days:
            cutoff_date = datetime.utcnow() - timedelta(days=date_range_days)
            stmt = stmt.where(Invoice.created_at >= cutoff_date)

        result = await self.db.execute(stmt)
        duplicates = result.scalars().all()

        return len(duplicates) > 0

    async def _op_variance_check(
        self,
        actual: Any,
        expected: Any,
        condition: Dict,
        context: Dict
    ) -> bool:
        """Check for unusual variance in invoice amounts."""
        invoice_data = context.get("invoice", {})
        vendor_data = context.get("vendor", {})

        if not vendor_data.get("id"):
            return False

        current_amount = invoice_data.get("total_amount", 0)
        history_months = condition.get("vendor_history_months", 12)
        variance_threshold = condition.get("variance_threshold", 0.5)
        min_invoices = condition.get("min_invoices", 3)

        # Get historical invoices for this vendor
        cutoff_date = datetime.utcnow() - timedelta(days=history_months * 30)
        stmt = select(Invoice).where(
            Invoice.vendor_id == vendor_data.get("id"),
            Invoice.created_at >= cutoff_date,
            Invoice.total_amount.isnot(None)
        ).order_by(Invoice.created_at.desc())

        result = await self.db.execute(stmt)
        historical_invoices = result.scalars().all()

        if len(historical_invoices) < min_invoices:
            return False  # Not enough data

        # Calculate average and variance
        amounts = [float(inv.total_amount) for inv in historical_invoices]
        avg_amount = sum(amounts) / len(amounts)

        # Calculate variance
        variance = abs(current_amount - avg_amount) / avg_amount if avg_amount > 0 else 1

        return variance > variance_threshold

    async def _save_policy_evaluation(
        self,
        gate_id: str,
        invoice_id: str,
        triggered: bool,
        result: str,
        details: Dict[str, Any],
        evaluation_time: datetime,
        duration_ms: int,
        context_data: Dict[str, Any]
    ):
        """Save policy evaluation result to database."""
        evaluation = PolicyEvaluation(
            gate_id=gate_id,
            invoice_id=invoice_id,
            triggered=triggered,
            result=result,
            evaluation_details=details,
            evaluation_time=evaluation_time,
            evaluation_duration_ms=duration_ms,
            context_data=context_data
        )
        self.db.add(evaluation)
        await self.db.commit()

    async def _log_policy_evaluation(
        self,
        gate: PolicyGate,
        result: PolicyEvaluationResult,
        invoice: Invoice
    ):
        """Log policy evaluation for audit purposes."""
        audit_log = PolicyAuditLog(
            gate_id=gate.id,
            invoice_id=invoice.id,
            event_type="policy_evaluation",
            event_data=result.to_dict(),
            decision=result.result,
            decision_reason=result.details.get("reason", "Policy evaluated")
        )
        self.db.add(audit_log)
        await self.db.commit()

    async def _log_overall_evaluation(
        self,
        invoice: Invoice,
        results: List[PolicyEvaluationResult],
        start_time: datetime
    ):
        """Log overall policy evaluation for an invoice."""
        triggered_gates = [r for r in results if r.triggered]
        blocked_gates = [r for r in results if r.result == "blocked"]

        audit_log = PolicyAuditLog(
            invoice_id=invoice.id,
            event_type="policy_evaluation_complete",
            event_data={
                "total_gates": len(results),
                "triggered_gates": len(triggered_gates),
                "blocked_gates": len(blocked_gates),
                "evaluation_duration_ms": int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                ),
                "gate_results": [r.to_dict() for r in results]
            },
            decision="blocked" if blocked_gates else "processed",
            decision_reason=f"Policy evaluation complete: {len(triggered_gates)} gates triggered"
        )
        self.db.add(audit_log)
        await self.db.commit()

    async def _log_evaluation_error(self, invoice: Invoice, error: str, start_time: datetime):
        """Log evaluation error for audit purposes."""
        audit_log = PolicyAuditLog(
            invoice_id=invoice.id,
            event_type="policy_evaluation_error",
            event_data={
                "error": error,
                "evaluation_duration_ms": int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                )
            },
            decision="error",
            decision_reason=f"Policy evaluation failed: {error}"
        )
        self.db.add(audit_log)
        await self.db.commit()

    async def initialize_default_policy_gates(self):
        """Initialize default policy gates in the database."""
        for gate_data in DEFAULT_POLICY_GATES:
            # Check if gate already exists
            stmt = select(PolicyGate).where(PolicyGate.name == gate_data["name"])
            result = await self.db.execute(stmt)
            existing_gate = result.scalar_one_or_none()

            if existing_gate:
                # Update existing gate if needed
                for key, value in gate_data.items():
                    if key != "name" and hasattr(existing_gate, key):
                        setattr(existing_gate, key, value)
            else:
                # Create new gate
                gate = PolicyGate(**gate_data)
                self.db.add(gate)

        await self.db.commit()

    async def get_policy_evaluation_summary(
        self,
        invoice_id: str
    ) -> Dict[str, Any]:
        """Get a summary of policy evaluations for an invoice."""
        stmt = (
            select(PolicyEvaluation)
            .where(PolicyEvaluation.invoice_id == invoice_id)
            .options(selectinload(PolicyEvaluation.gate))
        )
        result = await self.db.execute(stmt)
        evaluations = result.scalars().all()

        summary = {
            "invoice_id": invoice_id,
            "total_evaluations": len(evaluations),
            "triggered_gates": [],
            "blocked_gates": [],
            "requires_approval_gates": [],
            "flagged_gates": [],
            "passed_gates": []
        }

        for eval in evaluations:
            eval_dict = eval.to_dict()
            if eval.triggered:
                summary["triggered_gates"].append(eval_dict)

                if eval.result == "blocked":
                    summary["blocked_gates"].append(eval_dict)
                elif eval.result == "requires_approval":
                    summary["requires_approval_gates"].append(eval_dict)
                elif eval.result == "flagged":
                    summary["flagged_gates"].append(eval_dict)
            else:
                summary["passed_gates"].append(eval_dict)

        return summary

    async def get_policy_gate_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get statistics about policy gate performance."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stmt = select(PolicyEvaluation).where(
            PolicyEvaluation.evaluation_time >= cutoff_date
        )
        result = await self.db.execute(stmt)
        evaluations = result.scalars().all()

        stats = {
            "period_days": days,
            "total_evaluations": len(evaluations),
            "gate_statistics": {},
            "result_distribution": {
                "passed": 0,
                "blocked": 0,
                "requires_approval": 0,
                "flagged": 0,
                "error": 0
            }
        }

        for eval in evaluations:
            gate_name = eval.gate.name
            if gate_name not in stats["gate_statistics"]:
                stats["gate_statistics"][gate_name] = {
                    "total_evaluations": 0,
                    "triggered_count": 0,
                    "triggered_percentage": 0,
                    "average_duration_ms": 0,
                    "results": {}
                }

            gate_stats = stats["gate_statistics"][gate_name]
            gate_stats["total_evaluations"] += 1
            gate_stats["average_duration_ms"] = (
                (gate_stats["average_duration_ms"] * (gate_stats["total_evaluations"] - 1) + eval.evaluation_duration_ms)
                / gate_stats["total_evaluations"]
            )

            if eval.triggered:
                gate_stats["triggered_count"] += 1

            # Track result distribution
            if eval.result not in gate_stats["results"]:
                gate_stats["results"][eval.result] = 0
            gate_stats["results"][eval.result] += 1

            # Track overall result distribution
            if eval.result in stats["result_distribution"]:
                stats["result_distribution"][eval.result] += 1

        # Calculate triggered percentages
        for gate_name, gate_stats in stats["gate_statistics"].items():
            if gate_stats["total_evaluations"] > 0:
                gate_stats["triggered_percentage"] = (
                    gate_stats["triggered_count"] / gate_stats["total_evaluations"] * 100
                )

        return stats