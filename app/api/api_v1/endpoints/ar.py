"""
AR (Accounts Receivable) API endpoints.

This module provides REST API endpoints for managing AR customers and invoices,
including working capital optimization and collection management features.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.ar_invoice import Customer, ARInvoice, PaymentStatus, CollectionPriority
from app.models.user import User
from app.schemas.ar_schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    ARInvoiceCreate,
    ARInvoiceUpdate,
    ARInvoiceResponse,
    PaymentApply,
    WorkingCapitalSummary,
    CollectionRecommendation,
    CashFlowForecast,
    EarlyPaymentDiscountOpportunity,
    WorkingCapitalOptimizationScore,
    CollectionEfficiencyMetrics,
    CustomerOutstandingInvoices,
    BulkPaymentApplication,
    BulkPaymentApplicationResult,
)
from app.services.ar_service import ARService
from app.services.ar_validation_service import ARValidationService
from app.services.metrics_service import MetricsService

router = APIRouter()
ar_service = ARService()
ar_validation_service = ARValidationService()
metrics_service = MetricsService()


# Customer endpoints

@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new AR customer."""
    try:
        # Validate customer data
        validation_result = await ar_validation_service.validate_customer(db, customer_data.dict())
        if not validation_result["passed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {validation_result['issues']}"
            )

        # Create customer
        customer = await ar_service.create_customer(db, customer_data.dict())

        # Calculate derived fields
        outstanding_balance = await customer.get_outstanding_balance(db)
        available_credit = await customer.get_available_credit(db)
        invoice_count = await customer.get_invoice_count(db)

        return CustomerResponse(
            **customer.__dict__,
            outstanding_balance=outstanding_balance,
            available_credit=available_credit,
            invoice_count=invoice_count
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/customers", response_model=List[CustomerResponse])
async def get_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of AR customers."""
    try:
        from sqlalchemy import select

        query = select(Customer)
        if active_only:
            query = query.where(Customer.active == True)

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        customers = result.scalars().all()

        customer_responses = []
        for customer in customers:
            outstanding_balance = await customer.get_outstanding_balance(db)
            available_credit = await customer.get_available_credit(db)
            invoice_count = await customer.get_invoice_count(db)

            customer_responses.append(CustomerResponse(
                **customer.__dict__,
                outstanding_balance=outstanding_balance,
                available_credit=available_credit,
                invoice_count=invoice_count
            ))

        return customer_responses
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific AR customer."""
    try:
        from uuid import UUID
        from sqlalchemy import select

        result = await db.execute(
            select(Customer).where(Customer.id == UUID(customer_id))
        )
        customer = result.scalar_one_or_none()

        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        outstanding_balance = await customer.get_outstanding_balance(db)
        available_credit = await customer.get_available_credit(db)
        invoice_count = await customer.get_invoice_count(db)

        return CustomerResponse(
            **customer.__dict__,
            outstanding_balance=outstanding_balance,
            available_credit=available_credit,
            invoice_count=invoice_count
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    customer_update: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an AR customer."""
    try:
        from uuid import UUID
        from sqlalchemy import select

        result = await db.execute(
            select(Customer).where(Customer.id == UUID(customer_id))
        )
        customer = result.scalar_one_or_none()

        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        # Update fields
        update_data = customer_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        await db.commit()
        await db.refresh(customer)

        outstanding_balance = await customer.get_outstanding_balance(db)
        available_credit = await customer.get_available_credit(db)
        invoice_count = await customer.get_invoice_count(db)

        return CustomerResponse(
            **customer.__dict__,
            outstanding_balance=outstanding_balance,
            available_credit=available_credit,
            invoice_count=invoice_count
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft delete an AR customer."""
    try:
        from uuid import UUID
        from sqlalchemy import select

        result = await db.execute(
            select(Customer).where(Customer.id == UUID(customer_id))
        )
        customer = result.scalar_one_or_none()

        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        # Soft delete
        customer.active = False
        await db.commit()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# AR Invoice endpoints

@router.post("/invoices", response_model=ARInvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_ar_invoice(
    invoice_data: ARInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new AR invoice."""
    try:
        # Validate invoice data
        validation_result = await ar_validation_service.validate_ar_invoice(
            db, invoice_data.dict(), str(invoice_data.customer_id)
        )
        if not validation_result["passed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {validation_result['issues']}"
            )

        # Create invoice
        invoice = await ar_service.create_ar_invoice(db, invoice_data.dict())

        # Add derived fields
        invoice.days_overdue = invoice.days_overdue()
        invoice.is_overdue = invoice.is_overdue()
        invoice.early_payment_discount_available = invoice.is_early_payment_discount_available()
        invoice.early_payment_discount_amount = invoice.calculate_early_payment_discount()

        return ARInvoiceResponse(**invoice.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/invoices", response_model=List[ARInvoiceResponse])
async def get_ar_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    customer_id: Optional[str] = Query(None),
    status: Optional[PaymentStatus] = Query(None),
    collection_priority: Optional[CollectionPriority] = Query(None),
    overdue_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of AR invoices with filtering."""
    try:
        from uuid import UUID
        from sqlalchemy import select, and_

        query = select(ARInvoice)

        # Apply filters
        filters = []
        if customer_id:
            filters.append(ARInvoice.customer_id == UUID(customer_id))
        if status:
            filters.append(ARInvoice.status == status)
        if collection_priority:
            filters.append(ARInvoice.collection_priority == collection_priority)
        if overdue_only:
            filters.append(ARInvoice.due_date < datetime.utcnow())

        if filters:
            query = query.where(and_(*filters))

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        invoices = result.scalars().all()

        # Add derived fields
        invoice_responses = []
        for invoice in invoices:
            invoice.days_overdue = invoice.days_overdue()
            invoice.is_overdue = invoice.is_overdue()
            invoice.early_payment_discount_available = invoice.is_early_payment_discount_available()
            invoice.early_payment_discount_amount = invoice.calculate_early_payment_discount()

            invoice_responses.append(ARInvoiceResponse(**invoice.__dict__))

        return invoice_responses
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filter parameters")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/invoices/{invoice_id}", response_model=ARInvoiceResponse)
async def get_ar_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific AR invoice."""
    try:
        from uuid import UUID
        from sqlalchemy import select

        result = await db.execute(
            select(ARInvoice).where(ARInvoice.id == UUID(invoice_id))
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        # Add derived fields
        invoice.days_overdue = invoice.days_overdue()
        invoice.is_overdue = invoice.is_overdue()
        invoice.early_payment_discount_available = invoice.is_early_payment_discount_available()
        invoice.early_payment_discount_amount = invoice.calculate_early_payment_discount()

        return ARInvoiceResponse(**invoice.__dict__)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invoice ID")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/invoices/{invoice_id}", response_model=ARInvoiceResponse)
async def update_ar_invoice(
    invoice_id: str,
    invoice_update: ARInvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an AR invoice."""
    try:
        from uuid import UUID
        from sqlalchemy import select

        result = await db.execute(
            select(ARInvoice).where(ARInvoice.id == UUID(invoice_id))
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        # Update fields
        update_data = invoice_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(invoice, field, value)

        await db.commit()
        await db.refresh(invoice)

        # Add derived fields
        invoice.days_overdue = invoice.days_overdue()
        invoice.is_overdue = invoice.is_overdue()
        invoice.early_payment_discount_available = invoice.is_early_payment_discount_available()
        invoice.early_payment_discount_amount = invoice.calculate_early_payment_discount()

        return ARInvoiceResponse(**invoice.__dict__)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invoice ID")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Payment endpoints

@router.post("/invoices/{invoice_id}/payments", response_model=ARInvoiceResponse)
async def apply_payment(
    invoice_id: str,
    payment_data: PaymentApply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Apply payment to an AR invoice."""
    try:
        from uuid import UUID

        invoice = await ar_service.apply_payment(
            db, UUID(invoice_id), payment_data.payment_amount, payment_data.payment_date
        )

        # Add derived fields
        invoice.days_overdue = invoice.days_overdue()
        invoice.is_overdue = invoice.is_overdue()
        invoice.early_payment_discount_available = invoice.is_early_payment_discount_available()
        invoice.early_payment_discount_amount = invoice.calculate_early_payment_discount()

        return ARInvoiceResponse(**invoice.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/payments/bulk", response_model=BulkPaymentApplicationResult)
async def apply_bulk_payments(
    bulk_payment: BulkPaymentApplication,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Apply multiple payments in bulk."""
    try:
        from uuid import UUID, uuid4

        results = []
        total_applied = Decimal("0")
        successful_count = 0

        for i, payment in enumerate(bulk_payment.payments):
            try:
                # For bulk payments, we need to get the invoice_id from somewhere
                # This is a simplified example - in practice, you'd pass invoice_id with each payment
                raise ValueError("Invoice ID required for payment application")
            except Exception as e:
                results.append({
                    "payment_id": uuid4(),
                    "invoice_id": None,
                    "invoice_number": None,
                    "amount_applied": Decimal("0"),
                    "success": False,
                    "error_message": str(e),
                    "new_outstanding_amount": None,
                    "new_status": None
                })

        return BulkPaymentApplicationResult(
            total_payments=len(bulk_payment.payments),
            successful_payments=successful_count,
            failed_payments=len(bulk_payment.payments) - successful_count,
            total_amount_applied=total_applied,
            results=results
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Analytics and reporting endpoints

@router.get("/analytics/working-capital", response_model=WorkingCapitalSummary)
async def get_working_capital_summary(
    customer_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get working capital summary for AR portfolio."""
    try:
        from uuid import UUID

        customer_uuid = UUID(customer_id) if customer_id else None
        summary = await ar_service.get_working_capital_summary(db, customer_uuid)
        return WorkingCapitalSummary(**summary)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except Exception as e:
        raise HTTPException(status_code=status_HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/collection-recommendations", response_model=List[CollectionRecommendation])
async def get_collection_recommendations(
    customer_id: Optional[str] = Query(None),
    priority: Optional[CollectionPriority] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get collection recommendations for overdue invoices."""
    try:
        from uuid import UUID

        customer_uuid = UUID(customer_id) if customer_id else None
        recommendations = await ar_service.get_collection_recommendations(db, customer_uuid)

        # Filter by priority if specified
        if priority:
            recommendations = [r for r in recommendations if r["priority"] == priority.value]

        return [CollectionRecommendation(**r) for r in recommendations]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/early-payment-discounts", response_model=List[EarlyPaymentDiscountOpportunity])
async def get_early_payment_discount_opportunities(
    customer_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get early payment discount opportunities."""
    try:
        from uuid import UUID

        customer_uuid = UUID(customer_id) if customer_id else None
        opportunities = await ARInvoice.find_early_payment_discount_opportunities(db)

        if customer_uuid:
            opportunities = [o for o in opportunities if o["customer_id"] == customer_uuid]

        return [EarlyPaymentDiscountOpportunity(**o) for o in opportunities]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/optimization-score", response_model=WorkingCapitalOptimizationScore)
async def get_working_capital_optimization_score(
    customer_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get working capital optimization score."""
    try:
        from uuid import UUID

        customer_uuid = UUID(customer_id) if customer_id else None
        score_data = await ARInvoice.calculate_working_capital_optimization_score(db, customer_uuid)
        return WorkingCapitalOptimizationScore(**score_data)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/collection-efficiency", response_model=CollectionEfficiencyMetrics)
async def get_collection_efficiency_metrics(
    customer_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get collection efficiency metrics."""
    try:
        from uuid import UUID

        customer_uuid = UUID(customer_id) if customer_id else None
        metrics = await ARInvoice.calculate_collection_efficiency(db, customer_uuid)
        return CollectionEfficiencyMetrics(**metrics)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/cash-flow-forecast", response_model=List[CashFlowForecast])
async def get_cash_flow_forecast(
    customer_id: Optional[str] = Query(None),
    weeks: int = Query(12, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get cash flow forecast for AR invoices."""
    try:
        from uuid import UUID
        from datetime import timedelta

        customer_uuid = UUID(customer_id) if customer_id else None
        cash_flow = await ARInvoice.calculate_cash_flow(db, customer_uuid)

        forecasts = []
        start_date = datetime.utcnow().date()

        # Generate weekly forecasts
        for week in range(weeks):
            week_start = start_date + timedelta(weeks=week)
            week_end = week_start + timedelta(days=6)
            week_key = (week_start.isocalendar()[0], week_start.isocalendar()[1])  # (year, week)

            amount = cash_flow["weekly_forecast"].get(week_key, Decimal("0"))
            count = 1  # Simplified count

            forecasts.append(CashFlowForecast(
                period_start=week_start,
                period_end=week_end,
                expected_amount=amount,
                invoice_count=count
            ))

        return forecasts
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parameters")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/customers/{customer_id}/outstanding", response_model=CustomerOutstandingInvoices)
async def get_customer_outstanding_invoices(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get outstanding invoices for a customer."""
    try:
        from uuid import UUID
        from sqlalchemy import select

        customer_uuid = UUID(customer_id)

        # Get customer
        result = await db.execute(
            select(Customer).where(Customer.id == customer_uuid)
        )
        customer = result.scalar_one_or_none()

        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        # Get outstanding invoices
        outstanding_invoices = await ar_service.get_customer_outstanding_invoices(db, customer_uuid)

        # Calculate totals
        total_outstanding = sum(inv.outstanding_amount for inv in outstanding_invoices)

        # Add derived fields to invoices
        invoice_responses = []
        for invoice in outstanding_invoices:
            invoice.days_overdue = invoice.days_overdue()
            invoice.is_overdue = invoice.is_overdue()
            invoice.early_payment_discount_available = invoice.is_early_payment_discount_available()
            invoice.early_payment_discount_amount = invoice.calculate_early_payment_discount()

            invoice_responses.append(ARInvoiceResponse(**invoice.__dict__))

        return CustomerOutstandingInvoices(
            customer_id=customer_uuid,
            customer_name=customer.name,
            total_outstanding=total_outstanding,
            invoice_count=len(outstanding_invoices),
            overdue_invoices=invoice_responses
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customer ID")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))