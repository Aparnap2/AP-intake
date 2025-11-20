"""
Enhanced export service for generating CSV, JSON, and other format exports from invoice data.
"""

import asyncio
import csv
import gzip
import io
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, BinaryIO, TextIO
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import uuid

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.core.exceptions import ExportException, ValidationException
from app.models.invoice import Invoice, InvoiceExtraction, StagedExport
from app.models.export_models import (
    ExportJob, ExportTemplate, ExportAuditLog, ExportMetrics,
    ExportFormat, ExportStatus, ExportDestination
)
from app.schemas.export_schemas import (
    ExportRequest, ExportResponse, ExportProgress, ExportAuditLog as AuditLogSchema,
    ExportMetrics as MetricsSchema, ExportFieldMapping, ExportFilter
)
from app.services.storage_service import StorageService
from app.services.validation_service import ValidationService

logger = logging.getLogger(__name__)


@dataclass
class ExportContext:
    """Context for export operations."""
    job_id: str
    template: ExportTemplate
    filters: Optional[Dict[str, Any]] = None
    batch_size: int = 1000
    destination: ExportDestination = ExportDestination.DOWNLOAD
    destination_config: Optional[Dict[str, Any]] = None


class ExportFieldTransformer:
    """Service for transforming export fields according to mappings."""

    def __init__(self, field_mappings: List[ExportFieldMapping]):
        """Initialize with field mappings."""
        self.field_mappings = {m.source_field: m for m in field_mappings}
        self.transform_functions = {
            'uppercase': lambda x: str(x).upper() if x else '',
            'lowercase': lambda x: str(x).lower() if x else '',
            'title_case': lambda x: str(x).title() if x else '',
            'currency_format': lambda x: f"${float(x):.2f}" if x else '$0.00',
            'percentage': lambda x: f"{float(x):.1f}%" if x else '0.0%',
            'date_format': self._format_date,
            'phone_format': self._format_phone,
        }

    def transform_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a single record according to field mappings."""
        transformed = {}

        for source_field, mapping in self.field_mappings.items():
            value = self._get_nested_value(record, source_field)

            if value is None and mapping.default_value is not None:
                value = mapping.default_value

            # Apply validation
            if mapping.required and value is None:
                raise ValidationException(f"Required field '{mapping.target_field}' is missing")

            # Apply transformation
            if mapping.transform_function and value is not None:
                transform_func = self.transform_functions.get(mapping.transform_function)
                if transform_func:
                    try:
                        value = transform_func(value, mapping.format_string)
                    except Exception as e:
                        logger.warning(f"Transform failed for field {source_field}: {e}")

            # Apply formatting
            if mapping.format_string and value is not None:
                try:
                    if mapping.field_type == "date":
                        value = datetime.strptime(value, mapping.format_string).isoformat()
                    elif mapping.field_type in ["number", "decimal"]:
                        value = float(value)
                except Exception as e:
                    logger.warning(f"Format failed for field {source_field}: {e}")

            transformed[mapping.target_field] = value

        return transformed

    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split('.')
        current = obj

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _format_date(self, value: Any, format_str: Optional[str] = None) -> str:
        """Format date value with standardized YYYY-MM-DD output for Invoicify compliance."""
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    dt = datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    try:
                        # Try other common date formats
                        for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d-%m-%Y', '%Y/%m/%d']:
                            try:
                                dt = datetime.strptime(value, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            return str(value)  # Return as-is if no format matches
                    except:
                        return str(value)
        elif isinstance(value, datetime):
            dt = value
        else:
            return str(value)

        # Default to YYYY-MM-DD format for Invoicify compliance
        if format_str:
            return dt.strftime(format_str)
        return dt.strftime('%Y-%m-%d')

    def _format_phone(self, value: Any, format_str: Optional[str] = None) -> str:
        """Format phone number."""
        if not value:
            return ""

        # Remove all non-digit characters
        digits = ''.join(c for c in str(value) if c.isdigit())

        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

        return str(value)


class ExportValidator:
    """Service for validating export data."""

    def __init__(self, validation_rules: List[Dict[str, Any]]):
        """Initialize with validation rules."""
        self.validation_rules = validation_rules

    def validate_record(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate a single record and return list of errors."""
        errors = []

        for rule in self.validation_rules:
            try:
                field_value = self._get_nested_value(record, rule['field_path'])

                if not self._apply_rule(field_value, rule):
                    errors.append({
                        'field': rule['field_path'],
                        'rule': rule['rule_type'],
                        'message': rule['error_message'],
                        'severity': rule.get('severity', 'error'),
                        'value': field_value
                    })
            except Exception as e:
                errors.append({
                    'field': rule['field_path'],
                    'rule': rule['rule_type'],
                    'message': f"Validation error: {str(e)}",
                    'severity': 'error'
                })

        return errors

    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split('.')
        current = obj

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _apply_rule(self, value: Any, rule: Dict[str, Any]) -> bool:
        """Apply validation rule to value."""
        rule_type = rule['rule_type']
        rule_config = rule['rule_config']

        if rule_type == 'required':
            return value is not None and value != ''
        elif rule_type == 'min_length':
            return len(str(value)) >= rule_config['min_length']
        elif rule_type == 'max_length':
            return len(str(value)) <= rule_config['max_length']
        elif rule_type == 'pattern':
            import re
            pattern = rule_config['pattern']
            return bool(re.match(pattern, str(value)))
        elif rule_type == 'in_list':
            return value in rule_config['allowed_values']
        elif rule_type == 'numeric_range':
            try:
                num_value = float(value)
                return rule_config['min'] <= num_value <= rule_config['max']
            except (ValueError, TypeError):
                return False
        elif rule_type == 'date_range':
            try:
                if isinstance(value, str):
                    date_value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                elif isinstance(value, datetime):
                    date_value = value
                else:
                    return False

                min_date = datetime.fromisoformat(rule_config['min_date'].replace('Z', '+00:00'))
                max_date = datetime.fromisoformat(rule_config['max_date'].replace('Z', '+00:00'))

                return min_date <= date_value <= max_date
            except (ValueError, TypeError):
                return False

        return True


