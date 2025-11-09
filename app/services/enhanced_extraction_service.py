"""
Enhanced extraction service with per-field confidence scoring, PDF bbox coordinates,
and field-level lineage tracking.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from decimal import Decimal
from dataclasses import dataclass
import json

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import DoclingDocument

from app.core.config import settings
from app.core.exceptions import ExtractionException
from app.models.schemas import (
    InvoiceExtractionResult,
    InvoiceHeader,
    InvoiceLineItem,
    ConfidenceScores,
    ExtractionMetadata
)
from app.models.extraction import FieldExtraction, BBoxCoordinates, ExtractionLineage
from app.services.llm_patch_service import LLMPatchService

logger = logging.getLogger(__name__)


@dataclass
class FieldMetadata:
    """Metadata for extracted fields."""
    value: Any
    confidence: float
    bbox: Optional[BBoxCoordinates] = None
    extraction_method: str = "docling"
    lineage: Optional[ExtractionLineage] = None
    validation_errors: List[str] = None

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []


@dataclass
class BBoxCoordinates:
    """PDF bounding box coordinates for field location."""
    page: int
    x0: float  # left
    y0: float  # top
    x1: float  # right
    y1: float  # bottom

    def to_dict(self) -> Dict[str, float]:
        return {
            "page": self.page,
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1
        }


@dataclass
class ExtractionLineage:
    """Lineage tracking for extraction provenance."""
    extraction_version: str
    timestamp: datetime
    method: str
    confidence_sources: List[str]
    llm_patched: bool = False
    original_value: Any = None
    patch_timestamp: Optional[datetime] = None
    patch_confidence: Optional[float] = None


class EnhancedExtractionService:
    """Enhanced extraction service with per-field confidence and bbox tracking."""

    def __init__(self):
        """Initialize the enhanced extraction service."""
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = True
        self.pipeline_options.do_table_structure = True
        self.confidence_threshold = settings.DOCLING_CONFIDENCE_THRESHOLD
        self.max_pages = settings.DOCLING_MAX_PAGES

        # Initialize DocumentConverter
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=self.pipeline_options),
            }
        )

        # Initialize LLM patch service
        self.llm_patch_service = LLMPatchService()

        # Field extraction patterns
        self.extraction_patterns = self._init_extraction_patterns()

    def _init_extraction_patterns(self) -> Dict[str, List[str]]:
        """Initialize extraction patterns for different fields."""
        return {
            "vendor_name": [
                r"(?:vendor|supplier|bill to|from):\s*([^\n\r]+?)(?:\n|$)",
                r"^(.+?)\s+(?:invoice|bill)",
                r"([A-Z][a-z]+\s+(?:Inc|LLC|Corp|Co|Ltd))",
            ],
            "invoice_number": [
                r"(?:invoice\s*(?:no|#|number))\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
                r"invoice[:\s]*([A-Za-z0-9\-\/]+)",
                r"bill[:\s]*([A-Za-z0-9\-\/]+)",
            ],
            "invoice_date": [
                r"(?:invoice\s+date|date|bill\s+date):\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
                r"date[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
            ],
            "due_date": [
                r"(?:due\s+date|payment\s+due):\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
                r"due[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
            ],
            "po_number": [
                r"(?:purchase\s+order|po|p\.o\.)\s*(?:no|#|number)\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
                r"po[:\s]*([A-Za-z0-9\-\/]+)",
            ],
            "subtotal": [
                r"(?:subtotal|sub[-\s]?total)[:\s]*\$?([\d,]+\.\d{2})",
            ],
            "tax": [
                r"(?:tax|vat|gst)[:\s]*\$?([\d,]+\.\d{2})",
            ],
            "total": [
                r"(?:total|grand[-\s]?total|amount[-\s]?due)[:\s]*\$?([\d,]+\.\d{2})",
            ],
        }

    async def extract_with_enhancement(
        self,
        file_content: bytes,
        file_path: Optional[str] = None,
        enable_llm_patching: bool = True
    ) -> InvoiceExtractionResult:
        """Enhanced extraction with per-field confidence and bbox tracking."""
        logger.info(f"Starting enhanced extraction for {len(file_content)} bytes")
        start_time = datetime.utcnow()

        try:
            # Convert document
            doc = await self._convert_document(file_content, file_path)

            # Extract full text and layout information
            full_text = doc.export_to_markdown()
            layout_info = self._extract_layout_info(doc)

            # Extract header fields with confidence and bbox
            header_fields = await self._extract_header_with_metadata(doc, full_text, layout_info)

            # Extract line items with confidence and bbox
            line_items = await self._extract_lines_with_metadata(doc, full_text, layout_info)

            # Calculate confidence scores
            confidence_scores = self._calculate_enhanced_confidence(header_fields, line_items)

            # Apply LLM patching if enabled and needed
            if enable_llm_patching:
                header_fields, line_items, confidence_scores = await self._apply_llm_patching(
                    header_fields, line_items, confidence_scores
                )

            # Create structured models
            header_model = self._create_header_from_metadata(header_fields)
            line_models = self._create_lines_from_metadata(line_items)
            confidence_model = self._create_confidence_from_scores(confidence_scores)

            # Create extraction metadata with lineage
            metadata = self._create_enhanced_metadata(
                doc, file_content, header_fields, line_items, start_time
            )

            # Generate processing notes
            processing_notes = self._generate_enhanced_processing_notes(
                header_fields, line_items, confidence_scores
            )

            # Create extraction result
            result = InvoiceExtractionResult(
                header=header_model,
                lines=line_models,
                confidence=confidence_model,
                metadata=metadata,
                processing_notes=processing_notes
            )

            logger.info(f"Enhanced extraction completed with confidence: {float(confidence_model.overall):.3f}")
            return result

        except Exception as e:
            logger.error(f"Enhanced extraction failed: {e}")
            raise ExtractionException(f"Enhanced extraction failed: {str(e)}")

    async def _convert_document(self, file_content: bytes, file_path: Optional[str]) -> DoclingDocument:
        """Convert document content to DoclingDocument."""
        try:
            if file_path:
                result = self.converter.convert(file_path)
            else:
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name

                try:
                    result = self.converter.convert(temp_file_path)
                finally:
                    os.unlink(temp_file_path)

            return result.document

        except Exception as e:
            raise ExtractionException(f"Document conversion failed: {str(e)}")

    def _extract_layout_info(self, doc: DoclingDocument) -> Dict[str, Any]:
        """Extract layout information from document."""
        layout_info = {
            "pages": [],
            "text_blocks": [],
            "tables": []
        }

        try:
            # Get page information
            pages = getattr(doc, 'pages', [])
            for i, page in enumerate(pages):
                page_info = {
                    "page_number": i + 1,
                    "size": getattr(page, 'size', None),
                    "blocks": []
                }
                layout_info["pages"].append(page_info)

            # Extract text blocks with positions
            # This is a simplified version - you'd enhance this based on Docling's actual API
            full_text = doc.export_to_markdown()
            lines = full_text.split('\n')

            for line_num, line in enumerate(lines):
                if line.strip():
                    block_info = {
                        "text": line,
                        "line_number": line_num,
                        "page": 1,  # Simplified - would calculate actual page
                        "confidence": 0.9  # Default confidence
                    }
                    layout_info["text_blocks"].append(block_info)

            return layout_info

        except Exception as e:
            logger.warning(f"Failed to extract layout info: {e}")
            return layout_info

    async def _extract_header_with_metadata(
        self,
        doc: DoclingDocument,
        full_text: str,
        layout_info: Dict[str, Any]
    ) -> Dict[str, FieldMetadata]:
        """Extract header fields with confidence and bbox metadata."""
        header_fields = {}

        for field_name, patterns in self.extraction_patterns.items():
            field_metadata = await self._extract_field_with_metadata(
                field_name, patterns, full_text, layout_info
            )
            if field_metadata.value is not None:
                header_fields[field_name] = field_metadata

        return header_fields

    async def _extract_field_with_metadata(
        self,
        field_name: str,
        patterns: List[str],
        full_text: str,
        layout_info: Dict[str, Any]
    ) -> FieldMetadata:
        """Extract a single field with metadata."""
        best_value = None
        best_confidence = 0.0
        best_bbox = None

        for pattern in patterns:
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE | re.MULTILINE))
            for match in matches:
                value = match.group(1).strip() if match.groups() else match.group(0).strip()

                # Calculate confidence based on match quality
                confidence = self._calculate_field_confidence(field_name, value, pattern, match)

                # Extract bbox coordinates (simplified)
                bbox = self._estimate_bbox_from_match(match, layout_info)

                if confidence > best_confidence:
                    best_value = value
                    best_confidence = confidence
                    best_bbox = bbox

        # Create lineage
        lineage = ExtractionLineage(
            extraction_version="2.0.0",
            timestamp=datetime.utcnow(),
            method="docling_regex",
            confidence_sources=["docling", "pattern_match"],
            llm_patched=False
        )

        return FieldMetadata(
            value=best_value,
            confidence=best_confidence,
            bbox=best_bbox,
            extraction_method="docling_regex",
            lineage=lineage
        )

    def _calculate_field_confidence(
        self,
        field_name: str,
        value: str,
        pattern: str,
        match: re.Match
    ) -> float:
        """Calculate confidence score for a field extraction."""
        base_confidence = 0.5

        # Boost confidence based on field name and pattern specificity
        field_weights = {
            "vendor_name": 0.9,
            "invoice_number": 0.9,
            "po_number": 0.8,
            "invoice_date": 0.8,
            "due_date": 0.7,
            "total": 0.9,
            "subtotal": 0.8,
            "tax": 0.8
        }

        confidence = base_confidence + field_weights.get(field_name, 0.5) * 0.3

        # Boost based on pattern complexity
        pattern_complexity = len(pattern.split())
        confidence += min(pattern_complexity * 0.05, 0.2)

        # Validate value format
        if field_name.endswith("_date"):
            confidence += 0.1 if self._is_valid_date(value) else -0.2
        elif field_name in ["total", "subtotal", "tax"]:
            confidence += 0.1 if self._is_valid_amount(value) else -0.2
        elif field_name in ["invoice_number", "po_number"]:
            confidence += 0.1 if self._is_valid_identifier(value) else -0.1

        return min(max(confidence, 0.0), 1.0)

    def _estimate_bbox_from_match(
        self,
        match: re.Match,
        layout_info: Dict[str, Any]
    ) -> Optional[BBoxCoordinates]:
        """Estimate bounding box coordinates from regex match."""
        try:
            # Simplified bbox estimation
            # In a real implementation, you'd use Docling's layout API
            match_start = match.start()
            match_end = match.end()

            # Estimate line number from character position
            text_blocks = layout_info.get("text_blocks", [])
            line_number = 0
            char_count = 0

            for block in text_blocks:
                if char_count + len(block["text"]) >= match_start:
                    break
                char_count += len(block["text"])
                line_number += 1

            # Create estimated bbox
            return BBoxCoordinates(
                page=1,
                x0=100.0,  # Simplified - would calculate actual position
                y0=50.0 + line_number * 15.0,
                x1=300.0,
                y1=65.0 + line_number * 15.0
            )

        except Exception as e:
            logger.warning(f"Failed to estimate bbox: {e}")
            return None

    async def _extract_lines_with_metadata(
        self,
        doc: DoclingDocument,
        full_text: str,
        layout_info: Dict[str, Any]
    ) -> List[Dict[str, FieldMetadata]]:
        """Extract line items with metadata."""
        line_items = []

        # Try table extraction first
        table_lines = self._extract_table_lines_with_metadata(full_text, layout_info)
        if table_lines:
            line_items.extend(table_lines)

        # Fallback to text-based extraction
        if not line_items:
            text_lines = self._extract_text_lines_with_metadata(full_text, layout_info)
            line_items.extend(text_lines)

        return line_items[:10]  # Limit to 10 line items

    def _extract_table_lines_with_metadata(
        self,
        full_text: str,
        layout_info: Dict[str, Any]
    ) -> List[Dict[str, FieldMetadata]]:
        """Extract line items from table structures."""
        line_items = []

        # Look for table patterns
        table_pattern = r"(?:description|item|product|service)[^\n]*\n((?:[^\n]*\d+\.?\d*[^\n]*\n)+)"
        table_match = re.search(table_pattern, full_text, re.IGNORECASE | re.MULTILINE)

        if table_match:
            table_content = table_match.group(1)
            item_lines = re.split(r"\n(?=[^\n]*\d+\.?\d*)", table_content.strip())

            for i, item_text in enumerate(item_lines):
                if item_text.strip():
                    line_data = self._parse_line_item_with_metadata(item_text, i, layout_info)
                    if line_data:
                        line_items.append(line_data)

        return line_items

    def _extract_text_lines_with_metadata(
        self,
        full_text: str,
        layout_info: Dict[str, Any]
    ) -> List[Dict[str, FieldMetadata]]:
        """Extract line items from text patterns."""
        line_items = []

        # Look for line items with amounts
        line_pattern = r"([^\n]+?)\s+([\d,]+\.\d{2})\s*$"
        matches = re.findall(line_pattern, full_text, re.MULTILINE)

        for i, (description, amount) in enumerate(matches):
            if description.strip() and amount:
                line_data = {
                    "description": FieldMetadata(
                        value=description.strip(),
                        confidence=0.8,
                        extraction_method="regex_pattern",
                        lineage=ExtractionLineage(
                            extraction_version="2.0.0",
                            timestamp=datetime.utcnow(),
                            method="regex_pattern",
                            confidence_sources=["pattern_match"]
                        )
                    ),
                    "amount": FieldMetadata(
                        value=float(amount.replace(",", "")),
                        confidence=0.9,
                        extraction_method="regex_pattern",
                        lineage=ExtractionLineage(
                            extraction_version="2.0.0",
                            timestamp=datetime.utcnow(),
                            method="regex_pattern",
                            confidence_sources=["pattern_match"]
                        )
                    ),
                    "quantity": FieldMetadata(
                        value=1,
                        confidence=0.5,  # Default quantity
                        extraction_method="default",
                        lineage=ExtractionLineage(
                            extraction_version="2.0.0",
                            timestamp=datetime.utcnow(),
                            method="default",
                            confidence_sources=["default"]
                        )
                    ),
                    "unit_price": FieldMetadata(
                        value=float(amount.replace(",", "")),
                        confidence=0.8,
                        extraction_method="calculated",
                        lineage=ExtractionLineage(
                            extraction_version="2.0.0",
                            timestamp=datetime.utcnow(),
                            method="calculated",
                            confidence_sources=["calculation"]
                        )
                    )
                }
                line_items.append(line_data)

        return line_items

    def _parse_line_item_with_metadata(
        self,
        item_text: str,
        line_index: int,
        layout_info: Dict[str, Any]
    ) -> Optional[Dict[str, FieldMetadata]]:
        """Parse a single line item with metadata."""
        # Extract amount at the end
        amount_match = re.search(r"([\d,]+\.\d{2})\s*$", item_text.strip())
        if not amount_match:
            return None

        amount = float(amount_match.group(1).replace(",", ""))
        description = item_text[:amount_match.start()].strip()

        # Try to extract quantity and unit price
        qty_price_pattern = r"(\d+(?:\.\d+)?)\s*x\s*([\d,]+\.\d{2})"
        qty_price_match = re.search(qty_price_pattern, description)

        if qty_price_match:
            quantity = float(qty_price_match.group(1))
            unit_price = float(qty_price_match.group(2).replace(",", ""))
            description = description[:qty_price_match.start()].strip()
        else:
            quantity = 1
            unit_price = amount

        # Create metadata for each field
        lineage = ExtractionLineage(
            extraction_version="2.0.0",
            timestamp=datetime.utcnow(),
            method="table_extraction",
            confidence_sources=["table_structure"]
        )

        return {
            "description": FieldMetadata(
                value=description,
                confidence=0.9,
                extraction_method="table_extraction",
                lineage=lineage
            ),
            "quantity": FieldMetadata(
                value=quantity,
                confidence=0.8 if qty_price_match else 0.5,
                extraction_method="table_extraction",
                lineage=lineage
            ),
            "unit_price": FieldMetadata(
                value=unit_price,
                confidence=0.8 if qty_price_match else 0.7,
                extraction_method="table_extraction",
                lineage=lineage
            ),
            "amount": FieldMetadata(
                value=amount,
                confidence=0.95,
                extraction_method="table_extraction",
                lineage=lineage
            )
        }

    def _calculate_enhanced_confidence(
        self,
        header_fields: Dict[str, FieldMetadata],
        line_items: List[Dict[str, FieldMetadata]]
    ) -> ConfidenceScores:
        """Calculate enhanced confidence scores."""
        # Header confidence
        header_confidences = [field.confidence for field in header_fields.values()]
        header_overall = sum(header_confidences) / len(header_confidences) if header_confidences else 0.0

        # Map to specific field confidences
        invoice_number_conf = header_fields.get("invoice_number", FieldMetadata(value=None)).confidence
        vendor_conf = header_fields.get("vendor_name", FieldMetadata(value=None)).confidence
        date_conf = max(
            header_fields.get("invoice_date", FieldMetadata(value=None)).confidence,
            header_fields.get("due_date", FieldMetadata(value=None)).confidence
        )
        amounts_conf = max(
            header_fields.get("total", FieldMetadata(value=None)).confidence,
            header_fields.get("subtotal", FieldMetadata(value=None)).confidence
        )

        # Line items confidence
        line_confidences = []
        for line_item in line_items:
            item_confidences = [field.confidence for field in line_item.values()]
            if item_confidences:
                line_confidences.append(sum(item_confidences) / len(item_confidences))

        lines_overall = sum(line_confidences) / len(line_confidences) if line_confidences else 0.0

        # Overall confidence (weighted)
        overall = (header_overall * 0.6) + (lines_overall * 0.4)

        return ConfidenceScores(
            overall=Decimal(str(round(overall, 3))),
            invoice_number_confidence=Decimal(str(round(invoice_number_conf, 3))),
            vendor_confidence=Decimal(str(round(vendor_conf, 3))),
            date_confidence=Decimal(str(round(date_conf, 3))),
            amounts_confidence=Decimal(str(round(amounts_conf, 3))),
            line_items_confidence=Decimal(str(round(lines_overall, 3)))
        )

    async def _apply_llm_patching(
        self,
        header_fields: Dict[str, FieldMetadata],
        line_items: List[Dict[str, FieldMetadata]],
        confidence_scores: ConfidenceScores
    ) -> Tuple[Dict[str, FieldMetadata], List[Dict[str, FieldMetadata]], ConfidenceScores]:
        """Apply LLM patching to low-confidence fields."""
        if float(confidence_scores.overall) >= self.confidence_threshold:
            return header_fields, line_items, confidence_scores

        logger.info("Applying LLM patching to low-confidence fields")

        # Prepare data for LLM service
        extraction_dict = {
            "header": {k: v.value for k, v in header_fields.items()},
            "lines": [{k: v.value for k, v in line.items()} for line in line_items],
            "confidence": {
                "header": {k: v.confidence for k, v in header_fields.items()},
                "overall": float(confidence_scores.overall)
            }
        }

        # Apply LLM patching
        try:
            patched_result = await self.llm_patch_service.patch_fields(extraction_dict)

            # Update header fields with patches
            patched_header = patched_result.get("header", {})
            for field_name, new_value in patched_header.items():
                if field_name in header_fields:
                    old_field = header_fields[field_name]
                    header_fields[field_name] = FieldMetadata(
                        value=new_value,
                        confidence=0.9,  # High confidence for LLM patches
                        bbox=old_field.bbox,
                        extraction_method="llm_patch",
                        lineage=ExtractionLineage(
                            extraction_version="2.0.0",
                            timestamp=datetime.utcnow(),
                            method="llm_patch",
                            confidence_sources=["llm"],
                            llm_patched=True,
                            original_value=old_field.value,
                            patch_timestamp=datetime.utcnow(),
                            patch_confidence=0.9
                        )
                    )

            # Update line items with patches
            patched_lines = patched_result.get("lines", [])
            for i, patched_line in enumerate(patched_lines):
                if i < len(line_items):
                    for field_name, new_value in patched_line.items():
                        if field_name in line_items[i]:
                            old_field = line_items[i][field_name]
                            line_items[i][field_name] = FieldMetadata(
                                value=new_value,
                                confidence=0.9,
                                bbox=old_field.bbox,
                                extraction_method="llm_patch",
                                lineage=ExtractionLineage(
                                    extraction_version="2.0.0",
                                    timestamp=datetime.utcnow(),
                                    method="llm_patch",
                                    confidence_sources=["llm"],
                                    llm_patched=True,
                                    original_value=old_field.value,
                                    patch_timestamp=datetime.utcnow(),
                                    patch_confidence=0.9
                                )
                            )

            # Recalculate confidence scores
            new_confidence_scores = self._calculate_enhanced_confidence(header_fields, line_items)

            logger.info(f"LLM patching completed, new confidence: {float(new_confidence_scores.overall):.3f}")
            return header_fields, line_items, new_confidence_scores

        except Exception as e:
            logger.error(f"LLM patching failed: {e}")
            return header_fields, line_items, confidence_scores

    def _create_header_from_metadata(self, header_fields: Dict[str, FieldMetadata]) -> InvoiceHeader:
        """Create InvoiceHeader from field metadata."""
        try:
            return InvoiceHeader(
                invoice_number=header_fields.get("invoice_number", FieldMetadata(value=None)).value,
                invoice_date=self._parse_date(header_fields.get("invoice_date", FieldMetadata(value=None)).value),
                due_date=self._parse_date(header_fields.get("due_date", FieldMetadata(value=None)).value),
                vendor_name=header_fields.get("vendor_name", FieldMetadata(value=None)).value,
                subtotal_amount=self._safe_decimal(header_fields.get("subtotal", FieldMetadata(value=None)).value),
                tax_amount=self._safe_decimal(header_fields.get("tax", FieldMetadata(value=None)).value),
                total_amount=self._safe_decimal(header_fields.get("total", FieldMetadata(value=None)).value),
                currency="USD"  # Default currency
            )
        except Exception as e:
            logger.warning(f"Error creating header model: {e}")
            return InvoiceHeader(currency="USD")

    def _create_lines_from_metadata(self, line_items: List[Dict[str, FieldMetadata]]) -> List[InvoiceLineItem]:
        """Create InvoiceLineItem list from metadata."""
        lines = []

        for i, line_data in enumerate(line_items):
            try:
                description = line_data.get("description", FieldMetadata(value="")).value or "Unknown Item"
                quantity = self._safe_decimal(line_data.get("quantity", FieldMetadata(value=1)).value)
                unit_price = self._safe_decimal(line_data.get("unit_price", FieldMetadata(value=0)).value)
                total_amount = self._safe_decimal(line_data.get("amount", FieldMetadata(value=0)).value)

                line_item = InvoiceLineItem(
                    description=description[:500],
                    quantity=quantity,
                    unit_price=unit_price,
                    total_amount=total_amount,
                    line_number=i + 1
                )
                lines.append(line_item)

            except Exception as e:
                logger.warning(f"Error creating line item {i}: {e}")
                continue

        return lines

    def _create_confidence_from_scores(self, confidence_scores: ConfidenceScores) -> ConfidenceScores:
        """Create confidence model from scores."""
        return confidence_scores

    def _create_enhanced_metadata(
        self,
        doc: DoclingDocument,
        file_content: bytes,
        header_fields: Dict[str, FieldMetadata],
        line_items: List[Dict[str, FieldMetadata]],
        start_time: datetime
    ) -> ExtractionMetadata:
        """Create enhanced extraction metadata."""
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        page_count = len(getattr(doc, 'pages', []))

        # Calculate completeness score
        required_header_fields = ["vendor_name", "invoice_number", "total"]
        header_completeness = sum(1 for field in required_header_fields
                                if field in header_fields and header_fields[field].value)
        header_score = header_completeness / len(required_header_fields)

        lines_score = 1.0 if line_items else 0.0

        completeness_score = (header_score * 0.7) + (lines_score * 0.3)

        # Calculate average confidence
        all_confidences = [field.confidence for field in header_fields.values()]
        for line_item in line_items:
            all_confidences.extend(field.confidence for field in line_item.values())

        accuracy_score = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        return ExtractionMetadata(
            parser_version="enhanced-docling-2.0.0",
            processing_time_ms=processing_time,
            page_count=page_count,
            file_size_bytes=len(file_content),
            completeness_score=Decimal(str(round(completeness_score, 3))),
            accuracy_score=Decimal(str(round(accuracy_score, 3)))
        )

    def _generate_enhanced_processing_notes(
        self,
        header_fields: Dict[str, FieldMetadata],
        line_items: List[Dict[str, FieldMetadata]],
        confidence_scores: ConfidenceScores
    ) -> List[str]:
        """Generate enhanced processing notes."""
        notes = []

        # Header field analysis
        missing_header = [name for name, field in header_fields.items()
                         if not field.value and name in ["vendor_name", "invoice_number", "total"]]
        if missing_header:
            notes.append(f"Missing required header fields: {', '.join(missing_header)}")

        # Low confidence fields
        low_confidence_header = [name for name, field in header_fields.items()
                               if field.confidence < self.confidence_threshold]
        if low_confidence_header:
            notes.append(f"Low confidence header fields: {', '.join(low_confidence_header)}")

        # Line items analysis
        if not line_items:
            notes.append("No line items extracted")
        elif len(line_items) == 1:
            notes.append("Only one line item extracted")

        # LLM patching
        llm_patched_fields = []
        for field in header_fields.values():
            if field.lineage and field.lineage.llm_patched:
                llm_patched_fields.append("header field")
                break

        for line_item in line_items:
            for field in line_item.values():
                if field.lineage and field.lineage.llm_patched:
                    llm_patched_fields.append("line item field")
                    break

        if llm_patched_fields:
            notes.append(f"LLM patched fields: {', '.join(set(llm_patched_fields))}")

        # Overall confidence
        overall_conf = float(confidence_scores.overall)
        if overall_conf >= 0.9:
            notes.append("High confidence extraction")
        elif overall_conf >= 0.7:
            notes.append("Medium confidence extraction")
        else:
            notes.append("Low confidence extraction - review recommended")

        if not notes:
            notes.append("Enhanced extraction completed successfully")

        return notes

    # Helper methods
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if string is a valid date."""
        if not date_str:
            return False

        date_patterns = [
            r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}",
            r"\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}"
        ]

        return any(re.match(pattern, date_str.strip()) for pattern in date_patterns)

    def _is_valid_amount(self, amount_str: str) -> bool:
        """Check if string is a valid monetary amount."""
        if not amount_str:
            return False

        try:
            cleaned = amount_str.replace("$", "").replace(",", "").strip()
            float(cleaned)
            return True
        except ValueError:
            return False

    def _is_valid_identifier(self, identifier: str) -> bool:
        """Check if string is a valid identifier (invoice number, PO number)."""
        if not identifier:
            return False

        # Check for alphanumeric characters and common symbols
        return bool(re.match(r'^[A-Za-z0-9\-\/]+$', identifier.strip()))

    def _safe_decimal(self, value: Any) -> Decimal:
        """Safely convert value to Decimal."""
        if value is None:
            return Decimal("0")
        try:
            if isinstance(value, Decimal):
                return value
            elif isinstance(value, (int, float)):
                return Decimal(str(value))
            elif isinstance(value, str):
                cleaned = value.replace("$", "").replace(",", "").strip()
                return Decimal(cleaned)
            else:
                return Decimal("0")
        except (ValueError, TypeError):
            return Decimal("0")

    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Parse date value into datetime."""
        if not date_value:
            return None

        if isinstance(date_value, datetime):
            return date_value

        try:
            date_str = str(date_value).strip()
            date_formats = [
                "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
                "%m-%d-%Y", "%d-%m-%Y", "%Y/%m/%d"
            ]

            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

            return None

        except Exception:
            return None