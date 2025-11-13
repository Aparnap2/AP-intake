"""
Service for managing export templates and providing default templates.
"""

import uuid
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models.export_models import ExportTemplate, ExportFormat
from app.schemas.export_schemas import ExportFieldMapping, ExportTemplateCreate

logger = logging.getLogger(__name__)


class ExportTemplateService:
    """Service for managing export templates."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def create_default_templates(self) -> List[ExportTemplate]:
        """Create default export templates."""
        templates = []

        # Standard CSV Export Template
        csv_template = self._create_standard_csv_template()
        templates.append(csv_template)

        # Detailed JSON Export Template
        json_template = self._create_detailed_json_template()
        templates.append(json_template)

        # Accounting CSV Template
        accounting_template = self._create_accounting_csv_template()
        templates.append(accounting_template)

        # QuickBooks Template
        quickbooks_template = self._create_quickbooks_template()
        templates.append(quickbooks_template)

        # Save templates to database
        for template in templates:
            try:
                self.db.add(template)
                self.db.commit()
                logger.info(f"Created default export template: {template.name}")
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to create template {template.name}: {e}")

        return templates

    def _create_standard_csv_template(self) -> ExportTemplate:
        """Create standard CSV export template."""
        field_mappings = [
            ExportFieldMapping(
                source_field="id",
                target_field="Invoice ID",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.vendor_name",
                target_field="Vendor Name",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.invoice_no",
                target_field="Invoice Number",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.invoice_date",
                target_field="Invoice Date",
                field_type="date",
                required=True,
                format_string="%Y-%m-%d"
            ),
            ExportFieldMapping(
                source_field="header.due_date",
                target_field="Due Date",
                field_type="date",
                format_string="%Y-%m-%d"
            ),
            ExportFieldMapping(
                source_field="header.po_no",
                target_field="PO Number",
                field_type="string"
            ),
            ExportFieldMapping(
                source_field="header.currency",
                target_field="Currency",
                field_type="string",
                default_value="USD"
            ),
            ExportFieldMapping(
                source_field="header.total",
                target_field="Total Amount",
                field_type="decimal",
                required=True,
                transform_function="currency_format"
            ),
            ExportFieldMapping(
                source_field="metadata.status",
                target_field="Status",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="metadata.processed_at",
                target_field="Processed Date",
                field_type="date",
                format_string="%Y-%m-%d %H:%M:%S"
            )
        ]

        return ExportTemplate(
            name="Standard CSV Export",
            description="Standard CSV export with basic invoice fields",
            format=ExportFormat.CSV,
            field_mappings=[m.model_dump() for m in field_mappings],
            header_config={
                "title": "Invoice Export Report",
                "date": True,
                "include_timestamp": True
            },
            footer_config={
                "include_totals": True,
                "include_record_count": True
            },
            compression=False,
            encryption=False
        )

    def _create_detailed_json_template(self) -> ExportTemplate:
        """Create detailed JSON export template."""
        field_mappings = [
            ExportFieldMapping(
                source_field="id",
                target_field="invoice_id",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header",
                target_field="header_data",
                field_type="json",
                required=True
            ),
            ExportFieldMapping(
                source_field="lines",
                target_field="line_items",
                field_type="json",
                required=True
            ),
            ExportFieldMapping(
                source_field="metadata.confidence",
                target_field="extraction_confidence",
                field_type="json"
            ),
            ExportFieldMapping(
                source_field="metadata.processed_at",
                target_field="processed_timestamp",
                field_type="date"
            ),
            ExportFieldMapping(
                source_field="metadata.status",
                target_field="processing_status",
                field_type="string",
                required=True
            )
        ]

        return ExportTemplate(
            name="Detailed JSON Export",
            description="Complete JSON export with all invoice data and metadata",
            format=ExportFormat.JSON,
            field_mappings=[m.model_dump() for m in field_mappings],
            header_config={
                "include_metadata": True,
                "include_system_info": True
            },
            compression=True,
            encryption=False
        )

    def _create_accounting_csv_template(self) -> ExportTemplate:
        """Create accounting-focused CSV export template."""
        field_mappings = [
            ExportFieldMapping(
                source_field="header.invoice_no",
                target_field="Document Number",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.vendor_name",
                target_field="Vendor Name",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.invoice_date",
                target_field="Document Date",
                field_type="date",
                required=True,
                format_string="%Y-%m-%d"
            ),
            ExportFieldMapping(
                source_field="header.due_date",
                target_field="Due Date",
                field_type="date",
                required=True,
                format_string="%Y-%m-%d"
            ),
            ExportFieldMapping(
                source_field="header.subtotal",
                target_field="Net Amount",
                field_type="decimal",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.tax",
                target_field="Tax Amount",
                field_type="decimal"
            ),
            ExportFieldMapping(
                source_field="header.total",
                target_field="Gross Amount",
                field_type="decimal",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.currency",
                target_field="Currency Code",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="lines",
                target_field="Line Item Count",
                field_type="number",
                transform_function="len"
            )
        ]

        return ExportTemplate(
            name="Accounting CSV Export",
            description="Accounting-focused CSV export with financial fields",
            format=ExportFormat.CSV,
            field_mappings=[m.model_dump() for m in field_mappings],
            header_config={
                "title": "Accounts Payable Export",
                "date": True,
                "include_period": True
            },
            footer_config={
                "include_financial_totals": True,
                "include_summary_stats": True
            },
            compression=False,
            encryption=False
        )

    def _create_quickbooks_template(self) -> ExportTemplate:
        """Create QuickBooks-compatible export template."""
        field_mappings = [
            ExportFieldMapping(
                source_field="header.vendor_name",
                target_field="VendorRef",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.invoice_no",
                target_field="DocNumber",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.invoice_date",
                target_field="TxnDate",
                field_type="date",
                required=True,
                format_string="%Y-%m-%d"
            ),
            ExportFieldMapping(
                source_field="header.due_date",
                target_field="DueDate",
                field_type="date",
                required=True,
                format_string="%Y-%m-%d"
            ),
            ExportFieldMapping(
                source_field="header.total",
                target_field="TotalAmt",
                field_type="decimal",
                required=True
            ),
            ExportFieldMapping(
                source_field="lines",
                target_field="Line",
                field_type="json",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.po_no",
                target_field="PrivateNote",
                field_type="string",
                transform_function="title_case"
            )
        ]

        return ExportTemplate(
            name="QuickBooks Export",
            description="QuickBooks-compatible export format",
            format=ExportFormat.JSON,
            field_mappings=[m.model_dump() for m in field_mappings],
            header_config={
                "quickbooks_format": True,
                "api_version": "v3"
            },
            compression=True,
            encryption=False
        )

    def get_template_by_name(self, name: str) -> Optional[ExportTemplate]:
        """Get template by name."""
        return self.db.query(ExportTemplate).filter(
            ExportTemplate.name == name,
            ExportTemplate.is_active == True
        ).first()

    def get_templates_by_format(self, format: ExportFormat) -> List[ExportTemplate]:
        """Get all active templates for a specific format."""
        return self.db.query(ExportTemplate).filter(
            ExportTemplate.format == format,
            ExportTemplate.is_active == True
        ).order_by(ExportTemplate.name).all()

    def update_template_usage(self, template_id: str) -> None:
        """Update template usage statistics."""
        template = self.db.query(ExportTemplate).filter(ExportTemplate.id == template_id).first()
        if template:
            template.usage_count += 1
            template.last_used_at = datetime.utcnow()
            self.db.commit()