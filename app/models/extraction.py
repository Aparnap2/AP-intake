"""
Enhanced extraction models for field-level confidence scoring and lineage tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import ForeignKey
import uuid

Base = declarative_base()


class FieldExtraction(Base):
    """Field-level extraction with confidence and bbox coordinates."""
    __tablename__ = "field_extractions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(PG_UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    field_value = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=False)

    # Bounding box coordinates
    bbox_page = Column(Integer, nullable=True)
    bbox_x0 = Column(Float, nullable=True)
    bbox_y0 = Column(Float, nullable=True)
    bbox_x1 = Column(Float, nullable=True)
    bbox_y1 = Column(Float, nullable=True)

    # Extraction metadata
    extraction_method = Column(String(50), nullable=False)
    extraction_version = Column(String(20), nullable=False)
    extracted_at = Column(DateTime, default=datetime.utcnow)

    # LLM patching metadata
    llm_patched = Column(Boolean, default=False)
    original_value = Column(Text, nullable=True)
    patch_timestamp = Column(DateTime, nullable=True)
    patch_confidence = Column(Float, nullable=True)

    # Lineage and provenance
    confidence_sources = Column(JSON, nullable=True)  # List of sources
    validation_errors = Column(JSON, nullable=True)  # List of errors
    processing_notes = Column(JSON, nullable=True)  # Additional notes


class ExtractionLineage(Base):
    """Lineage tracking for extraction provenance."""
    __tablename__ = "extraction_lineage"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(PG_UUID(as_uuid=True), ForeignKey("field_extractions.id"), nullable=False)

    # Version and timestamp
    extraction_version = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Method and sources
    method = Column(String(50), nullable=False)
    confidence_sources = Column(JSON, nullable=True)  # List of sources

    # LLM patching tracking
    llm_patched = Column(Boolean, default=False)
    original_value = Column(Text, nullable=True)
    patch_timestamp = Column(DateTime, nullable=True)
    patch_confidence = Column(Float, nullable=True)
    patch_model = Column(String(50), nullable=True)

    # Quality metrics
    processing_time_ms = Column(Integer, nullable=True)
    token_usage = Column(JSON, nullable=True)  # Token usage for LLM calls

    # Additional metadata
    extraction_metadata = Column(JSON, nullable=True)


class BBoxCoordinates(Base):
    """PDF bounding box coordinates for field locations."""
    __tablename__ = "bbox_coordinates"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(PG_UUID(as_uuid=True), ForeignKey("field_extractions.id"), nullable=False)

    # Coordinates
    page = Column(Integer, nullable=False)
    x0 = Column(Float, nullable=False)  # left
    y0 = Column(Float, nullable=False)  # top
    x1 = Column(Float, nullable=False)  # right
    y1 = Column(Float, nullable=False)  # bottom

    # Additional spatial information
    width = Column(Float, nullable=False)  # calculated from x1-x0
    height = Column(Float, nullable=False)  # calculated from y1-y0
    area = Column(Float, nullable=False)  # calculated area

    # Context information
    block_type = Column(String(50), nullable=True)  # text, table, image, etc.
    neighboring_text = Column(Text, nullable=True)  # Context around the bbox

    # Quality metrics
    coordinate_confidence = Column(Float, nullable=True)
    extraction_method = Column(String(50), nullable=False)


class ExtractionSession(Base):
    """Session tracking for extraction processes."""
    __tablename__ = "extraction_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(PG_UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)

    # Session metadata
    session_start = Column(DateTime, default=datetime.utcnow)
    session_end = Column(DateTime, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    # Configuration
    extraction_version = Column(String(20), nullable=False)
    confidence_threshold = Column(Float, nullable=False)
    llm_patching_enabled = Column(Boolean, default=False)
    max_pages = Column(Integer, nullable=True)

    # Results summary
    total_fields_extracted = Column(Integer, default=0)
    high_confidence_fields = Column(Integer, default=0)
    low_confidence_fields = Column(Integer, default=0)
    llm_patched_fields = Column(Integer, default=0)

    # Performance metrics
    overall_confidence = Column(Float, nullable=True)
    completeness_score = Column(Float, nullable=True)
    accuracy_score = Column(Float, nullable=True)

    # Error tracking
    errors = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    processing_notes = Column(JSON, nullable=True)


# Pydantic models for API
class BBoxCoordinatesModel(BaseModel):
    """Pydantic model for BBox coordinates."""
    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    class Config:
        from_attributes = True


class ExtractionLineageModel(BaseModel):
    """Pydantic model for extraction lineage."""
    extraction_version: str
    timestamp: datetime
    method: str
    confidence_sources: List[str] = []
    llm_patched: bool = False
    original_value: Optional[Any] = None
    patch_timestamp: Optional[datetime] = None
    patch_confidence: Optional[float] = None
    patch_model: Optional[str] = None

    class Config:
        from_attributes = True


class FieldExtractionModel(BaseModel):
    """Pydantic model for field extraction."""
    field_name: str
    field_value: Optional[Any]
    confidence_score: float
    bbox: Optional[BBoxCoordinatesModel] = None
    extraction_method: str
    extraction_version: str
    extracted_at: datetime
    lineage: Optional[ExtractionLineageModel] = None
    validation_errors: List[str] = []
    processing_notes: List[str] = []

    class Config:
        from_attributes = True


class ExtractionSessionModel(BaseModel):
    """Pydantic model for extraction session."""
    session_id: str
    invoice_id: str
    session_start: datetime
    session_end: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    extraction_version: str
    confidence_threshold: float
    llm_patching_enabled: bool = False
    total_fields_extracted: int = 0
    high_confidence_fields: int = 0
    low_confidence_fields: int = 0
    llm_patched_fields: int = 0
    overall_confidence: Optional[float] = None
    completeness_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    errors: List[str] = []
    warnings: List[str] = []
    processing_notes: List[str] = []

    class Config:
        from_attributes = True


class ExtractionSummaryModel(BaseModel):
    """Summary model for extraction results."""
    invoice_id: str
    extraction_version: str
    timestamp: datetime

    # Field counts
    total_header_fields: int
    total_line_items: int

    # Quality metrics
    overall_confidence: float
    average_confidence: float
    completeness_score: float
    accuracy_score: float

    # Enhancement results
    llm_patched_fields: int
    bbox_coordinates_count: int

    # Processing time
    processing_time_ms: int

    # Validation status
    validation_passed: bool
    requires_human_review: bool

    class Config:
        from_attributes = True


class ExtractionMetricsModel(BaseModel):
    """Metrics model for extraction performance."""
    period_start: datetime
    period_end: datetime

    # Volume metrics
    total_invoices_processed: int
    successful_extractions: int
    failed_extractions: int

    # Quality metrics
    average_confidence: float
    average_processing_time_ms: float
    average_completeness_score: float

    # Enhancement metrics
    llm_patching_usage_rate: float
    average_llm_patches_per_invoice: float
    bbox_detection_rate: float

    # Error analysis
    common_extraction_errors: List[Dict[str, Any]]
    most_challenged_fields: List[str]

    # Performance by field type
    field_confidence_breakdown: Dict[str, float]

    class Config:
        from_attributes = True