class ExportService:
    """Enhanced service for exporting invoice data in various formats."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize the export service."""
        self.db = db
        self.export_path = settings.EXPORT_PATH
        self.storage_service = StorageService()
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def create_export_job(self, request: ExportRequest, user_id: Optional[str] = None) -> ExportResponse:
        """Create a new export job."""
        logger.info(f"Creating export job: {request.export_config.template_id}")

        try:
            # Get template
            template = self.db.query(ExportTemplate).filter(
                ExportTemplate.id == request.export_config.template_id
            ).first()

            if not template:
                raise ExportException(f"Export template not found: {request.export_config.template_id}")

            if not template.is_active:
                raise ExportException(f"Export template is not active: {template.name}")

            # Create export job
            export_job = ExportJob(
                name=f"Export {template.name}",
                description=request.export_config.destination_config.get('description', ''),
                template_id=template.id,
                format=template.format,
                destination=request.export_config.destination,
                destination_config=request.export_config.destination_config,
                filters=request.filters,
                invoice_ids=[str(id) for id in request.invoice_ids] if request.invoice_ids else None,
                priority=request.priority,
                batch_size=request.export_config.batch_size,
                notify_on_completion=request.export_config.notify_on_completion,
                notification_config=request.export_config.notification_config,
                created_by=user_id,
                user_id=user_id,
            )

            self.db.add(export_job)
            self.db.commit()
            self.db.refresh(export_job)

            # Log creation
            await self._log_export_event(
                export_job.id,
                "job_created",
                {
                    "template_id": str(template.id),
                    "format": template.format,
                    "destination": request.export_config.destination.value,
                    "invoice_count": len(request.invoice_ids) if request.invoice_ids else None
                },
                user_id
            )

            # Schedule export
            if request.scheduled_at:
                export_job.status = ExportStatus.PENDING
                self.db.commit()
            else:
                # Start export immediately
                asyncio.create_task(self._execute_export_job(export_job.id))

            return ExportResponse(
                export_id=export_job.id,
                status=export_job.status,
                message="Export job created successfully",
                estimated_completion=request.scheduled_at
            )

        except Exception as e:
            logger.error(f"Failed to create export job: {e}")
            raise ExportException(f"Failed to create export job: {str(e)}")

    async def _execute_export_job(self, job_id: str) -> None:
        """Execute an export job."""
        logger.info(f"Starting export job execution: {job_id}")

        try:
            # Get job
            job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
            if not job:
                logger.error(f"Export job not found: {job_id}")
                return

            # Get template
            template = self.db.query(ExportTemplate).filter(ExportTemplate.id == job.template_id).first()
            if not template:
                await self._fail_export_job(job_id, "Template not found")
                return

            # Update job status
            job.status = ExportStatus.PREPARING
            job.started_at = datetime.now(timezone.utc)
            self.db.commit()

            # Get invoices to export
            invoices = await self._get_invoices_for_export(job)
            job.total_records = len(invoices)
            self.db.commit()

            if not invoices:
                await self._complete_export_job(job_id, "No invoices found matching criteria")
                return

            # Create export context
            context = ExportContext(
                job_id=job_id,
                template=template,
                filters=job.filters,
                batch_size=job.batch_size,
                destination=job.destination,
                destination_config=job.destination_config
            )

            # Execute export based on format
            if template.format == ExportFormat.CSV:
                file_path, file_size = await self._export_to_csv_enhanced(invoices, context)
            elif template.format == ExportFormat.JSON:
                file_path, file_size = await self._export_to_json_enhanced(invoices, context)
            else:
                raise ExportException(f"Unsupported export format: {template.format}")

            # Handle destination
            final_path = await self._handle_export_destination(file_path, job.destination, job.destination_config)

            # Update job with results
            job.status = ExportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.file_path = final_path
            job.file_size = file_size
            job.record_count = len(invoices)
            self.db.commit()

            # Create metrics
            await self._create_export_metrics(job_id, len(invoices), file_size)

            # Send notification if configured
            if job.notify_on_completion:
                await self._send_completion_notification(job)

            await self._log_export_event(job_id, "job_completed", {
                "record_count": len(invoices),
                "file_size": file_size,
                "file_path": final_path
            })

            logger.info(f"Export job completed successfully: {job_id}")

        except Exception as e:
            logger.error(f"Export job failed: {job_id}, error: {e}")
            await self._fail_export_job(job_id, str(e))

    async def _get_invoices_for_export(self, job: ExportJob) -> List[Dict[str, Any]]:
        """Get invoices that match the export criteria."""
        query = self.db.query(Invoice).join(InvoiceExtraction)

        # Apply specific invoice IDs if provided
        if job.invoice_ids:
            invoice_uuids = [uuid.UUID(id) for id in job.invoice_ids]
            query = query.filter(Invoice.id.in_(invoice_uuids))

        # Apply filters
        if job.filters:
            filters = job.filters

            if 'vendor_ids' in filters:
                vendor_uuids = [uuid.UUID(id) for id in filters['vendor_ids']]
                query = query.filter(Invoice.vendor_id.in_(vendor_uuids))

            if 'status' in filters:
                query = query.filter(Invoice.status.in_(filters['status']))

            if 'date_from' in filters:
                query = query.filter(Invoice.created_at >= filters['date_from'])

            if 'date_to' in filters:
                query = query.filter(Invoice.created_at <= filters['date_to'])

            if 'has_exceptions' in filters:
                from app.models.invoice import Exception
                if filters['has_exceptions']:
                    query = query.join(Exception, Invoice.id == Exception.invoice_id)
                else:
                    query = query.outerjoin(Exception, Invoice.id == Exception.invoice_id).filter(Exception.id.is_(None))

        # Get only invoices with successful extractions
        invoices = query.all()

        # Build invoice data
        invoice_data = []
        for invoice in invoices:
            # Get latest extraction
            extraction = self.db.query(InvoiceExtraction).filter(
                InvoiceExtraction.invoice_id == invoice.id
            ).order_by(InvoiceExtraction.created_at.desc()).first()

            if extraction:
                data = {
                    "id": str(invoice.id),
                    "header": extraction.header_json,
                    "lines": extraction.lines_json,
                    "metadata": {
                        "invoice_id": str(invoice.id),
                        "vendor_id": str(invoice.vendor_id),
                        "processed_at": invoice.updated_at.isoformat(),
                        "confidence": extraction.confidence_json,
                        "status": invoice.status.value,
                        "created_at": invoice.created_at.isoformat(),
                    }
                }
                invoice_data.append(data)

        return invoice_data

    async def _export_to_csv_enhanced(self, invoices: List[Dict[str, Any]], context: ExportContext) -> tuple[str, int]:
        """Enhanced CSV export with template support."""
        logger.info(f"Starting enhanced CSV export for {len(invoices)} invoices")

        # Parse field mappings
        field_mappings = [ExportFieldMapping(**mapping) for mapping in context.template.field_mappings]
        transformer = ExportFieldTransformer(field_mappings)

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            file_path = temp_file.name

            try:
                # Write header if configured
                if context.template.header_config:
                    header_config = context.template.header_config
                    temp_file.write(f"{header_config.get('title', 'Invoice Export')}\n")
                    if header_config.get('date'):
                        temp_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    temp_file.write("\n")

                # Transform and write data
                writer = csv.DictWriter(temp_file, fieldnames=[m.target_field for m in field_mappings])
                writer.writeheader()

                for i, invoice in enumerate(invoices):
                    try:
                        # Transform record
                        transformed = transformer.transform_record(invoice)
                        writer.writerow(transformed)

                        # Update progress
                        if i % context.batch_size == 0:
                            await self._update_export_progress(context.job_id, i, len(invoices))

                    except Exception as e:
                        logger.error(f"Failed to transform invoice {invoice.get('id')}: {e}")
                        continue

                # Write footer if configured
                if context.template.footer_config:
                    footer_config = context.template.footer_config
                    temp_file.write("\n")
                    temp_file.write(f"Total Records: {len(invoices)}\n")
                    temp_file.write(f"Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            finally:
                temp_file.close()

        # Get file size
        file_size = os.path.getsize(file_path)

        # Compress if configured
        if context.template.compression:
            compressed_path = await self._compress_file(file_path)
            os.unlink(file_path)  # Remove uncompressed file
            file_path = compressed_path
            file_size = os.path.getsize(file_path)

        logger.info(f"CSV export completed: {file_path}, size: {file_size} bytes")
        return file_path, file_size

    async def _export_to_json_enhanced(self, invoices: List[Dict[str, Any]], context: ExportContext) -> tuple[str, int]:
        """Enhanced JSON export with template support."""
        logger.info(f"Starting enhanced JSON export for {len(invoices)} invoices")

        # Parse field mappings
        field_mappings = [ExportFieldMapping(**mapping) for mapping in context.template.field_mappings]
        transformer = ExportFieldTransformer(field_mappings)

        # Create export payload
        export_payload = {
            "export_metadata": {
                "format": "json",
                "version": "2.0",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_records": len(invoices),
                "template_name": context.template.name,
                "template_id": str(context.template.id),
                "system": "ap-intake-validation",
                "version": settings.VERSION,
            }
        }

        # Transform invoices
        transformed_invoices = []
        for i, invoice in enumerate(invoices):
            try:
                transformed = transformer.transform_record(invoice)
                transformed_invoices.append(transformed)

                # Update progress
                if i % context.batch_size == 0:
                    await self._update_export_progress(context.job_id, i, len(invoices))

            except Exception as e:
                logger.error(f"Failed to transform invoice {invoice.get('id')}: {e}")
                continue

        export_payload["invoices"] = transformed_invoices

        # Add summary statistics
        if transformed_invoices:
            totals = {}
            for invoice in transformed_invoices:
                for key, value in invoice.items():
                    if isinstance(value, (int, float)):
                        if key not in totals:
                            totals[key] = 0
                        totals[key] += value

            export_payload["summary"] = {
                "total_invoices": len(transformed_invoices),
                "numeric_totals": totals
            }

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            file_path = temp_file.name
            json.dump(export_payload, temp_file, indent=2, ensure_ascii=False)

        # Get file size
        file_size = os.path.getsize(file_path)

        # Compress if configured
        if context.template.compression:
            compressed_path = await self._compress_file(file_path)
            os.unlink(file_path)  # Remove uncompressed file
            file_path = compressed_path
            file_size = os.path.getsize(file_path)

        logger.info(f"JSON export completed: {file_path}, size: {file_size} bytes")
        return file_path, file_size

    async def _compress_file(self, file_path: str) -> str:
        """Compress a file using gzip."""
        compressed_path = file_path + '.gz'

        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                while True:
                    chunk = f_in.read(8192)
                    if not chunk:
                        break
                    f_out.write(chunk)

        return compressed_path

    async def _handle_export_destination(self, file_path: str, destination: ExportDestination, config: Dict[str, Any]) -> str:
        """Handle export to different destinations."""
        if destination == ExportDestination.FILE_STORAGE:
            # Upload to storage service
            filename = config.get('filename', os.path.basename(file_path))
            path = config.get('path', 'exports')
            storage_path = f"{path}/{filename}"

            with open(file_path, 'rb') as f:
                await self.storage_service.upload_file(storage_path, f.read())

            # Remove local file
            os.unlink(file_path)
            return storage_path

        elif destination == ExportDestination.DOWNLOAD:
            # Keep file for download
            return file_path

        elif destination == ExportDestination.API_ENDPOINT:
            # Send to API endpoint
            await self._send_to_api_endpoint(file_path, config)
            return file_path

        elif destination == ExportDestination.EMAIL:
            # Send via email
            await self._send_email_with_attachment(file_path, config)
            return file_path

        else:
            raise ExportException(f"Unsupported export destination: {destination}")

    async def _send_to_api_endpoint(self, file_path: str, config: Dict[str, Any]) -> None:
        """Send export file to API endpoint."""
        import aiohttp

        url = config['url']
        auth_method = config.get('auth_method', 'none')
        headers = config.get('headers', {})

        # Add authentication
        if auth_method == 'bearer':
            headers['Authorization'] = f"Bearer {config['token']}"
        elif auth_method == 'basic':
            import base64
            credentials = f"{config['username']}:{config['password']}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"

        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                async with session.post(url, data=f, headers=headers) as response:
                    if response.status >= 400:
                        raise ExportException(f"API endpoint returned error: {response.status}")

    async def _send_email_with_attachment(self, file_path: str, config: Dict[str, Any]) -> None:
        """Send export file via email."""
        # Implementation would depend on email service
        # This is a placeholder for email functionality
        logger.info(f"Email sending not implemented for file: {file_path}")

    async def _update_export_progress(self, job_id: str, processed: int, total: int) -> None:
        """Update export job progress."""
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if job:
            job.processed_records = processed
            job.status = ExportStatus.PROCESSING
            self.db.commit()

    async def _complete_export_job(self, job_id: str, message: str) -> None:
        """Mark export job as completed."""
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if job:
            job.status = ExportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            self.db.commit()

    async def _fail_export_job(self, job_id: str, error_message: str) -> None:
        """Mark export job as failed."""
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if job:
            job.status = ExportStatus.FAILED
            job.error_message = error_message
            job.completed_at = datetime.now(timezone.utc)
            job.retry_count += 1
            self.db.commit()

        await self._log_export_event(job_id, "job_failed", {"error": error_message})

    async def _log_export_event(self, job_id: str, event_type: str, event_data: Dict[str, Any], user_id: Optional[str] = None) -> None:
        """Log export event."""
        audit_log = ExportAuditLog(
            export_job_id=job_id,
            event_type=event_type,
            event_data=event_data,
            user_id=user_id
        )
        self.db.add(audit_log)
        self.db.commit()

    async def _create_export_metrics(self, job_id: str, record_count: int, file_size: int) -> None:
        """Create export metrics."""
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if job and job.started_at and job.completed_at:
            processing_time = int((job.completed_at - job.started_at).total_seconds())

            metrics = ExportMetrics(
                export_job_id=job_id,
                total_records=record_count,
                successful_records=record_count,
                failed_records=0,
                processing_time_seconds=processing_time,
                file_size_bytes=file_size,
                records_per_second=record_count // processing_time if processing_time > 0 else 0
            )
            self.db.add(metrics)
            self.db.commit()

    async def _send_completion_notification(self, job: ExportJob) -> None:
        """Send completion notification."""
        # Implementation would depend on notification service
        logger.info(f"Completion notification would be sent for job {job.id}")

    def get_export_progress(self, job_id: str) -> ExportProgress:
        """Get export job progress."""
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if not job:
            raise ExportException(f"Export job not found: {job_id}")

        progress_percentage = 0.0
        if job.total_records and job.total_records > 0:
            progress_percentage = (job.processed_records / job.total_records) * 100

        return ExportProgress(
            export_id=job.id,
            status=job.status,
            total_records=job.total_records or 0,
            processed_records=job.processed_records,
            failed_records=job.failed_records,
            progress_percentage=progress_percentage,
            current_stage=job.status.value,
            error_message=job.error_message,
            started_at=job.started_at,
            estimated_completion=job.estimated_completion
        )

    def cancel_export_job(self, job_id: str, user_id: Optional[str] = None) -> bool:
        """Cancel an export job."""
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if not job:
            raise ExportException(f"Export job not found: {job_id}")

        if job.status in [ExportStatus.COMPLETED, ExportStatus.FAILED, ExportStatus.CANCELLED]:
            raise ExportException(f"Cannot cancel job in {job.status.value} status")

        job.status = ExportStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()

        # Log cancellation
        asyncio.create_task(self._log_export_event(
            job_id,
            "job_cancelled",
            {"cancelled_by": user_id},
            user_id
        ))

        return True

    def get_export_job(self, job_id: str) -> ExportJob:
        """Get export job details."""
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if not job:
            raise ExportException(f"Export job not found: {job_id}")
        return job

    def list_export_jobs(self, user_id: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[ExportJob]:
        """List export jobs."""
        query = self.db.query(ExportJob)

        if user_id:
            query = query.filter(ExportJob.user_id == user_id)

        return query.order_by(ExportJob.created_at.desc()).offset(offset).limit(limit).all()

    async def export_to_csv(self, invoice_data: Dict[str, Any]) -> str:
        """Export invoice data to CSV format."""
        logger.info("Exporting invoice data to CSV")

        try:
            # Create CSV buffer
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header information
            header = invoice_data.get("header", {})
            writer.writerow(["INVOICE HEADER"])
            writer.writerow(["Vendor Name", header.get("vendor_name", "")])
            writer.writerow(["Invoice Number", header.get("invoice_no", "")])
            writer.writerow(["Invoice Date", header.get("invoice_date", "")])
            writer.writerow(["Due Date", header.get("due_date", "")])
            writer.writerow(["PO Number", header.get("po_no", "")])
            writer.writerow(["Currency", header.get("currency", "USD")])
            writer.writerow(["Subtotal", header.get("subtotal", "")])
            writer.writerow(["Tax", header.get("tax", "")])
            writer.writerow(["Total", header.get("total", "")])

            # Write separator
            writer.writerow([])
            writer.writerow(["LINE ITEMS"])

            # Write line items header
            writer.writerow(["Line #", "Description", "Quantity", "Unit Price", "Amount"])

            # Write line items
            lines = invoice_data.get("lines", [])
            for i, line in enumerate(lines, 1):
                writer.writerow([
                    i,
                    line.get("description", ""),
                    line.get("quantity", ""),
                    line.get("unit_price", ""),
                    line.get("amount", ""),
                ])

            # Add metadata
            metadata = invoice_data.get("metadata", {})
            writer.writerow([])
            writer.writerow(["METADATA"])
            writer.writerow(["Invoice ID", metadata.get("invoice_id", "")])
            writer.writerow(["Processed At", metadata.get("processed_at", "")])
            writer.writerow(["Exported At", datetime.utcnow().isoformat()])

            csv_content = output.getvalue()
            output.close()

            logger.info("CSV export completed successfully")
            return csv_content

        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            raise ExportException(f"CSV export failed: {str(e)}")

    async def export_to_json(self, invoice_data: Dict[str, Any]) -> str:
        """Export invoice data to JSON format."""
        logger.info("Exporting invoice data to JSON")

        try:
            # Create export payload
            export_payload = {
                "export_format": "json",
                "export_version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "invoice": invoice_data,
            }

            # Add export metadata
            export_payload["export_metadata"] = {
                "system": "ap-intake-validation",
                "version": settings.VERSION,
                "export_rules_version": "1.0.0",
            }

            json_content = json.dumps(export_payload, indent=2, ensure_ascii=False)

            logger.info("JSON export completed successfully")
            return json_content

        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            raise ExportException(f"JSON export failed: {str(e)}")

    async def export_multiple_to_csv(self, invoices: List[Dict[str, Any]]) -> str:
        """Export multiple invoices to a single CSV file."""
        logger.info(f"Exporting {len(invoices)} invoices to CSV")

        try:
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header for multiple invoices
            writer.writerow([
                "Invoice ID",
                "Vendor Name",
                "Invoice Number",
                "Invoice Date",
                "Due Date",
                "PO Number",
                "Currency",
                "Subtotal",
                "Tax",
                "Total",
                "Line Count",
                "Processed At",
            ])

            # Write each invoice
            for invoice in invoices:
                header = invoice.get("header", {})
                metadata = invoice.get("metadata", {})
                lines = invoice.get("lines", [])

                writer.writerow([
                    metadata.get("invoice_id", ""),
                    header.get("vendor_name", ""),
                    header.get("invoice_no", ""),
                    header.get("invoice_date", ""),
                    header.get("due_date", ""),
                    header.get("po_no", ""),
                    header.get("currency", "USD"),
                    header.get("subtotal", ""),
                    header.get("tax", ""),
                    header.get("total", ""),
                    len(lines),
                    metadata.get("processed_at", ""),
                ])

            # Add summary section
            writer.writerow([])
            writer.writerow(["SUMMARY"])
            writer.writerow(["Total Invoices", len(invoices)])

            total_amount = sum(
                float(invoice.get("header", {}).get("total", 0) or 0)
                for invoice in invoices
            )
            writer.writerow(["Total Amount", total_amount])

            csv_content = output.getvalue()
            output.close()

            logger.info(f"Multiple invoice CSV export completed: {len(invoices)} invoices")
            return csv_content

        except Exception as e:
            logger.error(f"Multiple invoice CSV export failed: {e}")
            raise ExportException(f"Multiple invoice CSV export failed: {str(e)}")

    async def export_multiple_to_json(self, invoices: List[Dict[str, Any]]) -> str:
        """Export multiple invoices to a single JSON file."""
        logger.info(f"Exporting {len(invoices)} invoices to JSON")

        try:
            export_payload = {
                "export_format": "json",
                "export_version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "invoices": invoices,
                "summary": {
                    "total_invoices": len(invoices),
                    "total_amount": sum(
                        float(invoice.get("header", {}).get("total", 0) or 0)
                        for invoice in invoices
                    ),
                },
                "export_metadata": {
                    "system": "ap-intake-validation",
                    "version": settings.VERSION,
                    "export_rules_version": "1.0.0",
                },
            }

            json_content = json.dumps(export_payload, indent=2, ensure_ascii=False)

            logger.info(f"Multiple invoice JSON export completed: {len(invoices)} invoices")
            return json_content

        except Exception as e:
            logger.error(f"Multiple invoice JSON export failed: {e}")
            raise ExportException(f"Multiple invoice JSON export failed: {str(e)}")

    async def export_for_erp(self, invoice_data: Dict[str, Any], erp_system: str = "generic") -> Dict[str, Any]:
        """Export invoice data formatted for specific ERP systems."""
        logger.info(f"Exporting invoice data for {erp_system} ERP system")

        try:
            if erp_system.lower() == "netsuite":
                return await self._export_for_netsuite(invoice_data)
            elif erp_system.lower() == "quickbooks":
                return await self._export_for_quickbooks(invoice_data)
            elif erp_system.lower() == "xero":
                return await self._export_for_xero(invoice_data)
            else:
                return await self._export_generic_erp(invoice_data)

        except Exception as e:
            logger.error(f"ERP export failed for {erp_system}: {e}")
            raise ExportException(f"ERP export failed: {str(e)}")

    async def export_to_quickbooks(
        self,
        invoice_data: Dict[str, Any],
        access_token: str,
        realm_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Export invoice data directly to QuickBooks using the QuickBooks service.

        Args:
            invoice_data: Invoice data from AP intake system
            access_token: QuickBooks OAuth access token
            realm_id: QuickBooks company ID
            dry_run: If True, validate without creating

        Returns:
            Export result from QuickBooks service
        """
        logger.info(f"Exporting invoice to QuickBooks: {invoice_data.get('header', {}).get('invoice_no', 'Unknown')}")

        try:
            from app.services.quickbooks_service import QuickBooksService

            async with QuickBooksService() as qb_service:
                result = await qb_service.create_bill(
                    access_token=access_token,
                    realm_id=realm_id,
                    invoice_data=invoice_data,
                    dry_run=dry_run
                )

            logger.info(f"QuickBooks export completed successfully: {result.get('Id', 'validation')}")
            return result

        except Exception as e:
            logger.error(f"QuickBooks export failed: {str(e)}")
            raise ExportException(f"QuickBooks export failed: {str(e)}")

    async def export_multiple_to_quickbooks(
        self,
        invoices: List[Dict[str, Any]],
        access_token: str,
        realm_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Export multiple invoices to QuickBooks using batch operations.

        Args:
            invoices: List of invoice data
            access_token: QuickBooks OAuth access token
            realm_id: QuickBooks company ID
            dry_run: If True, validate without creating

        Returns:
            Batch export result from QuickBooks service
        """
        logger.info(f"Batch exporting {len(invoices)} invoices to QuickBooks")

        try:
            from app.services.quickbooks_service import QuickBooksService

            async with QuickBooksService() as qb_service:
                result = await qb_service.export_multiple_bills(
                    access_token=access_token,
                    realm_id=realm_id,
                    invoices=invoices,
                    dry_run=dry_run
                )

            logger.info(f"QuickBooks batch export completed: {result['success']} success, {result['failed']} failed")
            return result

        except Exception as e:
            logger.error(f"QuickBooks batch export failed: {str(e)}")
            raise ExportException(f"QuickBooks batch export failed: {str(e)}")

    async def _export_for_netsuite(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Export invoice data for NetSuite."""
        header = invoice_data.get("header", {})
        lines = invoice_data.get("lines", [])

        # Map to NetSuite vendor bill format
        netsuite_payload = {
            "vendorName": header.get("vendor_name"),
            "tranId": header.get("invoice_no"),
            "tranDate": header.get("invoice_date"),
            "dueDate": header.get("due_date"),
            "currency": header.get("currency", "USD"),
            "memo": f"Imported from AP Intake System - PO: {header.get('po_no', 'N/A')}",
            "expenseList": []
        }

        # Add expense line items
        for line in lines:
            netsuite_payload["expenseList"].append({
                "accountName": "Accounts Payable",  # Default account
                "amount": float(line.get("amount", 0)),
                "memo": line.get("description", ""),
                "quantity": float(line.get("quantity", 1)),
                "rate": float(line.get("unit_price", 0)),
            })

        return netsuite_payload

    async def _export_for_quickbooks(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Export invoice data for QuickBooks (legacy format)."""
        header = invoice_data.get("header", {})
        lines = invoice_data.get("lines", [])

        # Map to QuickBooks bill format
        quickbooks_payload = {
            "VendorRef": {"value": header.get("vendor_name")},
            "TxnDate": header.get("invoice_date"),
            "DueDate": header.get("due_date"),
            "PrivateNote": f"Imported from AP Intake System - PO: {header.get('po_no', 'N/A')}",
            "Line": []
        }

        # Add line items
        for line in lines:
            quickbooks_payload["Line"].append({
                "Amount": float(line.get("amount", 0)),
                "Description": line.get("description", ""),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": "1"},  # Default account
                    "BillableStatus": "NotBillable",
                    "Qty": float(line.get("quantity", 1)),
                    "UnitPrice": float(line.get("unit_price", 0)),
                }
            })

        return quickbooks_payload

    async def _export_for_xero(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Export invoice data for Xero."""
        header = invoice_data.get("header", {})
        lines = invoice_data.get("lines", [])

        # Map to Xero bill format
        xero_payload = {
            "Type": "ACCPAY",
            "Contact": {"Name": header.get("vendor_name")},
            "Date": header.get("invoice_date"),
            "DueDate": header.get("due_date"),
            "CurrencyCode": header.get("currency", "USD"),
            "Reference": header.get("invoice_no"),
            "LineItems": []
        }

        # Add line items
        for line in lines:
            xero_payload["LineItems"].append({
                "Description": line.get("description", ""),
                "Quantity": str(line.get("quantity", 1)),
                "UnitAmount": str(line.get("unit_price", 0)),
                "AccountCode": "200",  # Default account code
                "TaxType": "NONE",  # Default tax type
            })

        return xero_payload

    async def _export_generic_erp(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Export invoice data in generic ERP format."""
        header = invoice_data.get("header", {})
        lines = invoice_data.get("lines", [])

        # Generic ERP format
        generic_payload = {
            "invoice": {
                "vendor": header.get("vendor_name"),
                "invoice_number": header.get("invoice_no"),
                "invoice_date": header.get("invoice_date"),
                "due_date": header.get("due_date"),
                "po_number": header.get("po_no"),
                "currency": header.get("currency", "USD"),
                "subtotal": float(header.get("subtotal", 0)),
                "tax": float(header.get("tax", 0)),
                "total": float(header.get("total", 0)),
            },
            "line_items": lines,
            "metadata": {
                "source_system": "ap-intake-validation",
                "export_timestamp": datetime.utcnow().isoformat(),
            }
        }

        return generic_payload

    async def generate_export_filename(
        self, invoice_id: str, format_type: str, timestamp: Optional[datetime] = None
    ) -> str:
        """Generate a standardized export filename."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        return f"invoice_{invoice_id}_{timestamp_str}.{format_type.lower()}"