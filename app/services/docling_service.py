"""
Docling integration for document extraction and parsing.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import aiofiles
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import DoclingDocument

from app.core.config import settings
from app.core.exceptions import ExtractionException

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
    ) -> Dict[str, Any]:
        """Extract data from document content bytes."""
        logger.info(f"Extracting data from content ({len(file_content)} bytes)")

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
            if hasattr(doc, 'pages') and len(doc.pages) > self.max_pages:
                logger.warning(f"Document has {len(doc.pages)} pages, exceeding limit of {self.max_pages}")

            # Extract header information
            header_data = await self._extract_header(doc)

            # Extract line items (table data)
            lines_data = await self._extract_lines(doc)

            # Calculate confidence scores
            confidence_data = await self._calculate_confidence(doc, header_data, lines_data)

            # Calculate overall confidence
            overall_confidence = await self._calculate_overall_confidence(confidence_data)

            extraction_result = {
                "header": header_data,
                "lines": lines_data,
                "confidence": confidence_data,
                "overall_confidence": overall_confidence,
                "metadata": {
                    "file_path": file_path,
                    "file_hash": hashlib.sha256(file_content).hexdigest(),
                    "file_size": len(file_content),
                    "pages_processed": len(getattr(doc, 'pages', [])),
                    "extracted_at": datetime.utcnow().isoformat(),
                    "parser_version": "docling-2.60.1",
                    "conversion_status": str(result.status),
                }
            }

            logger.info(f"Successfully extracted data with overall confidence: {overall_confidence:.2f}")
            return extraction_result

        except Exception as e:
            logger.error(f"Failed to extract document content: {e}")
            raise ExtractionException(f"Document extraction failed: {str(e)}")

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