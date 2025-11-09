"""
Enhanced LLM patch service for intelligent field correction with cost optimization
and detailed tracking.
"""

import logging
import time
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import ExtractionException

logger = logging.getLogger(__name__)


@dataclass
class LLMPatchRequest:
    """Request for LLM field patching."""
    extraction_result: Dict[str, Any]
    confidence_threshold: float
    target_fields: Optional[List[str]] = None
    max_cost_estimate: Optional[float] = None


@dataclass
class LLMPatchResult:
    """Result of LLM field patching."""
    patched_fields: Dict[str, Any]
    patch_metadata: Dict[str, Any]
    cost_estimate: float
    processing_time_ms: int
    token_usage: Dict[str, int]
    model_used: str
    patch_confidence: float


@dataclass
class LLMUsage:
    """Track LLM usage for cost monitoring."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    cost_estimate: float
    timestamp: float
    operation_type: str  # "field_patch", "context_extraction", etc.


class LLMPatchService:
    """Enhanced LLM service for intelligent field patching with cost optimization."""

    def __init__(self):
        """Initialize the enhanced LLM patch service."""
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self.base_url = settings.OPENROUTER_BASE_URL
        self.provider = settings.LLM_PROVIDER
        self.app_name = settings.OPENROUTER_APP_NAME
        self.app_url = settings.OPENROUTER_APP_URL

        # Patching configuration
        self.confidence_threshold = settings.DOCLING_CONFIDENCE_THRESHOLD
        self.min_confidence_for_patching = 0.3  # Don't patch extremely low confidence
        self.max_fields_per_request = 10  # Limit fields per request for cost control
        self.max_cost_per_invoice = 0.10  # Maximum cost per invoice in USD

        # Usage tracking
        self.usage_history: List[LLMUsage] = []
        self.total_cost: float = 0.0
        self.daily_cost: float = 0.0
        self.daily_reset_time: float = time.time()

        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0
        self.backoff_factor = 2.0

        # Initialize client
        self.client = None
        if self.api_key and self.provider == 'openrouter':
            self._init_openrouter_client()

    def _init_openrouter_client(self):
        """Initialize OpenRouter client."""
        try:
            from openai import OpenAI

            default_headers = {
                "HTTP-Referer": self.app_url,
                "X-Title": self.app_name,
            }

            client_kwargs = {
                "api_key": self.api_key,
                "base_url": self.base_url,
                "default_headers": default_headers,
            }

            self.client = OpenAI(**client_kwargs)
            logger.info(f"LLM Patch Service initialized with model: {self.model}")

        except ImportError:
            logger.error("OpenAI package not installed")
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {e}")

    async def patch_fields(
        self,
        extraction_result: Dict[str, Any],
        target_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Patch low-confidence fields using LLM with cost optimization."""
        start_time = time.time()
        logger.info("Starting LLM field patching")

        if not self.client:
            logger.warning("LLM client not available")
            return extraction_result

        try:
            # Identify fields needing patching
            low_confidence_fields = self._identify_patchable_fields(
                extraction_result, target_fields
            )

            if not low_confidence_fields:
                logger.info("No fields need patching")
                return extraction_result

            # Check cost estimate
            cost_estimate = self._estimate_patch_cost(low_confidence_fields)
            if cost_estimate > self.max_cost_per_invoice:
                logger.warning(f"Cost estimate ${cost_estimate:.4f} exceeds limit ${self.max_cost_per_invoice}")
                # Select most important fields to patch
                low_confidence_fields = self._prioritize_fields_for_patching(low_confidence_fields)

            # Generate patch prompt
            prompt = self._generate_enhanced_patch_prompt(
                extraction_result, low_confidence_fields
            )

            # Call LLM with retry logic
            patch_response = await self._call_llm_with_retry(prompt, "field_patch")

            # Apply patches with validation
            patched_result = self._apply_validated_patches(
                extraction_result, patch_response, low_confidence_fields
            )

            # Update confidence scores
            patched_result = self._update_confidence_scores(
                patched_result, low_confidence_fields
            )

            # Track usage and performance
            processing_time = int((time.time() - start_time) * 1000)
            await self._track_patch_performance(
                low_confidence_fields, patch_response, processing_time, cost_estimate
            )

            logger.info(f"Successfully patched {len(low_confidence_fields)} fields in {processing_time}ms")
            return patched_result

        except Exception as e:
            logger.error(f"LLM field patching failed: {e}")
            return extraction_result

    def _identify_patchable_fields(
        self,
        extraction_result: Dict[str, Any],
        target_fields: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Identify fields that need LLM patching."""
        patchable_fields = {}
        confidence_data = extraction_result.get("confidence", {})

        # Check header fields
        header_confidence = confidence_data.get("header", {})
        header_data = extraction_result.get("header", {})

        for field_name, confidence in header_confidence.items():
            if field_name == "overall":
                continue

            # Skip if confidence is too low (likely garbage)
            if confidence < self.min_confidence_for_patching:
                continue

            # Skip if field is already good
            if confidence >= self.confidence_threshold:
                continue

            # Skip if target fields specified and this field not in target
            if target_fields and field_name not in target_fields:
                continue

            # Check if field has a value to work with
            current_value = header_data.get(field_name)
            if current_value is None or (isinstance(current_value, str) and not current_value.strip()):
                continue

            patchable_fields[f"header.{field_name}"] = {
                "current_value": current_value,
                "confidence": confidence,
                "field_type": "header",
                "field_name": field_name
            }

        # Check line items (limit to first few for cost control)
        lines_confidence = confidence_data.get("lines", [])
        lines_data = extraction_result.get("lines", [])

        for i, (line_confidence, line_data) in enumerate(zip(lines_confidence, lines_data)):
            if i >= 3:  # Limit to first 3 line items
                break

            if line_confidence < self.confidence_threshold and line_confidence >= self.min_confidence_for_patching:
                description = line_data.get("description", "")
                if description and description.strip():
                    patchable_fields[f"lines.{i}.description"] = {
                        "current_value": description,
                        "confidence": line_confidence,
                        "field_type": "line_item",
                        "field_name": "description",
                        "line_index": i
                    }

            # Also check amount fields if confidence is low
            amount = line_data.get("amount")
            if (amount and line_confidence < self.confidence_threshold and
                line_confidence >= self.min_confidence_for_patching):
                patchable_fields[f"lines.{i}.amount"] = {
                    "current_value": amount,
                    "confidence": line_confidence,
                    "field_type": "line_item",
                    "field_name": "amount",
                    "line_index": i
                }

        return patchable_fields

    def _estimate_patch_cost(self, patchable_fields: Dict[str, Dict[str, Any]]) -> float:
        """Estimate cost for patching the given fields."""
        # Rough estimation based on field count and complexity
        field_count = len(patchable_fields)

        # Estimate tokens (rough approximation)
        estimated_input_tokens = 500 + (field_count * 50)  # Base prompt + field descriptions
        estimated_output_tokens = field_count * 20  # Rough output per field

        # Cost estimation (adjust based on actual model pricing)
        # Using approximate rates for GPT-3.5-turbo
        input_cost_per_1k = 0.0005
        output_cost_per_1k = 0.0015

        input_cost = (estimated_input_tokens / 1000) * input_cost_per_1k
        output_cost = (estimated_output_tokens / 1000) * output_cost_per_1k

        total_cost = input_cost + output_cost
        return total_cost

    def _prioritize_fields_for_patching(
        self,
        patchable_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Prioritize fields for patching when cost is a constraint."""
        # Sort by business importance
        field_priority = {
            "header.invoice_number": 10,
            "header.vendor_name": 9,
            "header.total": 8,
            "header.invoice_date": 7,
            "header.po_number": 6,
            "lines.0.description": 5,
            "lines.0.amount": 5,
        }

        # Sort fields by priority and confidence (higher confidence first)
        sorted_fields = sorted(
            patchable_fields.items(),
            key=lambda x: (field_priority.get(x[0], 0), x[1]["confidence"]),
            reverse=True
        )

        # Select top fields within budget
        selected_fields = {}
        current_cost = 0.0

        for field_key, field_data in sorted_fields:
            field_cost = self._estimate_patch_cost({field_key: field_data})
            if current_cost + field_cost <= self.max_cost_per_invoice:
                selected_fields[field_key] = field_data
                current_cost += field_cost
            else:
                break

        logger.info(f"Prioritized {len(selected_fields)} fields for patching (estimated cost: ${current_cost:.4f})")
        return selected_fields

    def _generate_enhanced_patch_prompt(
        self,
        extraction_result: Dict[str, Any],
        patchable_fields: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate enhanced prompt for LLM field patching."""
        header = extraction_result.get("header", {})
        lines = extraction_result.get("lines", [])
        confidence = extraction_result.get("confidence", {})

        prompt = """You are an expert invoice data extraction specialist. I need you to review and improve extracted invoice data.

Below is the current extraction result with confidence scores. Fields marked as LOW CONFIDENCE need your attention.

"""
        # Add header information with confidence indicators
        prompt += "\nHEADER DATA:\n"
        for field_name, value in header.items():
            field_confidence = confidence.get("header", {}).get(field_name, 1.0)
            confidence_indicator = "HIGH" if field_confidence >= self.confidence_threshold else "LOW"
            field_key = f"header.{field_name}"

            if field_key in patchable_fields:
                prompt += f"- {field_name}: {value} [LOW CONFIDENCE - {field_confidence:.2f} - NEEDS CORRECTION]\n"
            else:
                prompt += f"- {field_name}: {value} [{confidence_indicator} CONFIDENCE - {field_confidence:.2f}]\n"

        # Add line items with confidence indicators
        prompt += "\nLINE ITEMS:\n"
        for i, line in enumerate(lines[:3]):  # Limit to first 3 lines
            line_confidence = confidence.get("lines", [])[i] if i < len(confidence.get("lines", [])) else 1.0
            confidence_indicator = "HIGH" if line_confidence >= self.confidence_threshold else "LOW"

            prompt += f"Line {i+1} [{confidence_indicator} CONFIDENCE - {line_confidence:.2f}]:\n"
            for field_name, value in line.items():
                field_key = f"lines.{i}.{field_name}"
                if field_key in patchable_fields:
                    prompt += f"  - {field_name}: {value} [LOW CONFIDENCE - NEEDS CORRECTION]\n"
                else:
                    prompt += f"  - {field_name}: {value}\n"

        prompt += """
CORRECTION TASK:
Please correct the LOW CONFIDENCE fields marked above. Follow these guidelines:

1. Fix typos, formatting errors, and inconsistencies
2. Standardize formats (dates: YYYY-MM-DD, currency codes: USD/EUR/GBP)
3. Ensure mathematical consistency (quantity × unit_price = amount)
4. Infer missing values when logical from context
5. Preserve the original meaning and accuracy

BUSINESS RULES:
- Invoice numbers should retain their original format but be cleaned
- Dates should be in ISO format (YYYY-MM-DD)
- Amounts should be valid decimal numbers
- Vendor names should be properly capitalized
- Descriptions should be clear and concise

RESPONSE FORMAT:
Provide a JSON response with only the corrected fields. Do not include high-confidence fields.

Example response:
{
  "header": {
    "vendor_name": "Acme Corporation Inc.",
    "invoice_no": "INV-2024-00123",
    "invoice_date": "2024-01-15"
  },
  "lines": [
    {
      "description": "Professional Consulting Services",
      "amount": 2500.00
    }
  ]
}

Please provide your corrections:
"""

        return prompt

    async def _call_llm_with_retry(
        self,
        prompt: str,
        operation_type: str = "field_patch"
    ) -> Dict[str, Any]:
        """Call LLM API with retry logic and usage tracking."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"LLM API call attempt {attempt + 1}/{self.max_retries}")

                start_time = time.time()

                # Call LLM API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert invoice data extraction specialist. Always respond with valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                # Track usage
                usage = response.usage
                response_time = time.time() - start_time

                if usage:
                    await self._track_usage(usage, start_time, operation_type)

                response_text = response.choices[0].message.content.strip()

                # Parse JSON response
                try:
                    parsed_response = json.loads(response_text)
                    logger.debug(f"LLM response parsed successfully in {response_time:.2f}s")
                    return parsed_response
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse error: {e}")

                    # Try to extract JSON from response text
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except json.JSONDecodeError:
                            pass

                    # Fallback: try to extract key-value pairs
                    return self._extract_fallback_response(response_text)

            except Exception as e:
                last_exception = e
                logger.warning(f"LLM API call attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (self.backoff_factor ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)

        # All attempts failed
        raise ExtractionException(f"LLM service failed after {self.max_retries} attempts: {str(last_exception)}")

    def _extract_fallback_response(self, response_text: str) -> Dict[str, Any]:
        """Extract structured data from malformed LLM response."""
        logger.warning("Using fallback response extraction")

        fallback = {"header": {}, "lines": []}

        # Simple regex-based extraction
        try:
            # Extract header fields
            header_patterns = {
                "vendor_name": r"(?:vendor[_\s]*name|vendor)[:\s]*([^\n]+)",
                "invoice_number": r"(?:invoice[_\s]*(?:no|number)|invoice)[:\s]*([A-Za-z0-9\-\/]+)",
                "invoice_date": r"(?:invoice[_\s]*date|date)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
                "total": r"(?:total|amount)[:\s]*\$?([\d,]+\.\d{2})",
            }

            for field, pattern in header_patterns.items():
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    fallback["header"][field] = match.group(1).strip()

            # Extract line items (simplified)
            line_pattern = r"(?:description|item)[:\s]*([^\n]+?)\s*(?:amount|price)?[:\s]*\$?([\d,]+\.\d{2})"
            line_matches = re.findall(line_pattern, response_text, re.IGNORECASE)

            for description, amount in line_matches[:3]:  # Limit to 3 lines
                fallback["lines"].append({
                    "description": description.strip(),
                    "amount": float(amount.replace(",", ""))
                })

        except Exception as e:
            logger.warning(f"Fallback extraction failed: {e}")

        return fallback

    def _apply_validated_patches(
        self,
        original_result: Dict[str, Any],
        patch_response: Dict[str, Any],
        patchable_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply LLM patches with validation."""
        # Create a copy to avoid modifying the original
        patched_result = original_result.copy()

        # Validate and apply header patches
        if "header" in patch_response:
            patched_header = patched_result.get("header", {}).copy()
            header_patches = patch_response["header"]

            for field_name, new_value in header_patches.items():
                field_key = f"header.{field_name}"
                if field_key in patchable_fields:
                    # Validate the patch
                    if self._validate_field_patch(field_name, new_value, patchable_fields[field_key]):
                        old_value = patched_header.get(field_name)
                        patched_header[field_name] = new_value
                        logger.debug(f"Patched header field {field_name}: '{old_value}' -> '{new_value}'")
                    else:
                        logger.warning(f"Rejected invalid patch for {field_name}: {new_value}")

            patched_result["header"] = patched_header

        # Validate and apply line patches
        if "lines" in patch_response:
            patched_lines = patched_result.get("lines", []).copy()
            line_patches = patch_response["lines"]

            for i, line_patch in enumerate(line_patches):
                if i < len(patched_lines):
                    patched_line = patched_lines[i].copy()

                    for field_name, new_value in line_patch.items():
                        field_key = f"lines.{i}.{field_name}"
                        if field_key in patchable_fields:
                            # Validate the patch
                            if self._validate_field_patch(field_name, new_value, patchable_fields[field_key]):
                                old_value = patched_line.get(field_name)
                                patched_line[field_name] = new_value
                                logger.debug(f"Patched line {i+1} field {field_name}: '{old_value}' -> '{new_value}'")
                            else:
                                logger.warning(f"Rejected invalid patch for {field_key}: {new_value}")

                    patched_lines[i] = patched_line

            patched_result["lines"] = patched_lines

        return patched_result

    def _validate_field_patch(
        self,
        field_name: str,
        new_value: Any,
        field_info: Dict[str, Any]
    ) -> bool:
        """Validate a field patch."""
        try:
            # Basic validation
            if new_value is None:
                return False

            if isinstance(new_value, str) and not new_value.strip():
                return False

            # Field-specific validation
            if field_name.endswith("_date"):
                return self._validate_date_patch(new_value)
            elif field_name in ["total", "subtotal", "tax", "amount", "unit_price"]:
                return self._validate_amount_patch(new_value)
            elif field_name in ["invoice_number", "po_number"]:
                return self._validate_identifier_patch(new_value)
            elif field_name in ["vendor_name"]:
                return self._validate_name_patch(new_value)
            elif field_name in ["description"]:
                return self._validate_description_patch(new_value)

            # Generic validation
            return True

        except Exception as e:
            logger.warning(f"Field validation failed for {field_name}: {e}")
            return False

    def _validate_date_patch(self, value: Any) -> bool:
        """Validate date field patch."""
        if isinstance(value, str):
            date_patterns = [
                r"^\d{4}-\d{2}-\d{2}$",  # ISO format
                r"^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$",  # Common formats
            ]
            return any(re.match(pattern, value.strip()) for pattern in date_patterns)
        return False

    def _validate_amount_patch(self, value: Any) -> bool:
        """Validate amount field patch."""
        try:
            if isinstance(value, (int, float)):
                return value >= 0
            if isinstance(value, str):
                cleaned = value.replace("$", "").replace(",", "").strip()
                amount = float(cleaned)
                return amount >= 0
        except (ValueError, TypeError):
            pass
        return False

    def _validate_identifier_patch(self, value: Any) -> bool:
        """Validate identifier field patch."""
        if isinstance(value, str):
            # Check for reasonable identifier patterns
            return bool(re.match(r'^[A-Za-z0-9\-\/\s]+$', value.strip()))
        return False

    def _validate_name_patch(self, value: Any) -> bool:
        """Validate name field patch."""
        if isinstance(value, str):
            name = value.strip()
            # Check minimum length and reasonable characters
            return len(name) >= 2 and len(name) <= 200
        return False

    def _validate_description_patch(self, value: Any) -> bool:
        """Validate description field patch."""
        if isinstance(value, str):
            desc = value.strip()
            # Check reasonable length
            return 1 <= len(desc) <= 500
        return False

    def _update_confidence_scores(
        self,
        patched_result: Dict[str, Any],
        patchable_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update confidence scores for patched fields."""
        updated_confidence = patched_result.get("confidence", {}).copy()

        # Update header confidence
        header_confidence = updated_confidence.get("header", {}).copy()
        for field_key, field_info in patchable_fields.items():
            if field_key.startswith("header."):
                field_name = field_key.replace("header.", "")
                header_confidence[field_name] = 0.9  # High confidence for LLM patches

        # Recalculate header overall confidence
        if header_confidence:
            non_overall_confs = [v for k, v in header_confidence.items() if k != "overall"]
            if non_overall_confs:
                header_confidence["overall"] = sum(non_overall_confs) / len(non_overall_confs)

        updated_confidence["header"] = header_confidence

        # Update line confidence
        lines_confidence = updated_confidence.get("lines", []).copy()
        for field_key, field_info in patchable_fields.items():
            if field_key.startswith("lines."):
                line_index = int(field_key.split(".")[1])
                if line_index < len(lines_confidence):
                    lines_confidence[line_index] = 0.9  # High confidence for LLM patches

        updated_confidence["lines"] = lines_confidence

        # Update overall confidence
        header_overall = header_confidence.get("overall", 0.0)
        lines_overall = sum(lines_confidence) / len(lines_confidence) if lines_confidence else 0.0
        updated_confidence["overall"] = (header_overall * 0.6) + (lines_overall * 0.4)

        patched_result["confidence"] = updated_confidence
        return patched_result

    async def _track_usage(
        self,
        usage,
        start_time: float,
        operation_type: str
    ):
        """Track LLM usage and costs."""
        try:
            # Cost estimation (adjust based on actual model pricing)
            cost_per_1k_input = 0.0005
            cost_per_1k_output = 0.0015

            input_cost = (usage.prompt_tokens / 1000) * cost_per_1k_input
            output_cost = (usage.completion_tokens / 1000) * cost_per_1k_output
            total_cost = input_cost + output_cost

            usage_record = LLMUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                model=self.model,
                cost_estimate=total_cost,
                timestamp=start_time,
                operation_type=operation_type
            )

            self.usage_history.append(usage_record)
            self.total_cost += total_cost
            self.daily_cost += total_cost

            # Reset daily cost if needed
            if time.time() - self.daily_reset_time > 86400:  # 24 hours
                self.daily_cost = 0.0
                self.daily_reset_time = time.time()

            logger.info(f"LLM usage tracked - Tokens: {usage.total_tokens}, Cost: ${total_cost:.4f}")

            # Keep only last 100 records
            if len(self.usage_history) > 100:
                self.usage_history = self.usage_history[-100:]

        except Exception as e:
            logger.warning(f"Failed to track usage: {e}")

    async def _track_patch_performance(
        self,
        patchable_fields: Dict[str, Dict[str, Any]],
        patch_response: Dict[str, Any],
        processing_time: int,
        cost_estimate: float
    ):
        """Track patching performance for optimization."""
        try:
            performance_data = {
                "fields_attempted": len(patchable_fields),
                "fields_patched": len(patch_response.get("header", {})) + sum(1 for line in patch_response.get("lines", [])),
                "processing_time_ms": processing_time,
                "cost_estimate": cost_estimate,
                "success_rate": 1.0,  # Simplified
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.debug(f"Patch performance: {performance_data}")

        except Exception as e:
            logger.warning(f"Failed to track patch performance: {e}")

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        if not self.usage_history:
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "daily_cost": 0.0,
                "average_cost_per_request": 0.0
            }

        total_tokens = sum(u.total_tokens for u in self.usage_history)

        # Stats by operation type
        operation_stats = {}
        for usage in self.usage_history:
            op_type = usage.operation_type
            if op_type not in operation_stats:
                operation_stats[op_type] = {"count": 0, "tokens": 0, "cost": 0.0}
            operation_stats[op_type]["count"] += 1
            operation_stats[op_type]["tokens"] += usage.total_tokens
            operation_stats[op_type]["cost"] += usage.cost_estimate

        return {
            "total_requests": len(self.usage_history),
            "total_tokens": total_tokens,
            "total_cost": self.total_cost,
            "daily_cost": self.daily_cost,
            "average_cost_per_request": self.total_cost / len(self.usage_history),
            "average_tokens_per_request": total_tokens / len(self.usage_history),
            "model": self.model,
            "provider": self.provider,
            "operation_breakdown": operation_stats,
            "cost_per_1k_tokens": self.total_cost / (total_tokens / 1000) if total_tokens > 0 else 0
        }

    async def test_connection(self) -> Dict[str, Any]:
        """Test LLM service connection."""
        if not self.client:
            return {
                "status": "error",
                "message": "LLM client not initialized",
                "provider": self.provider,
                "model": self.model
            }

        try:
            start_time = time.time()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": "Respond with 'OK' to confirm connection."}
                ],
                max_tokens=10,
                temperature=0.0,
            )

            response_time = time.time() - start_time

            return {
                "status": "success",
                "message": "LLM connection successful",
                "provider": self.provider,
                "model": self.model,
                "response_time": f"{response_time:.2f}s",
                "test_response": response.choices[0].message.content.strip(),
                "usage_stats": self.get_usage_stats()
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"LLM connection failed: {str(e)}",
                "provider": self.provider,
                "model": self.model
            }