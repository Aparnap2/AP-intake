"""
LLM service for low-confidence field patching and intelligent data extraction.
Enhanced with OpenRouter integration and usage tracking.
"""

import logging
import time
from typing import Any, Dict, Optional, List
import json
import asyncio
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import ExtractionException

logger = logging.getLogger(__name__)


@dataclass
class LLMUsage:
    """Track LLM usage for cost monitoring."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    cost_estimate: float
    timestamp: float


class LLMService:
    """Service for using LLM to patch low-confidence extraction results with OpenRouter support."""

    def __init__(self):
        """Initialize the LLM service with OpenRouter support."""
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self.base_url = settings.OPENROUTER_BASE_URL
        self.provider = settings.LLM_PROVIDER
        self.app_name = settings.OPENROUTER_APP_NAME
        self.app_url = settings.OPENROUTER_APP_URL

        # Usage tracking
        self.usage_history: List[LLMUsage] = []
        self.total_cost: float = 0.0

        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.backoff_factor = 2.0

        # Initialize OpenAI-compatible client
        self.client = None
        if self.api_key and self.provider == 'openrouter':
            try:
                from openai import OpenAI

                # Set up default headers for OpenRouter
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
                logger.info(f"LLM service initialized with OpenRouter client using model: {self.model}")
                logger.info(f"OpenRouter configuration - Base URL: {self.base_url}, App: {self.app_name}")

            except ImportError:
                logger.error("OpenAI package not installed. Please install with: pip install openai>=1.0.0")
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter client: {e}")
        else:
            logger.warning(f"OpenRouter API key not configured or provider not set to 'openrouter'. LLM service will be disabled")

    async def patch_low_confidence_fields(
        self, extraction_result: Dict[str, Any], confidence_score: float
    ) -> Dict[str, Any]:
        """Patch low-confidence fields using LLM with retry logic."""
        logger.info(f"Patching low-confidence fields (confidence: {confidence_score:.2f})")

        if not self.client:
            logger.warning("LLM client not available, returning original extraction")
            return extraction_result

        try:
            # Identify low-confidence fields
            low_confidence_fields = self._identify_low_confidence_fields(extraction_result)
            if not low_confidence_fields:
                logger.info("No low-confidence fields to patch")
                return extraction_result

            # Generate prompt for LLM
            prompt = self._generate_patch_prompt(extraction_result, low_confidence_fields)

            # Call LLM with retry logic
            response = await self._call_llm_with_retry(prompt)

            # Parse and apply patches
            patched_result = self._apply_patches(extraction_result, response, low_confidence_fields)

            # Update confidence scores
            patched_result["confidence"] = self._update_confidence(
                extraction_result.get("confidence", {}),
                low_confidence_fields,
                0.9  # High confidence for LLM-patched fields
            )

            # Update overall confidence
            patched_result["overall_confidence"] = self._calculate_overall_confidence(patched_result["confidence"])

            logger.info(f"Successfully patched {len(low_confidence_fields)} fields")
            return patched_result

        except Exception as e:
            logger.error(f"Failed to patch low-confidence fields: {e}")
            # Return original extraction if patching fails
            return extraction_result

    def _identify_low_confidence_fields(self, extraction_result: Dict[str, Any]) -> Dict[str, float]:
        """Identify fields with low confidence scores."""
        low_confidence = {}
        confidence_data = extraction_result.get("confidence", {})
        threshold = settings.DOCLING_CONFIDENCE_THRESHOLD

        # Check header fields
        header_confidence = confidence_data.get("header", {})
        for field, confidence in header_confidence.items():
            if field != "overall" and confidence < threshold:
                low_confidence[f"header.{field}"] = confidence

        # Check line items
        lines_confidence = confidence_data.get("lines", [])
        for i, line_confidence in enumerate(lines_confidence):
            if line_confidence < threshold:
                low_confidence[f"lines.{i}"] = line_confidence

        return low_confidence

    def _generate_patch_prompt(self, extraction_result: Dict[str, Any], low_confidence_fields: Dict[str, float]) -> str:
        """Generate prompt for LLM to patch fields."""
        header = extraction_result.get("header", {})
        lines = extraction_result.get("lines", [])

        prompt = """You are an expert invoice data extraction specialist. I need you to review and improve the extracted invoice data below.

