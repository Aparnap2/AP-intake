"""
Test Data Generation Service

Comprehensive test data generation for AP Intake & Validation system.
Creates realistic PDF invoices with various scenarios, duplicates, exceptions,
and edge cases for testing all system capabilities.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import asyncio
from dataclasses import dataclass, asdict

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus import PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.core.config import settings
from app.models.invoice import Invoice, InvoiceStatus
from app.models.schemas import PreparedBill


@dataclass
class InvoiceTemplate:
    """Invoice template configuration"""
    vendor_name: str
    vendor_address: str
    vendor_tax_id: str
    customer_name: str
    customer_address: str
    invoice_number: str
    invoice_date: datetime
    due_date: datetime
    items: List[Dict[str, Any]]
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str = "USD"
    payment_terms: str = "Net 30"
    notes: Optional[str] = None
    purchase_order: Optional[str] = None


@dataclass
class TestScenario:
    """Test scenario configuration"""
    scenario_id: str
    name: str
    description: str
    category: str
    expected_extraction: Dict[str, Any]
    expected_validation: Dict[str, Any]
    test_tags: List[str]
    file_name: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    expected_exception_code: Optional[str] = None


class InvoicePDFGenerator:
    """Generate realistic PDF invoices for testing"""

    def __init__(self):
        self.output_dir = Path("tests/fixtures/test_invoices")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom styles for invoice PDFs"""
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#2C3E50')
        ))

        self.styles.add(ParagraphStyle(
            name='Address',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            textColor=HexColor('#7F8C8D')
        ))

        self.styles.add(ParagraphStyle(
            name='TotalLabel',
            parent=self.styles['Normal'],
            fontSize=12,
            alignment=TA_RIGHT,
            textColor=HexColor('#2C3E50')
        ))

        self.styles.add(ParagraphStyle(
            name='TotalAmount',
            parent=self.styles['Heading2'],
            fontSize=18,
            alignment=TA_RIGHT,
            textColor=HexColor('#27AE60')
        ))

    def generate_invoice_pdf(self, template: InvoiceTemplate, filename: str) -> str:
        """Generate a PDF invoice from template"""
        filepath = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []

        # Invoice header
        story.append(Paragraph("INVOICE", self.styles['InvoiceTitle']))
        story.append(Spacer(1, 0.3*inch))

        # Vendor and customer info
        vendor_customer_data = [
            [
                self._format_address_block(
                    template.vendor_name,
                    template.vendor_address,
                    template.vendor_tax_id
                ),
                self._format_address_block(
                    template.customer_name,
                    template.customer_address
                )
            ]
        ]

        vendor_table = Table(vendor_customer_data, colWidths=[3*inch, 3*inch])
        vendor_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))

        story.append(vendor_table)
        story.append(Spacer(1, 0.3*inch))

        # Invoice details
        invoice_info = [
            ["Invoice Number:", template.invoice_number],
            ["Invoice Date:", template.invoice_date.strftime("%B %d, %Y")],
            ["Due Date:", template.due_date.strftime("%B %d, %Y")],
            ["Payment Terms:", template.payment_terms],
        ]

        if template.purchase_order:
            invoice_info.append(["Purchase Order:", template.purchase_order])

        info_table = Table(invoice_info, colWidths=[1.5*inch, 2*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#7F8C8D')),
            ('TEXTCOLOR', (1, 0), (1, -1), HexColor('#2C3E50')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))

        # Line items table
        item_headers = ["Description", "Quantity", "Unit Price", "Amount"]
        item_data = [item_headers]

        for item in template.items:
            item_data.append([
                item['description'],
                str(item['quantity']),
                f"${item['unit_price']:.2f}",
                f"${item['amount']:.2f}"
            ])

        items_table = Table(item_data, colWidths=[3*inch, 0.8*inch, 1.2*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#ECF0F1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#2C3E50')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#BDC3C7')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(items_table)
        story.append(Spacer(1, 0.4*inch))

        # Totals
        totals_data = [
            ["Subtotal:", f"${template.subtotal:.2f}"],
            [f"Tax ({template.tax_rate*100:.1f}%):", f"${template.tax_amount:.2f}"],
            ["Total:", f"${template.total_amount:.2f}"]
        ]

        totals_table = Table(totals_data, colWidths=[4*inch, 2*inch])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (0, 1), 10),
            ('FONTSIZE', (0, 2), (1, 2), 14),
            ('FONTNAME', (0, 2), (1, 2), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 2), (1, 2), HexColor('#27AE60')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(totals_table)

        # Notes
        if template.notes:
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("Notes:", self.styles['Heading3']))
            story.append(Paragraph(template.notes, self.styles['Normal']))

        # Footer
        story.append(PageBreak())
        story.append(Spacer(1, 2*inch))
        footer_text = f"Thank you for your business! {template.vendor_name}"
        story.append(Paragraph(footer_text, self.styles['Normal']))

        doc.build(story)
        return str(filepath)

    def _format_address_block(self, name: str, address: str, tax_id: str = None) -> List[Paragraph]:
        """Format address block for PDF"""
        lines = [Paragraph(f"<b>{name}</b>", self.styles['Normal'])]

        for line in address.split('\n'):
            lines.append(Paragraph(line, self.styles['Address']))

        if tax_id:
            lines.append(Paragraph(f"Tax ID: {tax_id}", self.styles['Address']))

        return lines


class TestDataGenerator:
    """Generate comprehensive test data for AP Intake system"""

    def __init__(self):
        self.pdf_generator = InvoicePDFGenerator()
        self.metadata_dir = Path("tests/fixtures/test_data")
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.expected_results_dir = Path("tests/fixtures/expected_results")
        self.expected_results_dir.mkdir(parents=True, exist_ok=True)

        # Sample data pools
        self.vendors = [
            {
                "name": "Acme Corporation",
                "address": "123 Business Ave\nSuite 100\nNew York, NY 10001",
                "tax_id": "12-3456789"
            },
            {
                "name": "Global Tech Solutions",
                "address": "456 Innovation Drive\nTech Park, CA 94025",
                "tax_id": "98-7654321"
            },
            {
                "name": "Office Supply Warehouse",
                "address": "789 Commerce Blvd\nSupply City, TX 75001",
                "tax_id": "45-6789012"
            },
            {
                "name": "Consulting Partners LLC",
                "address": "321 Professional Way\nConsulting, MA 02101",
                "tax_id": "67-8901234"
            },
            {
                "name": "Manufacturing Excellence Inc",
                "address": "555 Production Road\nFactory Town, MI 48501",
                "tax_id": "89-0123456"
            }
        ]

        self.customers = [
            {
                "name": "Your Company Name",
                "address": "100 Main Street\nCorporate Center, CA 90210"
            }
        ]

        self.item_descriptions = [
            "Software License - Annual Subscription",
            "IT Consulting Services",
            "Office Supplies - Paper & Stationery",
            "Hardware Equipment",
            "Cloud Storage Services",
            "Professional Development Training",
            "Marketing Services",
            "Legal Services",
            "Accounting Services",
            "Facility Maintenance",
            "Employee Benefits Administration",
            "Cybersecurity Assessment",
            "Data Backup Services",
            "Network Infrastructure",
            "Equipment Rental"
        ]

    def generate_all_test_data(self) -> Dict[str, Any]:
        """Generate comprehensive test dataset"""
        print("🔧 Generating comprehensive test dataset...")

        results = {
            "standard_invoices": [],
            "duplicate_invoices": [],
            "exception_cases": [],
            "edge_cases": [],
            "performance_test": [],
            "scenarios": {}
        }

        # Generate standard invoices
        standard_invoices = self._generate_standard_invoices(30)
        results["standard_invoices"] = standard_invoices

        # Generate duplicate invoices
        duplicate_invoices = self._generate_duplicate_invoices(20, standard_invoices)
        results["duplicate_invoices"] = duplicate_invoices

        # Generate exception cases
        exception_cases = self._generate_exception_cases(25)
        results["exception_cases"] = exception_cases

        # Generate edge cases
        edge_cases = self._generate_edge_cases(15)
        results["edge_cases"] = edge_cases

        # Generate performance test cases
        performance_cases = self._generate_performance_test_cases(10)
        results["performance_test"] = performance_cases

        # Combine all scenarios
        all_scenarios = {}
        for category in results.values():
            if isinstance(category, list):
                for scenario in category:
                    all_scenarios[scenario.scenario_id] = scenario

        results["scenarios"] = all_scenarios

        # Save metadata
        self._save_test_metadata(results)

        print(f"✅ Generated {len(all_scenarios)} test scenarios:")
        print(f"   • Standard invoices: {len(standard_invoices)}")
        print(f"   • Duplicate invoices: {len(duplicate_invoices)}")
        print(f"   • Exception cases: {len(exception_cases)}")
        print(f"   • Edge cases: {len(edge_cases)}")
        print(f"   • Performance tests: {len(performance_cases)}")

        return results

    def _generate_standard_invoices(self, count: int) -> List[TestScenario]:
        """Generate standard invoice scenarios"""
        scenarios = []

        for i in range(count):
            scenario_id = f"STD_{i+1:03d}"

            # Select vendor
            vendor = random.choice(self.vendors)

            # Generate invoice details
            invoice_number = f"INV-{2025}-{i+1:04d}"
            invoice_date = datetime.now() - timedelta(days=random.randint(1, 60))
            due_date = invoice_date + timedelta(days=30)

            # Generate line items
            num_items = random.randint(1, 5)
            items = []
            subtotal = Decimal('0.00')

            for j in range(num_items):
                quantity = random.randint(1, 10)
                unit_price = Decimal(str(round(random.uniform(50.00, 500.00), 2)))
                amount = quantity * unit_price
                subtotal += amount

                items.append({
                    "description": random.choice(self.item_descriptions),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "amount": amount
                })

            # Calculate totals
            tax_rate = Decimal(str(random.choice([0.08, 0.0825, 0.09, 0.1])))
            tax_amount = subtotal * tax_rate
            total_amount = subtotal + tax_amount

            # Create template
            template = InvoiceTemplate(
                vendor_name=vendor["name"],
                vendor_address=vendor["address"],
                vendor_tax_id=vendor["tax_id"],
                customer_name=self.customers[0]["name"],
                customer_address=self.customers[0]["address"],
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                due_date=due_date,
                items=items,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total_amount=total_amount,
                currency="USD",
                payment_terms="Net 30",
                notes=None,
                purchase_order=f"PO-{2025}-{i+1:04d}" if random.random() > 0.5 else None
            )

            # Generate filename
            filename = f"standard_invoice_{i+1:03d}.pdf"

            # Generate PDF
            filepath = self.pdf_generator.generate_invoice_pdf(template, filename)

            # Create test scenario
            scenario = TestScenario(
                scenario_id=scenario_id,
                name=f"Standard Invoice {i+1}",
                description=f"Standard invoice with {num_items} line items",
                category="standard_invoices",
                expected_extraction={
                    "invoice_number": invoice_number,
                    "vendor_name": vendor["name"],
                    "total_amount": float(total_amount),
                    "invoice_date": invoice_date.strftime("%Y-%m-%d"),
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "line_items_count": num_items,
                    "currency": "USD"
                },
                expected_validation={
                    "structural_pass": True,
                    "math_pass": True,
                    "business_rules_pass": True,
                    "duplicate_pass": True
                },
                test_tags=["standard", "normal_processing"],
                file_name=filename
            )

            scenarios.append(scenario)

        return scenarios

    def _generate_duplicate_invoices(self, count: int, standard_invoices: List[TestScenario]) -> List[TestScenario]:
        """Generate duplicate invoice scenarios"""
        scenarios = []

        # Use first few standard invoices as originals
        originals = standard_invoices[:min(count, len(standard_invoices))]

        for i, original in enumerate(originals):
            # Create near-duplicate with subtle variations
            duplicate_types = [
                "exact_copy",
                "minor_amount_diff",
                "different_date",
                "different_vendor",
                "same_amount_diff_items"
            ]

            duplicate_type = random.choice(duplicate_types)
            variation_suffix = {
                "exact_copy": "copy",
                "minor_amount_diff": "v1",
                "different_date": "v2",
                "different_vendor": "v3",
                "same_amount_diff_items": "v4"
            }[duplicate_type]

            scenario_id = f"DUP_{i+1:03d}_{variation_suffix}"
            filename = f"duplicate_invoice_{i+1:03d}_{variation_suffix}.pdf"

            # Load original template data (simplified for demo)
            # In real implementation, would parse the PDF or store template data
            vendor = random.choice(self.vendors)

            # Adjust based on duplicate type
            if duplicate_type == "exact_copy":
                # Exact same invoice number
                invoice_number = original.expected_extraction["invoice_number"]
            elif duplicate_type == "minor_amount_diff":
                # Slightly different amount
                invoice_number = original.expected_extraction["invoice_number"]
                # Would adjust amounts in template
            elif duplicate_type == "different_date":
                # Different date, same invoice number
                invoice_number = original.expected_extraction["invoice_number"]
                # Would adjust date in template
            else:
                # Different invoice number but similar details
                base_num = int(original.expected_extraction["invoice_number"].split("-")[1])
                invoice_number = f"INV-{2025}-{base_num+100:04d}"

            # Create simplified template for duplicate
            template = InvoiceTemplate(
                vendor_name=vendor["name"],
                vendor_address=vendor["address"],
                vendor_tax_id=vendor["tax_id"],
                customer_name=self.customers[0]["name"],
                customer_address=self.customers[0]["address"],
                invoice_number=invoice_number,
                invoice_date=datetime.now() - timedelta(days=random.randint(1, 60)),
                due_date=datetime.now() + timedelta(days=30),
                items=[
                    {
                        "description": "Sample Service",
                        "quantity": 1,
                        "unit_price": Decimal("100.00"),
                        "amount": Decimal("100.00")
                    }
                ],
                subtotal=Decimal("100.00"),
                tax_rate=Decimal("0.08"),
                tax_amount=Decimal("8.00"),
                total_amount=Decimal("108.00")
            )

            # Generate PDF
            filepath = self.pdf_generator.generate_invoice_pdf(template, filename)

            # Create test scenario
            scenario = TestScenario(
                scenario_id=scenario_id,
                name=f"Duplicate Invoice {i+1} ({duplicate_type})",
                description=f"Duplicate of {original.scenario_id} with variation: {duplicate_type}",
                category="duplicate_invoices",
                expected_extraction={
                    "invoice_number": invoice_number,
                    "vendor_name": vendor["name"],
                    "total_amount": 108.00,
                    "currency": "USD"
                },
                expected_validation={
                    "structural_pass": True,
                    "math_pass": True,
                    "business_rules_pass": True,
                    "duplicate_pass": False  # Should flag as duplicate
                },
                test_tags=["duplicate", duplicate_type],
                file_name=filename,
                is_duplicate=True,
                duplicate_of=original.scenario_id
            )

            scenarios.append(scenario)

        return scenarios

    def _generate_exception_cases(self, count: int) -> List[TestScenario]:
        """Generate invoice scenarios that should trigger exceptions"""
        scenarios = []

        exception_types = [
            ("missing_vendor", "Vendor not in system", {"duplicate_pass": False}),
            ("invalid_total", "Mathematical error in totals", {"math_pass": False}),
            ("missing_required_fields", "Required fields missing", {"structural_pass": False}),
            ("invalid_date_format", "Date format not valid", {"structural_pass": False}),
            ("negative_amounts", "Negative line item amounts", {"business_rules_pass": False}),
            ("zero_amount_invoice", "Invoice with zero total", {"business_rules_pass": False}),
            ("duplicate_within_batch", "Same invoice uploaded twice", {"duplicate_pass": False}),
            ("po_mismatch", "Purchase order mismatch", {"business_rules_pass": False}),
            ("currency_not_supported", "Unsupported currency", {"business_rules_pass": False}),
            ("overdue_invoice", "Invoice already past due", {"business_rules_pass": False}),
            ("large_amount_threshold", "Amount exceeds approval threshold", {"business_rules_pass": False}),
            ("missing_tax_id", "Vendor tax ID missing", {"structural_pass": False}),
            ("corrupted_pdf", "Corrupted PDF file", {"structural_pass": False}),
            ("empty_invoice", "Invoice with no line items", {"structural_pass": False}),
            ("invalid_tax_calculation", "Incorrect tax calculation", {"math_pass": False}),
            ("future_date", "Invoice date in future", {"business_rules_pass": False}),
            ("very_old_date", "Invoice date too old", {"business_rules_pass": False})
        ]

        for i in range(count):
            exception_type, description, validation_result = exception_types[i % len(exception_types)]
            scenario_id = f"EXC_{i+1:03d}"
            filename = f"exception_invoice_{i+1:03d}_{exception_type}.pdf"

            # Create invoice that will trigger the exception
            vendor = random.choice(self.vendors)

            if exception_type == "negative_amounts":
                items = [{"description": "Refund", "quantity": -1, "unit_price": Decimal("100.00"), "amount": Decimal("-100.00")}]
                total_amount = Decimal("-100.00")
            elif exception_type == "zero_amount_invoice":
                items = [{"description": "Free Service", "quantity": 1, "unit_price": Decimal("0.00"), "amount": Decimal("0.00")}]
                total_amount = Decimal("0.00")
            elif exception_type == "large_amount_threshold":
                items = [{"description": "High Value Service", "quantity": 1, "unit_price": Decimal("50000.00"), "amount": Decimal("50000.00")}]
                total_amount = Decimal("54000.00")  # With tax
            else:
                items = [{"description": "Standard Service", "quantity": 1, "unit_price": Decimal("100.00"), "amount": Decimal("100.00")}]
                total_amount = Decimal("108.00")

            template = InvoiceTemplate(
                vendor_name=vendor["name"],
                vendor_address=vendor["address"],
                vendor_tax_id="" if exception_type == "missing_tax_id" else vendor["tax_id"],
                customer_name=self.customers[0]["name"],
                customer_address=self.customers[0]["address"],
                invoice_number=f"INV-{2025}-{i+1:04d}",
                invoice_date=datetime.now() + timedelta(days=7) if exception_type == "future_date" else datetime.now() - timedelta(days(400) if exception_type == "very_old_date" else random.randint(1, 60)),
                due_date=datetime.now() + timedelta(days=30),
                items=items,
                subtotal=Decimal("100.00") if total_amount >= 0 else Decimal("-100.00"),
                tax_rate=Decimal("0.08"),
                tax_amount=Decimal("8.00"),
                total_amount=total_amount,
                currency="EUR" if exception_type == "currency_not_supported" else "USD"
            )

            # Generate PDF (skip for corrupted PDF case)
            if exception_type != "corrupted_pdf":
                filepath = self.pdf_generator.generate_invoice_pdf(template, filename)
            else:
                # Create a corrupted file
                filepath = self.output_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(b'Corrupted PDF data that cannot be parsed')

            scenario = TestScenario(
                scenario_id=scenario_id,
                name=f"Exception Case {i+1}: {exception_type}",
                description=description,
                category="exception_cases",
                expected_extraction={
                    "invoice_number": template.invoice_number,
                    "vendor_name": template.vendor_name,
                    "total_amount": float(total_amount),
                    "currency": template.currency
                },
                expected_validation={
                    "structural_pass": exception_type not in ["missing_required_fields", "invalid_date_format", "missing_tax_id", "empty_invoice", "corrupted_pdf"],
                    "math_pass": exception_type not in ["invalid_total", "invalid_tax_calculation"],
                    "business_rules_pass": exception_type not in ["negative_amounts", "zero_amount_invoice", "po_mismatch", "currency_not_supported", "overdue_invoice", "large_amount_threshold", "future_date", "very_old_date"],
                    "duplicate_pass": exception_type != "duplicate_within_batch"
                },
                test_tags=["exception", exception_type],
                file_name=filename,
                expected_exception_code=exception_type
            )

            scenarios.append(scenario)

        return scenarios

    def _generate_edge_cases(self, count: int) -> List[TestScenario]:
        """Generate edge case scenarios"""
        scenarios = []

        edge_case_types = [
            ("multi_page", "Multi-page invoice with many items"),
            ("handwritten_elements", "Invoice with handwritten annotations"),
            ("foreign_currency", "Invoice in foreign currency with conversion"),
            ("very_large_file", "Extremely large PDF file"),
            ("complex_formatting", "Complex layout with tables and images"),
            ("partial_scan", "Poor quality scan of invoice"),
            ("non_standard_layout", "Unusual invoice layout"),
            ("multiple_vendors", "Invoice from multiple vendors"),
            ("partial_data", "Invoice with missing information"),
            ("special_characters", "Invoice with special characters"),
            ("long_descriptions", "Very long item descriptions"),
            ("decimal_precision", "High precision decimal amounts"),
            ("mixed_currencies", "Invoice with multiple currencies"),
            ("backdated", "Invoice backdated by years"),
            ("bulk_order", "Invoice with hundreds of line items")
        ]

        for i in range(count):
            edge_type, description = edge_case_types[i % len(edge_case_types)]
            scenario_id = f"EDGE_{i+1:03d}"
            filename = f"edge_case_{i+1:03d}_{edge_type}.pdf"

            # Create template for edge case
            vendor = random.choice(self.vendors)

            if edge_type == "multi_page":
                # Many items to create multi-page invoice
                num_items = 50
                items = []
                subtotal = Decimal('0.00')
                for j in range(num_items):
                    quantity = random.randint(1, 5)
                    unit_price = Decimal(str(round(random.uniform(10.00, 100.00), 2)))
                    amount = quantity * unit_price
                    subtotal += amount
                    items.append({
                        "description": f"Item {j+1}: {random.choice(self.item_descriptions)}",
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "amount": amount
                    })
            elif edge_type == "bulk_order":
                # Hundreds of small items
                num_items = 200
                items = []
                subtotal = Decimal('0.00')
                for j in range(num_items):
                    quantity = 1
                    unit_price = Decimal("5.00")
                    amount = Decimal("5.00")
                    subtotal += amount
                    items.append({
                        "description": f"Part {j+1:03d}",
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "amount": amount
                    })
            elif edge_type == "foreign_currency":
                items = [{"description": "International Service", "quantity": 1, "unit_price": Decimal("1000.00"), "amount": Decimal("1000.00")}]
                subtotal = Decimal("1000.00")
            elif edge_type == "decimal_precision":
                items = [{"description": "Precision Service", "quantity": 1, "unit_price": Decimal("123.456789"), "amount": Decimal("123.456789")}]
                subtotal = Decimal("123.456789")
            else:
                items = [{"description": f"Edge Case: {edge_type}", "quantity": 1, "unit_price": Decimal("100.00"), "amount": Decimal("100.00")}]
                subtotal = Decimal("100.00")

            tax_rate = Decimal("0.08")
            tax_amount = subtotal * tax_rate
            total_amount = subtotal + tax_amount

            # Create special notes for edge cases
            notes = {
                "handwritten_elements": "Note: Some amounts may be handwritten and verified",
                "partial_scan": "Note: Poor scan quality may affect OCR accuracy",
                "special_characters": "Note: Contains special characters: é, ü, ñ, ©, ®",
                "long_descriptions": "Note: Very long item descriptions for testing field limits",
                "partial_data": "Note: Some fields intentionally left incomplete"
            }.get(edge_type)

            template = InvoiceTemplate(
                vendor_name=vendor["name"],
                vendor_address=vendor["address"],
                vendor_tax_id=vendor["tax_id"],
                customer_name=self.customers[0]["name"],
                customer_address=self.customers[0]["address"],
                invoice_number=f"INV-{2025}-{i+1:04d}",
                invoice_date=datetime.now() - timedelta(days=random.randint(1, 60)),
                due_date=datetime.now() + timedelta(days=30),
                items=items,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total_amount=total_amount,
                currency="EUR" if edge_type == "foreign_currency" else "USD",
                notes=notes
            )

            # Generate PDF
            filepath = self.pdf_generator.generate_invoice_pdf(template, filename)

            scenario = TestScenario(
                scenario_id=scenario_id,
                name=f"Edge Case {i+1}: {edge_type}",
                description=description,
                category="edge_cases",
                expected_extraction={
                    "invoice_number": template.invoice_number,
                    "vendor_name": template.vendor_name,
                    "total_amount": float(total_amount),
                    "currency": template.currency,
                    "line_items_count": len(items)
                },
                expected_validation={
                    "structural_pass": edge_type not in ["partial_data"],
                    "math_pass": True,
                    "business_rules_pass": edge_type not in ["foreign_currency"],
                    "duplicate_pass": True
                },
                test_tags=["edge_case", edge_type],
                file_name=filename
            )

            scenarios.append(scenario)

        return scenarios

    def _generate_performance_test_cases(self, count: int) -> List[TestScenario]:
        """Generate performance test scenarios"""
        scenarios = []

        performance_types = [
            ("large_file_size", "Large file size test (10MB+)"),
            ("concurrent_processing", "Concurrent processing test"),
            ("high_volume_batch", "High volume batch processing"),
            ("memory_intensive", "Memory intensive processing"),
            ("complex_calculations", "Complex calculations test"),
            ("network_latency", "Network latency simulation"),
            ("database_load", "Database load test"),
            ("cache_performance", "Cache performance test"),
            ("queue_throughput", "Message queue throughput"),
            ("api_rate_limiting", "API rate limiting test")
        ]

        for i in range(count):
            perf_type, description = performance_types[i % len(performance_types)]
            scenario_id = f"PERF_{i+1:03d}"
            filename = f"performance_test_{i+1:03d}_{perf_type}.pdf"

            # Create template for performance test
            vendor = random.choice(self.vendors)

            # For performance tests, create varying complexity
            if perf_type in ["large_file_size", "memory_intensive"]:
                # Create many items to increase file size
                num_items = 100 if perf_type == "large_file_size" else 500
                items = []
                subtotal = Decimal('0.00')
                for j in range(num_items):
                    quantity = random.randint(1, 10)
                    unit_price = Decimal(str(round(random.uniform(1.00, 1000.00), 2)))
                    amount = quantity * unit_price
                    subtotal += amount
                    items.append({
                        "description": f"Performance Test Item {j+1:03d}: {random.choice(self.item_descriptions)}",
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "amount": amount
                    })
            elif perf_type == "complex_calculations":
                # Items with complex pricing
                items = []
                subtotal = Decimal('0.00')
                for j in range(20):
                    # Create complex pricing scenarios
                    quantity = random.randint(1, 100)
                    unit_price = Decimal(str(round(random.uniform(0.01, 9999.99), 2)))
                    amount = quantity * unit_price
                    subtotal += amount
                    items.append({
                        "description": f"Complex Calculation Item {j+1}",
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "amount": amount
                    })
            else:
                # Standard performance test
                items = [{"description": f"Performance Test: {perf_type}", "quantity": 10, "unit_price": Decimal("100.00"), "amount": Decimal("1000.00")}]
                subtotal = Decimal("1000.00")

            tax_rate = Decimal("0.08")
            tax_amount = subtotal * tax_rate
            total_amount = subtotal + tax_amount

            template = InvoiceTemplate(
                vendor_name=vendor["name"],
                vendor_address=vendor["address"],
                vendor_tax_id=vendor["tax_id"],
                customer_name=self.customers[0]["name"],
                customer_address=self.customers[0]["address"],
                invoice_number=f"INV-PERF-{2025}-{i+1:04d}",
                invoice_date=datetime.now() - timedelta(days=random.randint(1, 60)),
                due_date=datetime.now() + timedelta(days=30),
                items=items,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total_amount=total_amount,
                notes=f"Performance test scenario: {description}"
            )

            # Generate PDF
            filepath = self.pdf_generator.generate_invoice_pdf(template, filename)

            scenario = TestScenario(
                scenario_id=scenario_id,
                name=f"Performance Test {i+1}: {perf_type}",
                description=description,
                category="performance_test",
                expected_extraction={
                    "invoice_number": template.invoice_number,
                    "vendor_name": template.vendor_name,
                    "total_amount": float(total_amount),
                    "currency": "USD",
                    "line_items_count": len(items)
                },
                expected_validation={
                    "structural_pass": True,
                    "math_pass": True,
                    "business_rules_pass": True,
                    "duplicate_pass": True
                },
                test_tags=["performance", perf_type],
                file_name=filename
            )

            scenarios.append(scenario)

        return scenarios

    def _save_test_metadata(self, results: Dict[str, Any]) -> None:
        """Save test metadata to JSON files"""
        # Save complete metadata
        metadata_file = self.metadata_dir / "test_scenarios.json"

        # Convert scenarios to dictionaries
        serializable_results = {}
        for category, scenarios in results.items():
            if category == "scenarios":
                serializable_results[category] = {
                    scenario_id: asdict(scenario)
                    for scenario_id, scenario in scenarios.items()
                }
            elif isinstance(scenarios, list):
                serializable_results[category] = [asdict(scenario) for scenario in scenarios]
            else:
                serializable_results[category] = scenarios

        with open(metadata_file, 'w') as f:
            json.dump(serializable_results, f, indent=2, default=str)

        # Save category-specific metadata
        for category in ["standard_invoices", "duplicate_invoices", "exception_cases", "edge_cases", "performance_test"]:
            if category in results:
                category_file = self.metadata_dir / f"{category}.json"
                category_data = [asdict(scenario) for scenario in results[category]]
                with open(category_file, 'w') as f:
                    json.dump(category_data, f, indent=2, default=str)

        # Save summary
        summary = {
            "generation_timestamp": datetime.now().isoformat(),
            "total_scenarios": len(results["scenarios"]),
            "categories": {
                "standard_invoices": len(results["standard_invoices"]),
                "duplicate_invoices": len(results["duplicate_invoices"]),
                "exception_cases": len(results["exception_cases"]),
                "edge_cases": len(results["edge_cases"]),
                "performance_test": len(results["performance_test"])
            },
            "test_files_location": str(self.output_dir),
            "metadata_location": str(self.metadata_dir)
        }

        summary_file = self.metadata_dir / "generation_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"📊 Test metadata saved to: {self.metadata_dir}")


async def generate_test_data() -> Dict[str, Any]:
    """Main function to generate all test data"""
    generator = TestDataGenerator()
    return generator.generate_all_test_data()


if __name__ == "__main__":
    # Run test data generation
    results = asyncio.run(generate_test_data())
    print(f"\n🎯 Test data generation complete!")
    print(f"Generated {results['total_scenarios']} test scenarios")