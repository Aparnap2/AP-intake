"""
Email ingestion service for unified email processing across providers.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import EmailIngestionException
from app.services.gmail_service import GmailService, GmailCredentials
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class EmailProvider:
    """Email provider types."""
    GMAIL = "gmail"
    OUTLOOK = "outlook"


class EmailAttachment(BaseModel):
    """Email attachment model."""
    filename: str
    content: bytes
    mime_type: str
    size: int
    content_hash: str
    is_pdf: bool


class EmailIngestionRecord(BaseModel):
    """Email ingestion record model."""
    email_id: str
    provider: str
    message_id: str
    thread_id: Optional[str] = None
    subject: str
    from_email: str
    to_emails: List[str]
    date: datetime
    body: str
    attachments: List[EmailAttachment]
    processed_at: datetime
    status: str = "ingested"
    security_flags: List[str] = []


class EmailIngestionService:
    """Unified email ingestion service."""

    def __init__(self):
        """Initialize email ingestion service."""
        self.storage_service = StorageService()
        self.gmail_service = GmailService()

        # Security patterns for email validation
        self.malicious_patterns = [
            r'(?i)(urgent|immediate action required|suspended|account locked)',
            r'(?i)(click here|verify now|update payment|confirm account)',
            r'(?i)(you have won|congratulations|claim now|free money)',
            r'(?i)(bitcoin|cryptocurrency|investment opportunity)',
            r'[<>"\'&]',  # HTML/JS injection patterns
        ]

        # Trusted sender patterns
        self.trusted_domains = [
            r'.*\.quickbooks\.com$',
            r'.*\.xero\.com$',
            r'.*\.freshbooks\.com$',
            r'.*\.sage\.com$',
            r'.*\.intuit\.com$',
        ]

    async def ingest_from_gmail(
        self,
        credentials: GmailCredentials,
        days_back: int = 7,
        max_emails: int = 50,
        auto_process: bool = True
    ) -> List[EmailIngestionRecord]:
        """Ingest emails from Gmail."""
        try:
            # Build Gmail service
            await self.gmail_service.build_service(credentials)

            # Get recent emails with PDF attachments
            invoice_messages = await self.gmail_service.get_recent_invoices(
                days_back=days_back,
                max_results=max_emails
            )

            ingestion_records = []

            for message_data in invoice_messages:
                try:
                    record = await self._process_gmail_message(message_data)
                    if record:
                        ingestion_records.append(record)

                        # Auto-process if enabled
                        if auto_process:
                            await self._auto_process_email(record)

                        # Mark as processed in Gmail
                        await self.gmail_service.mark_message_processed(message_data['message_id'])

                except Exception as e:
                    logger.error(f"Error processing message {message_data.get('message_id')}: {e}")
                    continue

            logger.info(f"Successfully ingested {len(ingestion_records)} emails from Gmail")
            return ingestion_records

        except Exception as e:
            logger.error(f"Failed to ingest from Gmail: {e}")
            raise EmailIngestionException(f"Gmail ingestion failed: {str(e)}")

    async def _process_gmail_message(self, message_data: Dict[str, Any]) -> Optional[EmailIngestionRecord]:
        """Process a single Gmail message."""
        try:
            message_id = message_data['message_id']

            # Get full message details
            full_message = await self.gmail_service.get_message(message_id)

            # Security validation
            security_flags = await self._validate_email_security(full_message)
            if self._is_email_blocked(security_flags):
                logger.warning(f"Email blocked due to security concerns: {full_message.subject}")
                return None

            # Process attachments
            processed_attachments = []
            for attachment_data in full_message.attachments:
                try:
                    attachment = await self._process_attachment(
                        message_id,
                        attachment_data,
                        full_message.subject
                    )
                    if attachment:
                        processed_attachments.append(attachment)
                except Exception as e:
                    logger.error(f"Error processing attachment {attachment_data.get('filename')}: {e}")
                    continue

            if not processed_attachments:
                logger.debug(f"No valid PDF attachments found in message: {full_message.subject}")
                return None

            # Check for duplicates
            email_hash = self._generate_email_hash(full_message)
            if await self._is_duplicate_email(email_hash):
                logger.debug(f"Duplicate email detected: {full_message.subject}")
                return None

            # Create ingestion record
            record = EmailIngestionRecord(
                email_id=email_hash,
                provider=EmailProvider.GMAIL,
                message_id=full_message.id,
                thread_id=full_message.thread_id,
                subject=full_message.subject,
                from_email=full_message.from_email,
                to_emails=full_message.to_emails,
                date=full_message.date,
                body=full_message.body,
                attachments=processed_attachments,
                processed_at=datetime.utcnow(),
                security_flags=security_flags
            )

            logger.info(f"Processed email: {full_message.subject} with {len(processed_attachments)} attachments")
            return record

        except Exception as e:
            logger.error(f"Error processing Gmail message: {e}")
            return None

    async def _process_attachment(
        self,
        message_id: str,
        attachment_data: Dict[str, Any],
        email_subject: str
    ) -> Optional[EmailAttachment]:
        """Process a single email attachment."""
        try:
            filename = attachment_data['filename']
            attachment_id = attachment_data['attachment_id']

            # Download attachment content
            content = await self.gmail_service.download_attachment(message_id, attachment_id)

            # Validate attachment
            if not await self._validate_attachment(content, filename):
                logger.warning(f"Attachment validation failed: {filename}")
                return None

            # Generate content hash
            content_hash = hashlib.sha256(content).hexdigest()

            # Check for duplicate files
            if await self._is_duplicate_file(content_hash):
                logger.debug(f"Duplicate file detected: {filename}")
                return None

            # Store attachment
            storage_info = await self.storage_service.store_file(
                file_content=content,
                filename=filename,
                content_type=attachment_data['mime_type'],
                organization_path="email_ingestion",
                vendor_name=self._extract_vendor_name(email_subject, filename)
            )

            return EmailAttachment(
                filename=filename,
                content=content,
                mime_type=attachment_data['mime_type'],
                size=attachment_data['size'],
                content_hash=content_hash,
                is_pdf=True
            )

        except Exception as e:
            logger.error(f"Error processing attachment: {e}")
            return None

    async def _validate_email_security(self, message) -> List[str]:
        """Validate email for security concerns."""
        security_flags = []

        # Check for malicious patterns in subject and body
        text_to_check = f"{message.subject} {message.body}"

        for pattern in self.malicious_patterns:
            if re.search(pattern, text_to_check):
                security_flags.append(f"malicious_pattern: {pattern}")

        # Check sender domain
        sender_domain = message.from_email.split('@')[-1] if '@' in message.from_email else ''

        # Check if sender is from trusted domain
        is_trusted = any(re.match(pattern, sender_domain) for pattern in self.trusted_domains)
        if not is_trusted:
            security_flags.append("untrusted_sender")

        # Check for suspicious URLs in body
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, message.body)
        if len(urls) > 5:  # Too many URLs
            security_flags.append("excessive_urls")

        # Check for attachment count
        if len(message.attachments) > 10:
            security_flags.append("excessive_attachments")

        return security_flags

    def _is_email_blocked(self, security_flags: List[str]) -> bool:
        """Determine if email should be blocked based on security flags."""
        critical_flags = [
            'malicious_pattern',
            'excessive_urls',
            'excessive_attachments'
        ]

        return any(flag.startswith(tuple(critical_flags)) for flag in security_flags)

    async def _validate_attachment(self, content: bytes, filename: str) -> bool:
        """Validate attachment content."""
        try:
            # Check file size
            if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                logger.warning(f"Attachment too large: {filename}")
                return False

            # Validate PDF structure
            if filename.lower().endswith('.pdf'):
                if not content.startswith(b'%PDF'):
                    logger.warning(f"Invalid PDF file: {filename}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Attachment validation error: {e}")
            return False

    def _generate_email_hash(self, message) -> str:
        """Generate unique hash for email deduplication."""
        hash_data = f"{message.from_email}{message.subject}{message.date}"
        return hashlib.sha256(hash_data.encode()).hexdigest()

    async def _is_duplicate_email(self, email_hash: str) -> bool:
        """Check if email has already been processed."""
        # This would typically check a database
        # For now, return False (no duplicates)
        return False

    async def _is_duplicate_file(self, content_hash: str) -> bool:
        """Check if file has already been processed."""
        # This would typically check a database or storage
        # For now, return False (no duplicates)
        return False

    def _extract_vendor_name(self, email_subject: str, filename: str) -> Optional[str]:
        """Extract vendor name from email subject or filename."""
        # Simple vendor extraction - could be enhanced with ML
        vendor_patterns = [
            r'from\s+([A-Za-z0-9\s&]+)',
            r'([A-Za-z0-9\s&]+)\s+invoice',
            r'([A-Za-z0-9\s&]+)\s+bill',
        ]

        text_to_search = f"{email_subject} {filename}"

        for pattern in vendor_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                vendor = match.group(1).strip()
                if len(vendor) > 2 and len(vendor) < 50:  # Reasonable length
                    return vendor

        return None

    async def _auto_process_email(self, record: EmailIngestionRecord) -> None:
        """Automatically process email attachments through invoice workflow."""
        try:
            from app.workflows.invoice_processor import InvoiceProcessor

            processor = InvoiceProcessor()

            for attachment in record.attachments:
                if attachment.is_pdf:
                    # Generate invoice ID
                    invoice_id = f"email_{record.email_id}_{attachment.content_hash[:8]}"

                    # Process through invoice workflow
                    await processor.process_invoice(
                        invoice_id=invoice_id,
                        file_path=attachment.filename,  # Would need to map to storage path
                        file_hash=attachment.content_hash,
                        vendor_name=self._extract_vendor_name(record.subject, attachment.filename)
                    )

                    logger.info(f"Processed invoice {invoice_id} from email {record.email_id}")

        except Exception as e:
            logger.error(f"Auto-processing failed for email {record.email_id}: {e}")
            # Don't raise - continue with other attachments

    async def get_ingestion_statistics(
        self,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get email ingestion statistics."""
        # This would typically query a database
        return {
            "total_emails_processed": 0,
            "total_attachments_processed": 0,
            "pdf_attachments": 0,
            "security_blocked": 0,
            "duplicates_filtered": 0,
            "average_processing_time_ms": 0,
            "period_days": days_back,
            "generated_at": datetime.utcnow().isoformat()
        }

    async def create_email_filters(self) -> List[str]:
        """Create email search filters for common invoice patterns."""
        filters = [
            # Basic invoice patterns
            "has:attachment filename:pdf (invoice OR bill OR receipt)",

            # Vendor-specific patterns
            "has:attachment filename:pdf (quickbooks OR xero OR freshbooks)",

            # Time-based filters
            "newer:7d has:attachment filename:pdf invoice",

            # From trusted domains
            f"from:({'|'.join(['*.intuit.com', '*.xero.com'])}) has:attachment filename:pdf",
        ]

        return filters

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on email ingestion service."""
        return {
            "status": "healthy",
            "gmail_service_configured": bool(settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET),
            "storage_service_available": True,  # Could add actual check
            "security_validation_enabled": True,
            "timestamp": datetime.utcnow().isoformat()
        }