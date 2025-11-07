"""
Vendor management endpoints.
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.api.schemas import VendorCreate, VendorResponse, VendorListResponse
from app.db.session import get_db
from app.models.reference import Vendor, VendorStatus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=VendorResponse)
async def create_vendor(
    vendor: VendorCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new vendor."""
    try:
        # Check if vendor already exists
        result = await db.execute(
            select(Vendor).where(Vendor.tax_id == vendor.tax_id)
        )
        existing_vendor = result.scalar_one_or_none()
        if existing_vendor:
            raise HTTPException(status_code=409, detail="Vendor with this tax ID already exists")

        # Create vendor
        db_vendor = Vendor(
            name=vendor.name,
            tax_id=vendor.tax_id,
            currency=vendor.currency,
            email=vendor.email,
            phone=vendor.phone,
            address=vendor.address,
            payment_terms_days=vendor.payment_terms_days,
            credit_limit=vendor.credit_limit,
            status=VendorStatus.ACTIVE,
        )
        db.add(db_vendor)
        await db.commit()
        await db.refresh(db_vendor)

        logger.info(f"Created vendor {db_vendor.id}")
        return VendorResponse.from_orm(db_vendor)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vendor: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=VendorListResponse)
async def list_vendors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List vendors with optional filtering."""
    try:
        # Build base query
        conditions = []

        # Apply filters
        if status:
            try:
                status_enum = VendorStatus[status.upper()]
                conditions.append(Vendor.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        if search:
            conditions.append(Vendor.name.ilike(f"%{search}%"))

        # Build the query
        base_query = select(Vendor)
        if conditions:
            base_query = base_query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count(Vendor.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination and get vendors
        query = base_query.offset(skip).limit(limit)
        result = await db.execute(query)
        vendors = result.scalars().all()

        return VendorListResponse(
            vendors=[VendorResponse.from_orm(vendor) for vendor in vendors],
            total=total,
            skip=skip,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing vendors: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get vendor details by ID."""
    try:
        vendor_uuid = uuid.UUID(vendor_id)
        result = await db.execute(
            select(Vendor).where(Vendor.id == vendor_uuid)
        )
        vendor = result.scalar_one_or_none()

        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        return VendorResponse.from_orm(vendor)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vendor_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vendor {vendor_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")