"""
Docling integration for document extraction and parsing.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

import aiofiles
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
from app.services.schema_service import schema_service

logger = logging.getLogger(__name__)


class DoclingService:
    """Service for document extraction using Docling."""

    def __init__(self):
        """Initialize the Docling service."""
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = True
        self.pipeline_options.do_table_structure = True
        self.confidence_threshold = settings.DOCLING_CONFIDENCE_THRESHOLD
        self.max_pages = settings.DOCLING_MAX_PAGES

        # Initialize DocumentConverter with pipeline options
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=self.pipeline_options),
            }
        )

    async def extract_from_file(self, file_path: str) -> Dict[str, Any]:
        """Extract data from a document file."""
        logger.info(f"Extracting data from file: {file_path}")

        try:
            # Read file content
            async with aiofiles.open(file_path, "rb") as f:
                file_content = await f.read()

            return await self.extract_from_content(file_content, file_path=file_path)

        except Exception as e:
            logger.error(f"Failed to extract from file {file_path}: {e}")
            raise ExtractionException(f"Failed to extract document: {str(e)}")

    async def extract_from_content(
        self, file_content: bytes, file_path: Optional[str] = None
    ) -> InvoiceExtractionResult:
        """Extract data from document content bytes and return structured result."""
        logger.info(f"Extracting data from content ({len(file_content)} bytes)")
        start_time = datetime.utcnow()

        try:
            # Convert document using DocumentConverter
            # For content bytes, save to temporary file if needed, or use file_path directly
            if file_path:
                result = self.converter.convert(file_path)
            else:
                # For content bytes without file path, save to temp file first
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name

                try:
                    result = self.converter.convert(temp_file_path)
                finally:
                    # Clean up temporary file
                    os.unlink(temp_file_path)

            doc = result.document

            # Check page count
            page_count = len(getattr(doc, 'pages', []))
            if page_count > self.max_pages:
                logger.warning(f"Document has {page_count} pages, exceeding limit of {self.max_pages}")

            # Extract header information
            header_data = await self._extract_header(doc)

            # Extract line items (table data)
            lines_data = await self._extract_lines(doc)

            # Calculate confidence scores
            confidence_data = await self._calculate_confidence(doc, header_data, lines_data)

            # Create structured Pydantic models
            header_model = self._create_header_model(header_data)
            lines_models = self._create_line_item_models(lines_data)
            confidence_model = self._create_confidence_model(confidence_data)

            # Calculate processing time
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create metadata
            metadata = ExtractionMetadata(
                parser_version="docling-2.60.1",
                processing_time_ms=processing_time,
                page_count=page_count,
                file_size_bytes=len(file_content),
                completeness_score=self._calculate_completeness_score(header_model, lines_models),
                accuracy_score=confidence_model.overall
            )

            # Create structured extraction result
            extraction_result = InvoiceExtractionResult(
                header=header_model,
                lines=lines_models,
                confidence=confidence_model,
                metadata=metadata,
                processing_notes=self._generate_processing_notes(header_data, lines_data, confidence_data)
            )

            # Validate extraction result against schema
            try:
                is_valid, errors, metadata = schema_service.validate_invoice_extraction(
                    extraction_result,
                    schema_version="1.0.0",
                    strict_mode=False
                )

                if not is_valid:
                    logger.warning(f"Extraction result validation warnings: {errors}")
                    # Add validation notes to processing notes
                    if extraction_result.processing_notes is None:
                        extraction_result.processing_notes = []
                    extraction_result.processing_notes.extend([f"Schema validation: {error}" for error in errors])
                else:
                    logger.debug("Extraction result passed schema validation")

            except Exception as e:
                logger.warning(f"Schema validation failed: {e}")

            logger.info(f"Successfully extracted data with overall confidence: {float(confidence_model.overall):.2f}")
            return extraction_result

        except Exception as e:
            logger.error(f"Failed to extract document content: {e}")
            # Return a structured result with error information instead of raising
            return self._create_error_result(e, file_path, len(file_content), start_time)

    async def _extract_header(self, doc: DoclingDocument) -> Dict[str, Any]:
        """Extract header information from document."""
        logger.debug("Extracting header information")

        header = {}

        try:
            # Get full text
            full_text = doc.export_to_markdown()

            # Extract vendor name
            vendor_patterns = [
                r"(?:vendor|supplier|bill to|from):\s*([^\n\r]+?)(?:\n|$)",
                r"^(.+?)\s+(?:invoice|bill)",
                r"([A-Z][a-z]+\s+(?:Inc|LLC|Corp|Co|Ltd))",
            ]
            header["vendor_name"] = self._extract_with_patterns(full_text, vendor_patterns)

            # Extract invoice number
            invoice_patterns = [
                r"(?:invoice\s*(?:no|#|number))\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
                r"invoice[:\s]*([A-Za-z0-9\-\/]+)",
                r"bill[:\s]*([A-Za-z0-9\-\/]+)",
            ]
            header["invoice_no"] = self._extract_with_patterns(full_text, invoice_patterns)

            # Extract invoice date
            date_patterns = [
                r"(?:invoice\s+date|date|bill\s+date):\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
                r"date[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
            ]
            header["invoice_date"] = self._extract_with_patterns(full_text, date_patterns)

            # Extract due date
            due_date_patterns = [
                r"(?:due\s+date|payment\s+due):\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
                r"due[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
            ]
            header["due_date"] = self._extract_with_patterns(full_text, due_date_patterns)

            # Extract PO number
            po_patterns = [
                r"(?:purchase\s+order|po|p\.o\.)\s*(?:no|#|number)\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
                r"po[:\s]*([A-Za-z0-9\-\/]+)",
            ]
            header["po_no"] = self._extract_with_patterns(full_text, po_patterns)

            # Extract currency
            currency_patterns = [
                r"(?:currency|curr)[:\s]*([A-Z]{3})",
                r"\$|€|£|¥|₹",
            ]
            header["currency"] = self._extract_currency(full_text)

            # Extract monetary amounts
            header = await self._extract_amounts(full_text, header)

            # Clean and normalize extracted data
            header = self._clean_header_data(header)

            return header

        except Exception as e:
            logger.error(f"Failed to extract header: {e}")
            return {}

    async def _extract_lines(self, doc: DoclingDocument) -> List[Dict[str, Any]]:
        """Extract line items (table data) from document."""
        logger.debug("Extracting line items")

        lines = []

        try:
            # Look for tables in the document
            full_text = doc.export_to_markdown()

            # Try to extract line items from table-like structures
            lines = self._extract_table_lines(full_text)

            # If no table found, try to extract from text patterns
            if not lines:
                lines = self._extract_text_lines(full_text)

            logger.info(f"Extracted {len(lines)} line items")
            return lines

        except Exception as e:
            logger.error(f"Failed to extract lines: {e}")
            return []

    async def _calculate_confidence(
        self, doc: DoclingDocument, header: Dict[str, Any], lines: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate confidence scores for extracted data."""
        logger.debug("Calculating confidence scores")

        confidence = {
            "header": {},
            "lines": [],
            "overall": 0.0,
        }

        try:
            # Header confidence based on pattern matching and data completeness
            header_fields = ["vendor_name", "invoice_no", "invoice_date", "total"]
            extracted_fields = sum(1 for field in header_fields if header.get(field))
            header_confidence = extracted_fields / len(header_fields)

            confidence["header"] = {
                "vendor_name": 0.9 if header.get("vendor_name") else 0.0,
                "invoice_no": 0.9 if header.get("invoice_no") else 0.0,
                "invoice_date": 0.8 if header.get("invoice_date") else 0.0,
                "po_no": 0.7 if header.get("po_no") else 0.0,
                "total": 0.8 if header.get("total") else 0.0,
                "overall": header_confidence,
            }

            # Line items confidence
            if lines:
                line_confidences = []
                for line in lines:
                    required_fields = ["description", "amount"]
                    line_fields = sum(1 for field in required_fields if line.get(field))
                    line_confidence = line_fields / len(required_fields)
                    line_confidences.append(line_confidence)

                confidence["lines"] = line_confidences
                confidence["overall_lines"] = sum(line_confidences) / len(line_confidences) if line_confidences else 0.0
            else:
                confidence["lines"] = []
                confidence["overall_lines"] = 0.0

            # Overall confidence
            confidence["overall"] = (header_confidence * 0.6) + (confidence["overall_lines"] * 0.4)

            return confidence

        except Exception as e:
            logger.error(f"Failed to calculate confidence: {e}")
            return confidence

    async def _calculate_overall_confidence(self, confidence_data: Dict[str, Any]) -> float:
        """Calculate overall confidence score."""
        return confidence_data.get("overall", 0.0)

    def _extract_with_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """Extract text using multiple regex patterns."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result = match.group(1).strip()
                return result if result else None
        return None

    def _extract_currency(self, text: str) -> str:
        """Extract currency from document."""
        # Look for explicit currency codes
        currency_match = re.search(r"\b(USD|EUR|GBP|JPY|INR|CAD|AUD)\b", text, re.IGNORECASE)
        if currency_match:
            return currency_match.group(1).upper()

        # Look for currency symbols
        if "$" in text:
            return "USD"
        elif "€" in text:
            return "EUR"
        elif "£" in text:
            return "GBP"
        elif "¥" in text:
            return "JPY"

        return "USD"  # Default

    async def _extract_amounts(self, text: str, header: Dict[str, Any]) -> Dict[str, Any]:
        """Extract monetary amounts from document."""
        amount_patterns = [
            r"(?:subtotal|sub[-\s]?total)[:\s]*\$?([\d,]+\.\d{2})",
            r"(?:tax|vat|gst)[:\s]*\$?([\d,]+\.\d{2})",
            r"(?:total|grand[-\s]?total|amount[-\s]?due)[:\s]*\$?([\d,]+\.\d{2})",
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    amount = float(amount_str)
                    if "subtotal" in pattern.lower():
                        header["subtotal"] = amount
                    elif "tax" in pattern.lower():
                        header["tax"] = amount
                    elif "total" in pattern.lower():
                        header["total"] = amount
                except ValueError:
                    continue

        return header

    def _extract_table_lines(self, text: str) -> List[Dict[str, Any]]:
        """Extract line items from table-like structures."""
        lines = []

        # Look for table patterns
        table_pattern = r"(?:description|item|product|service)[^\n]*\n((?:[^\n]*\d+\.?\d*[^\n]*\n)+)"
        table_match = re.search(table_pattern, text, re.IGNORECASE | re.MULTILINE)

        if table_match:
            table_content = table_match.group(1)
            line_items = re.split(r"\n(?=[^\n]*\d+\.?\d*)", table_content.strip())

            for item in line_items:
                if item.strip():
                    # Try to parse line item
                    line_data = self._parse_line_item(item)
                    if line_data:
                        lines.append(line_data)

        return lines

    def _extract_text_lines(self, text: str) -> List[Dict[str, Any]]:
        """Extract line items from text patterns."""
        lines = []

        # Look for line items with amounts
        line_pattern = r"([^\n]+?)\s+([\d,]+\.\d{2})\s*$"
        matches = re.findall(line_pattern, text, re.MULTILINE)

        for description, amount in matches:
            if description.strip() and amount:
                lines.append({
                    "description": description.strip(),
                    "amount": float(amount.replace(",", "")),
                    "quantity": 1,
                    "unit_price": float(amount.replace(",", "")),
                })

        return lines

    def _parse_line_item(self, item_text: str) -> Optional[Dict[str, Any]]:
        """Parse a single line item from text."""
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

        return {
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": amount,
            "sku": "",  # Not typically in basic invoices
        }

    def _clean_header_data(self, header: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and normalize header data."""
        cleaned = {}

        for key, value in header.items():
            if value is not None and str(value).strip():
                if key.endswith("_date") and value:
                    cleaned[key] = self._normalize_date(value)
                elif key.endswith(("_no", "name", "currency")):
                    cleaned[key] = str(value).strip()
                elif key in ("subtotal", "tax", "total"):
                    cleaned[key] = float(value) if isinstance(value, (int, float, str)) else value

        return cleaned

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to ISO format."""
        if not date_str:
            return None

        # Simple date normalization - could be enhanced with dateparser
        date_patterns = [
            r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})",
            r"(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                # Try to construct a valid date
                groups = match.groups()
                try:
                    if len(groups[2]) == 2:  # YY format
                        year = "20" + groups[2] if int(groups[2]) < 50 else "19" + groups[2]
                    else:
                        year = groups[2]

                    month = groups[1].zfill(2)
                    day = groups[0].zfill(2)

                    return f"{year}-{month}-{day}"
                except (ValueError, IndexError):
                    continue

        return date_str  # Return original if parsing fails

    def _create_header_model(self, header_data: Dict[str, Any]) -> InvoiceHeader:
        """Create InvoiceHeader model from extracted data."""
        try:
            return InvoiceHeader(
                invoice_number=header_data.get("invoice_no"),
                invoice_date=self._parse_date(header_data.get("invoice_date")),
                due_date=self._parse_date(header_data.get("due_date")),
                vendor_name=header_data.get("vendor_name"),
                vendor_address={},  # TODO: Extract address information
                vendor_tax_id=None,  # TODO: Extract tax ID
                subtotal_amount=self._safe_decimal(header_data.get("subtotal")),
                tax_amount=self._safe_decimal(header_data.get("tax")),
                total_amount=self._safe_decimal(header_data.get("total")),
                currency=header_data.get("currency", "USD")
            )
        except Exception as e:
            logger.warning(f"Error creating header model: {e}")
            # Return a minimal valid header
            return InvoiceHeader(
                currency="USD",
                invoice_number=header_data.get("invoice_no", "UNKNOWN")
            )

    def _create_line_item_models(self, lines_data: List[Dict[str, Any]]) -> List[InvoiceLineItem]:
        """Create InvoiceLineItem models from extracted data."""
        line_items = []

        for i, line_data in enumerate(lines_data[:10]):  # Limit to 10 items
            try:
                description = line_data.get("description", "Unknown Item")
                quantity = self._safe_decimal(line_data.get("quantity", 1))
                unit_price = self._safe_decimal(line_data.get("unit_price", line_data.get("amount", 0)))
                total_amount = self._safe_decimal(line_data.get("amount", unit_price * quantity))

                line_item = InvoiceLineItem(
                    description=description[:500],  # Limit length
                    quantity=quantity,
                    unit_price=unit_price,
                    total_amount=total_amount,
                    line_number=i + 1,
                    item_code=line_data.get("sku")
                )
                line_items.append(line_item)

            except Exception as e:
                logger.warning(f"Error creating line item {i}: {e}")
                # Skip invalid line items
                continue

        return line_items

    def _create_confidence_model(self, confidence_data: Dict[str, Any]) -> ConfidenceScores:
        """Create ConfidenceScores model from extracted data."""
        try:
            header_conf = confidence_data.get("header", {})

            return ConfidenceScores(
                overall=self._safe_decimal(confidence_data.get("overall", 0.5)),
                invoice_number_confidence=self._safe_decimal(header_conf.get("invoice_no", 0.0)),
                vendor_confidence=self._safe_decimal(header_conf.get("vendor_name", 0.0)),
                date_confidence=self._safe_decimal(header_conf.get("invoice_date", 0.0)),
                amounts_confidence=self._safe_decimal(header_conf.get("total", 0.0)),
                line_items_confidence=self._safe_decimal(confidence_data.get("overall_lines", 0.0))
            )
        except Exception as e:
            logger.warning(f"Error creating confidence model: {e}")
            # Return minimal confidence scores
            return ConfidenceScores(overall=Decimal("0.1"))

    def _safe_decimal(self, value: Any) -> Decimal:
        """Safely convert a value to Decimal."""
        if value is None:
            return Decimal("0")
        try:
            if isinstance(value, Decimal):
                return value
            elif isinstance(value, (int, float)):
                return Decimal(str(value))
            elif isinstance(value, str):
                # Remove currency symbols and commas
                cleaned = value.replace("$", "").replace(",", "").strip()
                return Decimal(cleaned)
            else:
                return Decimal("0")
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not convert {value} to Decimal: {e}")
            return Decimal("0")

    def _parse_date(self, date_str: Any) -> Optional[datetime]:
        """Parse date string into datetime object."""
        if not date_str:
            return None

        try:
            if isinstance(date_str, datetime):
                return date_str

            date_str = str(date_str).strip()

            # Try common date formats
            date_formats = [
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%m-%d-%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
                "%d.%m.%Y",
                "%m.%d.%Y"
            ]

            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

            logger.warning(f"Could not parse date: {date_str}")
            return None

        except Exception as e:
            logger.warning(f"Error parsing date {date_str}: {e}")
            return None

    def _calculate_completeness_score(
        self,
        header: InvoiceHeader,
        lines: List[InvoiceLineItem]
    ) -> Decimal:
        """Calculate data completeness score."""
        score = 0.0
        max_score = 6.0  # Total number of important fields

        # Check header fields
        if header.invoice_number:
            score += 1.0
        if header.vendor_name:
            score += 1.0
        if header.invoice_date:
            score += 1.0
        if header.total_amount and header.total_amount > 0:
            score += 1.0
        if header.currency:
            score += 1.0

        # Check line items
        if lines and len(lines) > 0:
            score += 1.0

        return Decimal(str(min(score / max_score, 1.0)))

    def _generate_processing_notes(
        self,
        header_data: Dict[str, Any],
        lines_data: List[Dict[str, Any]],
        confidence_data: Dict[str, Any]
    ) -> List[str]:
        """Generate processing notes for the extraction."""
        notes = []

        # Header notes
        missing_header_fields = []
        if not header_data.get("vendor_name"):
            missing_header_fields.append("vendor name")
        if not header_data.get("invoice_no"):
            missing_header_fields.append("invoice number")
        if not header_data.get("total"):
            missing_header_fields.append("total amount")

        if missing_header_fields:
            notes.append(f"Missing header fields: {', '.join(missing_header_fields)}")

        # Line items notes
        if not lines_data:
            notes.append("No line items found")
        elif len(lines_data) == 1:
            notes.append("Only one line item found")

        # Confidence notes
        overall_conf = confidence_data.get("overall", 0.0)
        if overall_conf < 0.5:
            notes.append("Low overall confidence score")
        elif overall_conf < 0.8:
            notes.append("Medium overall confidence score")

        if not notes:
            notes.append("Extraction completed successfully")

        return notes

    def _create_error_result(
        self,
        error: Exception,
        file_path: Optional[str],
        file_size: int,
        start_time: datetime
    ) -> InvoiceExtractionResult:
        """Create a structured error result."""
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Create minimal valid data
        header = InvoiceHeader(currency="USD")
        lines: List[InvoiceLineItem] = []
        confidence = ConfidenceScores(overall=Decimal("0.0"))

        metadata = ExtractionMetadata(
            parser_version="docling-2.60.1",
            processing_time_ms=processing_time,
            page_count=0,
            file_size_bytes=file_size,
            completeness_score=Decimal("0.0"),
            accuracy_score=Decimal("0.0")
        )

        processing_notes = [f"Extraction failed: {str(error)}"]

        return InvoiceExtractionResult(
            header=header,
            lines=lines,
            confidence=confidence,
            metadata=metadata,
            processing_notes=processing_notes
        )