Here's the current extraction result:
"""

        # Add header information
        prompt += "\nHEADER DATA:\n"
        for field, value in header.items():
            field_key = f"header.{field}"
            if field_key in low_confidence_fields:
                prompt += f"- {field}: {value} [LOW CONFIDENCE - needs correction]\n"
            else:
                prompt += f"- {field}: {value}\n"

        # Add line items
        prompt += "\nLINE ITEMS:\n"
        for i, line in enumerate(lines):
            line_key = f"lines.{i}"
            prompt += f"Line {i+1}:\n"
            for field, value in line.items():
                if line_key in low_confidence_fields:
                    prompt += f"  - {field}: {value} [LOW CONFIDENCE - needs correction]\n"
                else:
                    prompt += f"  - {field}: {value}\n"

        prompt += """

TASK: Please correct the low-confidence fields marked above. Use your expertise to:

1. Correct any typos or formatting errors
2. Fill in missing values if you can infer them from context
3. Standardize formats (dates, currency codes, etc.)
4. Ensure mathematical consistency

RESPONSE FORMAT: Provide a JSON response with the corrected values. Only include fields that needed correction.

Example response:
{
  "header": {
    "vendor_name": "Acme Corporation Inc.",
    "invoice_no": "INV-2024-00123"
  },
  "lines": [
    {
      "description": "Office Supplies",
      "amount": 125.50
    }
  ]
}

