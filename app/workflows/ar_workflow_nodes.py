"""
AR (Accounts Receivable) workflow nodes for LangGraph state machine.

This module implements AR-specific workflow nodes that extend the existing
invoice processing workflow to handle customer validation, payment terms,
collection management, and working capital optimization.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from app.core.config import settings
from app.core.exceptions import WorkflowException, ValidationException
from app.models.ar_invoice import ARInvoice, Customer, PaymentStatus, CollectionPriority
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ARWorkflowState(Dict[str, Any]):
    """
    Enhanced workflow state for AR invoice processing.

    Extends the base invoice state with AR-specific fields for
    customer management, payment terms, collection, and working capital.
    """

    def __init__(self, **kwargs):
        # Set default AR-specific values
        ar_defaults = {
            "invoice_type": "ar",  # Distinguish from AP invoices
            "customer_id": None,
            "customer_data": None,
            "payment_terms": "NET30",
            "due_date": None,
            "collection_priority": CollectionPriority.MEDIUM.value,
            "working_capital_score": 0.0,
            "early_payment_discount": None,

            # AR-specific results
            "customer_validation_result": None,
            "payment_terms_result": None,
            "collection_result": None,
            "working_capital_result": None,
            "communication_result": None,

            # AR workflow step tracking
            "ar_step": "initialized",
            "ar_processing_history": [],
        }

        # Merge with provided kwargs
        merged_kwargs = {**ar_defaults, **kwargs}
        super().__init__(**merged_kwargs)


class BaseARWorkflowNode:
    """Base class for AR workflow nodes with common functionality."""

    def __init__(self, **services):
        """Initialize node with required services."""
        self.services = services

    def _update_processing_history(
        self, state: ARWorkflowState, step: str,
        status: str, metadata: Dict[str, Any] = None
    ) -> None:
        """Update processing history for the current step."""
        history_entry = {
            "step": step,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        if "ar_processing_history" not in state:
            state["ar_processing_history"] = []

        state["ar_processing_history"].append(history_entry)

        # Also update main processing history
        if "processing_history" not in state:
            state["processing_history"] = []
        state["processing_history"].append(history_entry)

        # Update timestamp
        state["updated_at"] = datetime.utcnow().isoformat()

    def _set_step_state(
        self, state: ARWorkflowState, step: str,
        status: str, error_message: str = None
    ) -> None:
        """Set current step and status in state."""
        state["current_step"] = step
        state["status"] = status
        state["ar_step"] = step

        if error_message:
            state["error_message"] = error_message
        else:
            state["error_message"] = None


class CustomerValidationNode(BaseARWorkflowNode):
    """
    Customer validation workflow node.

    Validates customer data, checks credit limits, and ensures customer
    is in good standing for AR processing.
    """

    def __init__(self, customer_service=None):
        super().__init__(customer_service=customer_service)
        self.customer_service = customer_service

    async def execute(self, state: ARWorkflowState) -> ARWorkflowState:
        """Execute customer validation."""
        start_time = datetime.utcnow()
        logger.info(f"Validating customer for AR invoice {state['invoice_id']}")

        try:
            # Get customer data
            customer_id = state.get("customer_id")
            extraction_result = state.get("extraction_result", {})

            customer_data = None
            validation_result = {
                "valid": False,
                "customer_found": False,
                "credit_valid": False,
                "active_status": False
            }

            if customer_id:
                # Validate existing customer
                customer_data = await self._validate_existing_customer(customer_id, validation_result)
            else:
                # Try to identify and create new customer from extraction
                customer_data = await self._identify_and_create_customer(extraction_result, validation_result)

            if not validation_result["valid"]:
                # Validation failed
                self._set_step_state(state, "customer_validation_failed", "exception",
                                   validation_result.get("reason", "Customer validation failed"))
                state["requires_human_review"] = True

                self._update_processing_history(
                    state, "customer_validation", "failed",
                    {"reason": validation_result.get("reason")}
                )

                return state

            # Update state with successful validation
            state["customer_data"] = customer_data
            state["customer_validation_result"] = validation_result

            if customer_data and "id" in customer_data:
                state["customer_id"] = customer_data["id"]

            self._set_step_state(state, "customer_validated", "processing")

            # Update processing history
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self._update_processing_history(
                state, "customer_validation", "completed",
                {
                    "customer_id": state.get("customer_id"),
                    "customer_name": customer_data.get("name") if customer_data else None,
                    "processing_time_ms": processing_time
                }
            )

            logger.info(f"Customer validation completed for invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"Customer validation failed for invoice {state['invoice_id']}: {e}")

            self._set_step_state(state, "customer_validation_failed", "error", str(e))
            state["requires_human_review"] = True

            self._update_processing_history(
                state, "customer_validation", "error",
                {"error": str(e), "error_type": type(e).__name__}
            )

            return state

    async def _validate_existing_customer(self, customer_id: str, validation_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate existing customer."""
        try:
            if not self.customer_service:
                # Mock validation for testing
                return {
                    "id": customer_id,
                    "name": "Mock Customer",
                    "active": True,
                    "credit_limit": "50000.00",
                    "payment_terms_days": "30"
                }

            # Get customer from service
            customer_data = await self.customer_service.get_customer_by_id(customer_id)

            if not customer_data:
                validation_result["reason"] = f"Customer {customer_id} not found"
                return None

            validation_result["customer_found"] = True

            # Check if customer is active
            if not customer_data.get("active", True):
                validation_result["reason"] = "Customer is inactive"
                return customer_data  # Return data for human review

            validation_result["active_status"] = True

            # Validate credit limit
            credit_validation = await self._validate_customer_credit(customer_id, customer_data)
            validation_result.update(credit_validation)

            if validation_result.get("credit_valid", False):
                validation_result["valid"] = True

            return customer_data

        except Exception as e:
            logger.error(f"Failed to validate existing customer: {e}")
            validation_result["reason"] = f"Validation error: {str(e)}"
            return None

    async def _identify_and_create_customer(self, extraction_result: Dict[str, Any], validation_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Identify and create new customer from extraction data."""
        try:
            header = extraction_result.get("header", {})

            # Extract customer information
            customer_name = header.get("customer_name") or header.get("bill_to_name")
            customer_tax_id = header.get("customer_tax_id") or header.get("customer_vat")
            customer_email = header.get("customer_email")

            if not customer_name:
                validation_result["reason"] = "No customer name found in extraction"
                return None

            if not self.customer_service:
                # Mock customer creation for testing
                mock_customer = {
                    "id": str(uuid.uuid4()),
                    "name": customer_name,
                    "tax_id": customer_tax_id,
                    "email": customer_email,
                    "active": True,
                    "credit_limit": "10000.00",
                    "payment_terms_days": "30"
                }
                validation_result.update({
                    "customer_found": True,
                    "active_status": True,
                    "credit_valid": True,
                    "valid": True,
                    "new_customer_created": True
                })
                return mock_customer

            # Check if customer already exists by tax ID or email
            existing_customer = None
            if customer_tax_id:
                existing_customer = await self.customer_service.get_customer_by_tax_id(customer_tax_id)
            elif customer_email:
                existing_customer = await self.customer_service.get_customer_by_email(customer_email)

            if existing_customer:
                validation_result["customer_found"] = True
                validation_result["matched_by"] = "tax_id" if customer_tax_id else "email"

                # Validate existing customer
                return await self._validate_existing_customer(existing_customer["id"], validation_result)

            # Create new customer
            new_customer_data = {
                "name": customer_name,
                "tax_id": customer_tax_id,
                "email": customer_email,
                "credit_limit": Decimal("10000.00"),  # Default credit limit
                "payment_terms_days": "30",
                "active": True,
                "currency": "USD"
            }

            new_customer = await self.customer_service.create_customer(new_customer_data)

            if new_customer:
                validation_result.update({
                    "customer_found": True,
                    "active_status": True,
                    "credit_valid": True,
                    "valid": True,
                    "new_customer_created": True
                })
                return new_customer

            validation_result["reason"] = "Failed to create new customer"
            return None

        except Exception as e:
            logger.error(f"Failed to identify/create customer: {e}")
            validation_result["reason"] = f"Customer creation error: {str(e)}"
            return None

    async def _validate_customer_credit(self, customer_id: str, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate customer credit availability."""
        try:
            if not self.customer_service:
                # Mock credit validation for testing
                return {
                    "credit_valid": True,
                    "available_credit": "30000.00",
                    "used_credit": "20000.00",
                    "credit_limit": customer_data.get("credit_limit", "50000.00")
                }

            credit_validation = await self.customer_service.validate_customer_credit(customer_id)
            return credit_validation

        except Exception as e:
            logger.error(f"Failed to validate customer credit: {e}")
            return {
                "credit_valid": False,
                "reason": f"Credit validation error: {str(e)}"
            }


class PaymentTermsNode(BaseARWorkflowNode):
    """
    Payment terms processing workflow node.

    Processes payment terms, calculates due dates, and handles
    early payment discount calculations.
    """

    def __init__(self, payment_service=None):
        super().__init__(payment_service=payment_service)
        self.payment_service = payment_service

    async def execute(self, state: ARWorkflowState) -> ARWorkflowState:
        """Execute payment terms processing."""
        start_time = datetime.utcnow()
        logger.info(f"Processing payment terms for AR invoice {state['invoice_id']}")

        try:
            extraction_result = state.get("extraction_result", {})
            header = extraction_result.get("header", {})

            # Get payment terms from extraction or use default
            payment_terms = state.get("payment_terms") or header.get("payment_terms") or "NET30"

            # Get invoice date
            invoice_date_str = header.get("invoice_date") or state.get("created_at")
            invoice_date = datetime.fromisoformat(invoice_date_str.replace('Z', '+00:00')) if invoice_date_str else datetime.utcnow()

            # Process payment terms
            terms_result = await self._process_payment_terms(payment_terms, invoice_date, header)

            if not terms_result.get("valid", False):
                # Payment terms processing failed
                self._set_step_state(state, "payment_terms_failed", "exception",
                                   terms_result.get("reason", "Invalid payment terms"))
                state["requires_human_review"] = True

                self._update_processing_history(
                    state, "payment_terms", "failed",
                    {"reason": terms_result.get("reason"), "terms": payment_terms}
                )

                return state

            # Update state with payment terms results
            state["payment_terms"] = payment_terms
            state["payment_terms_result"] = terms_result
            state["due_date"] = terms_result.get("due_date")

            # Handle early payment discount
            if terms_result.get("discount_percent"):
                state["early_payment_discount"] = terms_result["discount_percent"]

            self._set_step_state(state, "payment_terms_processed", "processing")

            # Update processing history
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self._update_processing_history(
                state, "payment_terms", "completed",
                {
                    "payment_terms": payment_terms,
                    "due_date": terms_result.get("due_date"),
                    "discount_available": terms_result.get("discount_percent") is not None,
                    "processing_time_ms": processing_time
                }
            )

            logger.info(f"Payment terms processing completed for invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"Payment terms processing failed for invoice {state['invoice_id']}: {e}")

            self._set_step_state(state, "payment_terms_failed", "error", str(e))
            state["requires_human_review"] = True

            self._update_processing_history(
                state, "payment_terms", "error",
                {"error": str(e), "error_type": type(e).__name__}
            )

            return state

    async def _process_payment_terms(self, payment_terms: str, invoice_date: datetime, header: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate payment terms."""
        try:
            if not self.payment_service:
                # Mock payment terms processing for testing
                return self._mock_payment_terms_processing(payment_terms, invoice_date)

            # Use payment service to process terms
            terms_result = await self.payment_service.process_payment_terms(
                payment_terms, invoice_date, header
            )

            return terms_result

        except Exception as e:
            logger.error(f"Failed to process payment terms: {e}")
            return {
                "valid": False,
                "reason": f"Payment terms processing error: {str(e)}"
            }

    def _mock_payment_terms_processing(self, payment_terms: str, invoice_date: datetime) -> Dict[str, Any]:
        """Mock payment terms processing for testing."""
        payment_terms_upper = payment_terms.upper().strip()

        # Standard NET terms
        if payment_terms_upper.startswith("NET"):
            try:
                days = int(payment_terms_upper[3:])
                due_date = invoice_date + timedelta(days=days)

                return {
                    "valid": True,
                    "terms_type": "standard",
                    "days": days,
                    "due_date": due_date.isoformat(),
                    "description": f"Net {days} days"
                }
            except ValueError:
                pass

        # Early payment discount terms (e.g., "2% 10 NET 30")
        if "%" in payment_terms_upper and "NET" in payment_terms_upper:
            try:
                parts = payment_terms_upper.split()
                discount_percent = float(parts[0].replace("%", ""))
                discount_days = int(parts[1])
                net_days = int(parts[3])

                due_date = invoice_date + timedelta(days=net_days)
                discount_deadline = invoice_date + timedelta(days=discount_days)

                return {
                    "valid": True,
                    "terms_type": "discount",
                    "discount_percent": discount_percent,
                    "discount_days": discount_days,
                    "net_days": net_days,
                    "due_date": due_date.isoformat(),
                    "discount_deadline": discount_deadline.isoformat(),
                    "description": f"{discount_percent}% {discount_days} NET {net_days}"
                }
            except (ValueError, IndexError):
                pass

        # Custom terms - default to 30 days
        due_date = invoice_date + timedelta(days=30)
        return {
            "valid": True,
            "terms_type": "custom",
            "days": 30,
            "due_date": due_date.isoformat(),
            "description": payment_terms,
            "note": "Processed as custom terms"
        }


class CollectionNode(BaseARWorkflowNode):
    """
    Collection management workflow node.

    Calculates collection priority, generates collection schedules,
    and manages collection workflows.
    """

    def __init__(self, collection_service=None):
        super().__init__(collection_service=collection_service)
        self.collection_service = collection_service

    async def execute(self, state: ARWorkflowState) -> ARWorkflowState:
        """Execute collection processing."""
        start_time = datetime.utcnow()
        logger.info(f"Processing collection management for AR invoice {state['invoice_id']}")

        try:
            extraction_result = state.get("extraction_result", {})
            customer_data = state.get("customer_data", {})
            header = extraction_result.get("header", {})

            # Calculate collection priority
            collection_result = await self._calculate_collection_priority(
                header, customer_data, state
            )

            # Generate collection schedule if needed
            if collection_result.get("priority") in [CollectionPriority.HIGH.value, CollectionPriority.URGENT.value]:
                schedule = await self._generate_collection_schedule(state, collection_result)
                collection_result["schedule"] = schedule

            # Update state with collection results
            state["collection_result"] = collection_result
            state["collection_priority"] = collection_result.get("priority", CollectionPriority.MEDIUM.value)

            self._set_step_state(state, "collection_processed", "processing")

            # Update processing history
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self._update_processing_history(
                state, "collection", "completed",
                {
                    "collection_priority": collection_result.get("priority"),
                    "risk_score": collection_result.get("risk_score"),
                    "schedule_created": "schedule" in collection_result,
                    "processing_time_ms": processing_time
                }
            )

            logger.info(f"Collection processing completed for invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"Collection processing failed for invoice {state['invoice_id']}: {e}")

            self._set_step_state(state, "collection_failed", "error", str(e))

            self._update_processing_history(
                state, "collection", "error",
                {"error": str(e), "error_type": type(e).__name__}
            )

            return state

    async def _calculate_collection_priority(self, header: Dict[str, Any], customer_data: Dict[str, Any], state: ARWorkflowState) -> Dict[str, Any]:
        """Calculate collection priority based on various factors."""
        try:
            if not self.collection_service:
                # Mock collection priority calculation for testing
                return self._mock_collection_priority_calculation(header, customer_data)

            # Use collection service to calculate priority
            priority_result = await self.collection_service.calculate_collection_priority(
                header, customer_data, state
            )

            return priority_result

        except Exception as e:
            logger.error(f"Failed to calculate collection priority: {e}")
            return {
                "priority": CollectionPriority.MEDIUM.value,
                "risk_score": 0.5,
                "factors": ["default_priority"],
                "error": str(e)
            }

    def _mock_collection_priority_calculation(self, header: Dict[str, Any], customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock collection priority calculation for testing."""
        total_amount = Decimal(str(header.get("total_amount", 0)))

        # Base factors
        factors = []
        risk_score = 0.3  # Base risk score

        # Amount-based risk
        if total_amount > 50000:
            risk_score += 0.2
            factors.append("high_amount")
        elif total_amount < 1000:
            risk_score -= 0.1
            factors.append("low_amount")

        # Customer history-based risk
        payment_history_score = customer_data.get("payment_history_score", 0.8)
        if payment_history_score < 0.5:
            risk_score += 0.3
            factors.append("poor_payment_history")
        elif payment_history_score > 0.9:
            risk_score -= 0.2
            factors.append("excellent_payment_history")

        # New customer risk
        if customer_data.get("new_customer", False):
            risk_score += 0.2
            factors.append("new_customer")

        # Overdue history
        overdue_invoices = customer_data.get("overdue_invoices", 0)
        if overdue_invoices > 0:
            risk_score += min(0.4, overdue_invoices * 0.1)
            factors.append("overdue_history")

        # Determine priority based on risk score
        if risk_score >= 0.8:
            priority = CollectionPriority.URGENT.value
        elif risk_score >= 0.6:
            priority = CollectionPriority.HIGH.value
        elif risk_score >= 0.4:
            priority = CollectionPriority.MEDIUM.value
        else:
            priority = CollectionPriority.LOW.value

        return {
            "priority": priority,
            "risk_score": round(min(risk_score, 1.0), 2),
            "factors": factors,
            "amount": float(total_amount),
            "customer_score": payment_history_score
        }

    async def _generate_collection_schedule(self, state: ARWorkflowState, collection_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate collection schedule for high-priority invoices."""
        try:
            if not self.collection_service:
                # Mock collection schedule generation for testing
                return self._mock_collection_schedule_generation(state, collection_result)

            # Use collection service to generate schedule
            schedule = await self.collection_service.generate_collection_schedule(state, collection_result)

            return schedule

        except Exception as e:
            logger.error(f"Failed to generate collection schedule: {e}")
            return {
                "schedule_created": False,
                "error": str(e)
            }

    def _mock_collection_schedule_generation(self, state: ARWorkflowState, collection_result: Dict[str, Any]) -> Dict[str, Any]:
        """Mock collection schedule generation for testing."""
        priority = collection_result.get("priority")
        due_date = datetime.fromisoformat(state.get("due_date").replace('Z', '+00:00')) if state.get("due_date") else datetime.utcnow() + timedelta(days=30)

        # Calculate contact dates based on priority
        if priority == CollectionPriority.URGENT.value:
            # Immediate contact
            next_contact = datetime.utcnow() + timedelta(days=1)
            contact_method = "phone"
        elif priority == CollectionPriority.HIGH.value:
            # Contact within 3 days
            next_contact = datetime.utcnow() + timedelta(days=3)
            contact_method = "email"
        else:
            # Standard contact
            next_contact = due_date - timedelta(days=7)
            contact_method = "email"

        return {
            "schedule_created": True,
            "next_contact_date": next_contact.isoformat(),
            "contact_method": contact_method,
            "template": f"{priority}_reminder",
            "escalation_dates": [
                (next_contact + timedelta(days=7)).isoformat(),
                (next_contact + timedelta(days=14)).isoformat()
            ]
        }


class WorkingCapitalNode(BaseARWorkflowNode):
    """
    Working capital optimization workflow node.

    Calculates working capital optimization scores, identifies
    early payment discount opportunities, and generates recommendations.
    """

    def __init__(self, working_capital_service=None):
        super().__init__(working_capital_service=working_capital_service)
        self.working_capital_service = working_capital_service

    async def execute(self, state: ARWorkflowState) -> ARWorkflowState:
        """Execute working capital optimization."""
        start_time = datetime.utcnow()
        logger.info(f"Processing working capital optimization for AR invoice {state['invoice_id']}")

        try:
            extraction_result = state.get("extraction_result", {})
            customer_data = state.get("customer_data", {})
            payment_terms_result = state.get("payment_terms_result", {})

            # Calculate working capital optimization
            wc_result = await self._calculate_working_capital_optimization(
                extraction_result, customer_data, payment_terms_result, state
            )

            # Update state with working capital results
            state["working_capital_result"] = wc_result
            state["working_capital_score"] = wc_result.get("overall_score", 0.0)

            self._set_step_state(state, "working_capital_optimized", "processing")

            # Update processing history
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self._update_processing_history(
                state, "working_capital", "completed",
                {
                    "optimization_score": wc_result.get("overall_score"),
                    "discount_opportunities": len(wc_result.get("discount_opportunities", [])),
                    "recommendations": len(wc_result.get("recommendations", [])),
                    "processing_time_ms": processing_time
                }
            )

            logger.info(f"Working capital optimization completed for invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"Working capital optimization failed for invoice {state['invoice_id']}: {e}")

            self._set_step_state(state, "working_capital_failed", "error", str(e))

            self._update_processing_history(
                state, "working_capital", "error",
                {"error": str(e), "error_type": type(e).__name__}
            )

            return state

    async def _calculate_working_capital_optimization(
        self, extraction_result: Dict[str, Any], customer_data: Dict[str, Any],
        payment_terms_result: Dict[str, Any], state: ARWorkflowState
    ) -> Dict[str, Any]:
        """Calculate working capital optimization score and recommendations."""
        try:
            if not self.working_capital_service:
                # Mock working capital optimization for testing
                return self._mock_working_capital_optimization(
                    extraction_result, customer_data, payment_terms_result, state
                )

            # Use working capital service for optimization
            optimization_result = await self.working_capital_service.calculate_optimization(
                extraction_result, customer_data, payment_terms_result, state
            )

            return optimization_result

        except Exception as e:
            logger.error(f"Failed to calculate working capital optimization: {e}")
            return {
                "overall_score": 50.0,
                "collection_efficiency_score": 50.0,
                "discount_optimization_score": 50.0,
                "recommendations": ["Error in optimization calculation"],
                "error": str(e)
            }

    def _mock_working_capital_optimization(
        self, extraction_result: Dict[str, Any], customer_data: Dict[str, Any],
        payment_terms_result: Dict[str, Any], state: ARWorkflowState
    ) -> Dict[str, Any]:
        """Mock working capital optimization for testing."""
        header = extraction_result.get("header", {})
        total_amount = Decimal(str(header.get("total_amount", 0)))

        # Collection efficiency score (70% weight)
        collection_score = self._calculate_collection_efficiency_score(customer_data, payment_terms_result)

        # Discount optimization score (30% weight)
        discount_score = self._calculate_discount_optimization_score(payment_terms_result, total_amount)

        # Overall score
        overall_score = (collection_score * 0.7) + (discount_score * 0.3)

        # Generate recommendations
        recommendations = self._generate_recommendations(collection_score, discount_score, customer_data)

        # Find discount opportunities
        discount_opportunities = []
        if payment_terms_result.get("discount_percent"):
            discount_amount = total_amount * (Decimal(str(payment_terms_result["discount_percent"])) / Decimal("100"))
            discount_opportunities.append({
                "discount_percent": payment_terms_result["discount_percent"],
                "discount_amount": float(discount_amount),
                "deadline": payment_terms_result.get("discount_deadline"),
                "days_until_deadline": self._calculate_days_until_deadline(
                    payment_terms_result.get("discount_deadline")
                )
            })

        return {
            "overall_score": round(overall_score, 1),
            "collection_efficiency_score": round(collection_score, 1),
            "discount_optimization_score": round(discount_score, 1),
            "recommendations": recommendations,
            "discount_opportunities": discount_opportunities,
            "cash_flow_impact": {
                "projected_days": payment_terms_result.get("days", 30),
                "potential_savings": sum(opp["discount_amount"] for opp in discount_opportunities)
            }
        }

    def _calculate_collection_efficiency_score(self, customer_data: Dict[str, Any], payment_terms_result: Dict[str, Any]) -> float:
        """Calculate collection efficiency score."""
        base_score = 80.0  # Base score

        # Customer payment history
        payment_history_score = customer_data.get("payment_history_score", 0.8)
        base_score += (payment_history_score - 0.5) * 40  # Adjust by 40 points

        # Payment terms length
        payment_days = payment_terms_result.get("days", 30)
        if payment_days > 60:
            base_score -= 20  # Penalty for very long terms
        elif payment_days < 15:
            base_score += 10  # Bonus for short terms

        return max(0, min(100, base_score))

    def _calculate_discount_optimization_score(self, payment_terms_result: Dict[str, Any], total_amount: Decimal) -> float:
        """Calculate discount optimization score."""
        if not payment_terms_result.get("discount_percent"):
            return 60.0  # Neutral score for no discounts

        discount_percent = payment_terms_result.get("discount_percent", 0)
        discount_days = payment_terms_result.get("discount_days", 10)

        # Score based on discount generosity and timeline
        if discount_percent >= 2.0 and discount_days >= 10:
            return 90.0  # Excellent terms
        elif discount_percent >= 1.5 and discount_days >= 7:
            return 80.0  # Good terms
        elif discount_percent >= 1.0 and discount_days >= 5:
            return 70.0  # Fair terms
        else:
            return 50.0  # Poor terms

    def _generate_recommendations(self, collection_score: float, discount_score: float, customer_data: Dict[str, Any]) -> List[str]:
        """Generate working capital optimization recommendations."""
        recommendations = []

        if collection_score < 70:
            recommendations.append("Implement proactive collection process")
            if customer_data.get("payment_history_score", 1.0) < 0.6:
                recommendations.append("Review customer payment terms and credit limits")

        if discount_score > 80:
            recommendations.append("Utilize early payment discounts for improved cash flow")
        elif discount_score < 60:
            recommendations.append("Consider offering early payment discounts to customers")

        if collection_score > 85 and discount_score > 85:
            recommendations.append("Current working capital optimization is excellent")

        return recommendations

    def _calculate_days_until_deadline(self, deadline_str: str) -> int:
        """Calculate days until discount deadline."""
        if not deadline_str:
            return 0

        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            days_until = (deadline - datetime.utcnow()).days
            return max(0, days_until)
        except:
            return 0


class CustomerCommunicationNode(BaseARWorkflowNode):
    """
    Customer communication workflow node.

    Handles communication to customers about invoices, including
    standard notifications, discount offers, and collection notices.
    """

    def __init__(self, communication_service=None):
        super().__init__(communication_service=communication_service)
        self.communication_service = communication_service

    async def execute(self, state: ARWorkflowState) -> ARWorkflowState:
        """Execute customer communication."""
        start_time = datetime.utcnow()
        logger.info(f"Processing customer communication for AR invoice {state['invoice_id']}")

        try:
            customer_data = state.get("customer_data", {})
            extraction_result = state.get("extraction_result", {})
            payment_terms_result = state.get("payment_terms_result", {})
            collection_result = state.get("collection_result", {})
            working_capital_result = state.get("working_capital_result", {})

            # Determine communication type and send
            communication_result = await self._send_customer_communication(
                customer_data, extraction_result, payment_terms_result,
                collection_result, working_capital_result, state
            )

            # Update state with communication results
            state["communication_result"] = communication_result

            self._set_step_state(state, "customer_communicated", "processing")

            # Update processing history
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self._update_processing_history(
                state, "customer_communication", "completed",
                {
                    "communication_type": communication_result.get("type"),
                    "communication_sent": communication_result.get("sent", False),
                    "channels": communication_result.get("channels", []),
                    "processing_time_ms": processing_time
                }
            )

            logger.info(f"Customer communication completed for invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"Customer communication failed for invoice {state['invoice_id']}: {e}")

            self._set_step_state(state, "customer_communication_failed", "error", str(e))

            self._update_processing_history(
                state, "customer_communication", "error",
                {"error": str(e), "error_type": type(e).__name__}
            )

            return state

    async def _send_customer_communication(
        self, customer_data: Dict[str, Any], extraction_result: Dict[str, Any],
        payment_terms_result: Dict[str, Any], collection_result: Dict[str, Any],
        working_capital_result: Dict[str, Any], state: ARWorkflowState
    ) -> Dict[str, Any]:
        """Send appropriate customer communication based on context."""
        try:
            if not self.communication_service:
                # Mock communication for testing
                return self._mock_customer_communication(
                    customer_data, extraction_result, payment_terms_result,
                    collection_result, working_capital_result, state
                )

            # Determine communication type
            communication_type = self._determine_communication_type(
                payment_terms_result, collection_result, working_capital_result
            )

            # Send communication via service
            if communication_type == "invoice_notification":
                result = await self.communication_service.send_invoice_notification(
                    customer_data, extraction_result, state
                )
            elif communication_type == "discount_offer":
                result = await self.communication_service.send_discount_offer(
                    customer_data, extraction_result, payment_terms_result, state
                )
            elif communication_type == "collection_reminder":
                result = await self.communication_service.send_collection_notice(
                    customer_data, extraction_result, collection_result, state
                )
            elif communication_type == "urgent_collection":
                result = await self.communication_service.send_multi_channel_notice(
                    customer_data, extraction_result, collection_result, state
                )
            else:
                result = await self.communication_service.send_invoice_notification(
                    customer_data, extraction_result, state
                )

            result["type"] = communication_type
            return result

        except Exception as e:
            logger.error(f"Failed to send customer communication: {e}")
            return {
                "sent": False,
                "type": "error",
                "error": str(e),
                "retry_recommended": True
            }

    def _determine_communication_type(
        self, payment_terms_result: Dict[str, Any], collection_result: Dict[str, Any],
        working_capital_result: Dict[str, Any]
    ) -> str:
        """Determine the appropriate type of communication."""
        # Urgent collection takes priority
        if collection_result.get("priority") == CollectionPriority.URGENT.value:
            return "urgent_collection"

        # High priority collection
        if collection_result.get("priority") == CollectionPriority.HIGH.value:
            return "collection_reminder"

        # Early payment discount available
        if payment_terms_result.get("discount_percent"):
            # Check if discount deadline is approaching
            days_until_deadline = self._calculate_days_until_deadline(
                payment_terms_result.get("discount_deadline")
            )
            if days_until_deadline <= 7:  # Within 7 days of deadline
                return "discount_offer"

        # Standard invoice notification
        return "invoice_notification"

    def _mock_customer_communication(
        self, customer_data: Dict[str, Any], extraction_result: Dict[str, Any],
        payment_terms_result: Dict[str, Any], collection_result: Dict[str, Any],
        working_capital_result: Dict[str, Any], state: ARWorkflowState
    ) -> Dict[str, Any]:
        """Mock customer communication for testing."""
        communication_type = self._determine_communication_type(
            payment_terms_result, collection_result, working_capital_result
        )

        # Mock successful communication
        result = {
            "sent": True,
            "communication_id": str(uuid.uuid4()),
            "type": communication_type,
            "timestamp": datetime.utcnow().isoformat(),
            "recipient": customer_data.get("email"),
            "channels": ["email"]
        }

        # Add type-specific details
        if communication_type == "discount_offer":
            result.update({
                "discount_percent": payment_terms_result.get("discount_percent"),
                "discount_amount": extraction_result.get("header", {}).get("total_amount", 0) *
                                 (payment_terms_result.get("discount_percent", 0) / 100),
                "deadline": payment_terms_result.get("discount_deadline")
            })
        elif communication_type in ["collection_reminder", "urgent_collection"]:
            result.update({
                "priority": collection_result.get("priority"),
                "due_date": state.get("due_date"),
                "amount": extraction_result.get("header", {}).get("total_amount", 0)
            })

            if communication_type == "urgent_collection":
                result["channels"] = ["email", "sms", "portal"]

        return result