Please provide your corrections below:
"""

        return prompt

    async def _call_llm_with_retry(self, prompt: str) -> Dict[str, Any]:
        """Call LLM API with retry logic and usage tracking."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"LLM API call attempt {attempt + 1}/{self.max_retries}")

                # Track start time
                start_time = time.time()

                # Call LLM API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert invoice data extraction specialist."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                # Track usage
                usage = response.usage
                if usage:
                    await self._track_usage(usage, start_time)

                response_text = response.choices[0].message.content.strip()

                # Parse JSON response
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    # Try to extract JSON from response text
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    else:
                        raise ValueError("Could not parse JSON from LLM response")

            except Exception as e:
                last_exception = e
                logger.warning(f"LLM API call attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (self.backoff_factor ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} LLM API attempts failed")

        # All attempts failed
        raise ExtractionException(f"LLM service failed after {self.max_retries} attempts: {str(last_exception)}")

    async def _track_usage(self, usage, start_time: float):
        """Track LLM usage and estimate costs."""
        try:
            # Simple cost estimation (adjust based on actual OpenRouter pricing)
            # This is a rough estimate - update with actual model pricing
            cost_per_1k_input = 0.001  # Adjust based on actual pricing
            cost_per_1k_output = 0.002  # Adjust based on actual pricing

            input_cost = (usage.prompt_tokens / 1000) * cost_per_1k_input
            output_cost = (usage.completion_tokens / 1000) * cost_per_1k_output
            total_cost = input_cost + output_cost

            usage_record = LLMUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                model=self.model,
                cost_estimate=total_cost,
                timestamp=start_time
            )

            self.usage_history.append(usage_record)
            self.total_cost += total_cost

            logger.info(f"LLM usage tracked - Tokens: {usage.total_tokens}, Estimated cost: ${total_cost:.4f}")

            # Keep only last 100 usage records
            if len(self.usage_history) > 100:
                self.usage_history = self.usage_history[-100:]

        except Exception as e:
            logger.warning(f"Failed to track usage: {e}")

    def _apply_patches(
        self, original_result: Dict[str, Any], patches: Dict[str, Any], low_confidence_fields: Dict[str, float]
    ) -> Dict[str, Any]:
        """Apply LLM patches to the original extraction result."""
        # Create a copy to avoid modifying the original
        patched_result = original_result.copy()

        # Apply header patches
        if "header" in patches:
            patched_header = patched_result.get("header", {}).copy()
            for field, value in patches["header"].items():
                field_key = f"header.{field}"
                if field_key in low_confidence_fields:
                    patched_header[field] = value
                    logger.debug(f"Patched header field {field}: {value}")
            patched_result["header"] = patched_header

        # Apply line patches
        if "lines" in patches:
            patched_lines = patched_result.get("lines", []).copy()
            for i, line_patch in enumerate(patches["lines"]):
                if i < len(patched_lines):
                    patched_line = patched_lines[i].copy()
                    for field, value in line_patch.items():
                        line_key = f"lines.{i}"
                        if line_key in low_confidence_fields:
                            patched_line[field] = value
                            logger.debug(f"Patched line {i+1} field {field}: {value}")
                    patched_lines[i] = patched_line
            patched_result["lines"] = patched_lines

        return patched_result

    def _update_confidence(
        self, original_confidence: Dict[str, Any], patched_fields: Dict[str, float], new_confidence: float
    ) -> Dict[str, Any]:
        """Update confidence scores for patched fields."""
        updated_confidence = original_confidence.copy()

        # Update header confidence
        header_confidence = updated_confidence.get("header", {}).copy()
        for field_key, original_conf in patched_fields.items():
            if field_key.startswith("header."):
                field_name = field_key.replace("header.", "")
                header_confidence[field_name] = new_confidence

        # Recalculate header overall confidence
        if header_confidence:
            non_overall_confs = [v for k, v in header_confidence.items() if k != "overall"]
            if non_overall_confs:
                header_confidence["overall"] = sum(non_overall_confs) / len(non_overall_confs)

        updated_confidence["header"] = header_confidence

        # Update line confidence
        lines_confidence = updated_confidence.get("lines", []).copy()
        for field_key, original_conf in patched_fields.items():
            if field_key.startswith("lines."):
                line_index = int(field_key.replace("lines.", ""))
                if line_index < len(lines_confidence):
                    lines_confidence[line_index] = new_confidence

        updated_confidence["lines"] = lines_confidence

        return updated_confidence

    def _calculate_overall_confidence(self, confidence_data: Dict[str, Any]) -> float:
        """Calculate overall confidence score."""
        header_overall = confidence_data.get("header", {}).get("overall", 0.0)
        lines_confidence = confidence_data.get("lines", [])
        lines_overall = sum(lines_confidence) / len(lines_confidence) if lines_confidence else 0.0

        # Weight header more heavily than lines
        overall = (header_overall * 0.6) + (lines_overall * 0.4)
        return round(overall, 3)

    async def extract_invoice_context(self, full_text: str) -> Dict[str, Any]:
        """Extract contextual information from full document text."""
        if not self.client:
            return {}

        try:
            prompt = f"""
Analyze this invoice text and provide key contextual information:

{full_text[:2000]}  # Limit to first 2000 chars to avoid token limits

Provide a JSON response with:
1. Document type (invoice, receipt, etc.)
2. Business domain (retail, services, etc.)
3. Key entities (vendor, customer, dates)
4. Document structure (tables, sections)
"""

            response = await self._call_llm_with_retry(prompt)
            return response

        except Exception as e:
            logger.error(f"Failed to extract invoice context: {e}")
            return {}

    async def test_connection(self) -> Dict[str, Any]:
        """Test LLM connection and return status information."""
        if not self.client:
            return {
                "status": "error",
                "message": "LLM client not initialized",
                "provider": self.provider,
                "model": self.model
            }

        try:
            start_time = time.time()

            # Simple test call
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
                "base_url": self.base_url,
                "response_time": f"{response_time:.2f}s",
                "test_response": response.choices[0].message.content.strip(),
                "total_usage_records": len(self.usage_history),
                "total_cost": f"${self.total_cost:.4f}"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"LLM connection failed: {str(e)}",
                "provider": self.provider,
                "model": self.model,
                "base_url": self.base_url
            }

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics and cost information."""
        if not self.usage_history:
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "average_cost_per_request": 0.0
            }

        total_tokens = sum(u.total_tokens for u in self.usage_history)

        return {
            "total_requests": len(self.usage_history),
            "total_tokens": total_tokens,
            "total_cost": self.total_cost,
            "average_cost_per_request": self.total_cost / len(self.usage_history),
            "average_tokens_per_request": total_tokens / len(self.usage_history),
            "model": self.model,
            "provider": self.provider
        }