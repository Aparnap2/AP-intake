#!/usr/bin/env python3
"""
Comprehensive Test PDF Invoice Generator for AP Intake & Validation System.

This script creates professional test PDF invoices using ReportLab to thoroughly test
the document parsing capabilities of the Docling-based invoice processing system.

Features:
- Multiple invoice scenarios (standard, complex, edge cases, error scenarios)
- Professional formatting with tables, headers, footers
- Barcode/QR code generation for advanced testing
- Various data quality scenarios to test validation
- Configurable output directory and naming

Usage:
    python scripts/create_test_invoice.py [--scenario all] [--output-dir ./test_invoices]
"""

import os
import sys
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import tempfile
import subprocess

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Try to import barcode/qrcode libraries
try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("Warning: barcode library not available. Install with: pip install python-barcode")

try:
    import qrcode
    from qrcode.image.pil import PilImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    print("Warning: qrcode library not available. Install with: pip install qrcode[pil]")


@dataclass
class InvoiceData:
    """Data structure for invoice information."""
    vendor_name: str
    vendor_address: str
    vendor_phone: str
    vendor_email: str
    vendor_tax_id: str

    bill_to_name: str
    bill_to_address: str

    invoice_number: str
    invoice_date: str
    due_date: str
    po_number: str
    terms: str

    currency: str
    line_items: List[Dict[str, Any]]
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    freight: float = 0.0

    payment_terms: str = ""
    bank_name: str = ""
    bank_account: str = ""
    bank_routing: str = ""
    notes: str = ""


class TestInvoiceGenerator:
    """Generate professional test PDF invoices for AP system testing."""

    def __init__(self, output_dir: str = "./test_invoices"):
        """Initialize the invoice generator."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Set up fonts and styles
        self._setup_fonts()
        self._setup_styles()

        # Sample data generators
        self.vendors = self._get_vendor_data()
        self.customers = self._get_customer_data()
        self.products = self._get_product_data()

    def _setup_fonts(self):
        """Set up custom fonts for professional appearance."""
        try:
            # Try to use standard fonts
            self.font_bold = "Helvetica-Bold"
            self.font_normal = "Helvetica"
            self.font_italic = "Helvetica-Oblique"
        except Exception:
            # Fallback to default fonts
            self.font_bold = "Helvetica-Bold"
            self.font_normal = "Helvetica"
            self.font_italic = "Helvetica-Oblique"

    def _setup_styles(self):
        """Set up paragraph styles."""
        self.styles = getSampleStyleSheet()

        # Custom styles
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#2c3e50')
        ))

        self.styles.add(ParagraphStyle(
            name='VendorName',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=6,
            textColor=HexColor('#34495e')
        ))

        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=HexColor('#7f8c8d')
        ))

        self.styles.add(ParagraphStyle(
            name='FooterText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=grey
        ))

    def _get_vendor_data(self) -> List[Dict[str, str]]:
        """Get sample vendor data."""
        return [
            {
                "name": "TechCorp Solutions Inc.",
                "address": "1234 Technology Boulevard, Suite 500\nSilicon Valley, CA 94025",
                "phone": "(555) 123-4567",
                "email": "billing@techcorp.com",
                "tax_id": "12-3456789",
                "bank": "First National Bank",
                "account": "1234567890",
                "routing": "021000021"
            },
            {
                "name": "Global Supply Chain LLC",
                "address": "789 Industrial Park Drive\nHouston, TX 77001",
                "phone": "(555) 987-6543",
                "email": "accounts@globalsupply.com",
                "tax_id": "87-6543210",
                "bank": "Commerce Bank",
                "account": "9876543210",
                "routing": "111000025"
            },
            {
                "name": "Premium Services Group",
                "address": "456 Executive Plaza\nNew York, NY 10001",
                "phone": "(555) 246-8135",
                "email": "finance@premiumservices.com",
                "tax_id": "45-6789012",
                "bank": "Manhattan Trust",
                "account": "5555555555",
                "routing": "026009593"
            }
        ]

    def _get_customer_data(self) -> List[Dict[str, str]]:
        """Get sample customer data."""
        return [
            {
                "name": "Innovation Labs Inc.",
                "address": "1000 Research Park Drive\nBoston, MA 02101"
            },
            {
                "name": "Manufacturing Pro Corp",
                "address": "2500 Factory Road\nChicago, IL 60601"
            },
            {
                "name": "Retail Solutions Ltd",
                "address": "345 Commerce Street\nLos Angeles, CA 90001"
            }
        ]

    def _get_product_data(self) -> List[Dict[str, Any]]:
        """Get sample product/service data."""
        return [
            {"sku": "TECH-001", "description": "Software License - Enterprise Edition", "unit_price": 5000.00},
            {"sku": "TECH-002", "description": "Cloud Infrastructure Services", "unit_price": 1250.00},
            {"sku": "TECH-003", "description": "Technical Support Package", "unit_price": 750.00},
            {"sku": "SUPP-001", "description": "Industrial Raw Materials - Steel", "unit_price": 45.50},
            {"sku": "SUPP-002", "description": "Electronic Components", "unit_price": 125.75},
            {"sku": "SUPP-003", "description": "Packaging Materials", "unit_price": 15.25},
            {"sku": "SERV-001", "description": "Consulting Services - Senior Consultant", "unit_price": 250.00},
            {"sku": "SERV-002", "description": "Project Management", "unit_price": 185.50},
            {"sku": "SERV-003", "description": "Training Services", "unit_price": 95.00}
        ]

    def generate_invoice_data(self, scenario: str = "standard") -> InvoiceData:
        """Generate invoice data for different scenarios."""
        vendor = random.choice(self.vendors)
        customer = random.choice(self.customers)

        # Generate dates
        invoice_date = datetime.now() - timedelta(days=random.randint(1, 30))
        due_date = invoice_date + timedelta(days=random.choice([30, 45, 60]))

        # Generate numbers
        invoice_number = f"{vendor['name'][:3].upper()}-{invoice_date.strftime('%Y%m')}-{random.randint(1000, 9999)}"
        po_number = f"PO-{invoice_date.strftime('%Y')}-{random.randint(10000, 99999)}"

        # Generate line items based on scenario
        if scenario == "standard":
            line_items = self._generate_standard_line_items(3)
        elif scenario == "complex":
            line_items = self._generate_complex_line_items(8)
        elif scenario == "minimal":
            line_items = self._generate_minimal_line_items(1)
        elif scenario == "high_value":
            line_items = self._generate_high_value_items(2)
        elif scenario == "many_items":
            line_items = self._generate_many_items(25)
        elif scenario == "error_scenarios":
            return self._generate_error_scenario(vendor, customer, invoice_date, due_date)
        else:
            line_items = self._generate_standard_line_items(5)

        # Calculate totals
        subtotal = sum(item['amount'] for item in line_items)
        tax_rate = random.choice([0.0, 0.06, 0.075, 0.08, 0.1])  # Different tax rates
        tax_amount = subtotal * tax_rate
        freight = random.choice([0, 25.00, 50.00, 100.00]) if scenario in ["complex", "high_value"] else 0
        total = subtotal + tax_amount + freight

        return InvoiceData(
            vendor_name=vendor["name"],
            vendor_address=vendor["address"],
            vendor_phone=vendor["phone"],
            vendor_email=vendor["email"],
            vendor_tax_id=vendor["tax_id"],
            bill_to_name=customer["name"],
            bill_to_address=customer["address"],
            invoice_number=invoice_number,
            invoice_date=invoice_date.strftime("%m/%d/%Y"),
            due_date=due_date.strftime("%m/%d/%Y"),
            po_number=po_number,
            terms=random.choice(["NET 30", "NET 45", "NET 60", "Due on Receipt"]),
            currency="USD",
            line_items=line_items,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            freight=freight,
            total=total,
            payment_terms=random.choice(["Payment due within 30 days", "Payment due within 45 days"]),
            bank_name=vendor["bank"],
            bank_account=vendor["account"],
            bank_routing=vendor["routing"],
            notes=self._generate_notes(scenario)
        )

    def _generate_standard_line_items(self, count: int) -> List[Dict[str, Any]]:
        """Generate standard line items."""
        items = []
        selected_products = random.sample(self.products, min(count, len(self.products)))

        for product in selected_products:
            quantity = random.randint(1, 10)
            unit_price = product["unit_price"]
            amount = quantity * unit_price

            items.append({
                "sku": product["sku"],
                "description": product["description"],
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount
            })

        return items

    def _generate_complex_line_items(self, count: int) -> List[Dict[str, Any]]:
        """Generate complex line items with varied quantities and prices."""
        items = []

        for i in range(count):
            product = random.choice(self.products)
            quantity = random.randint(1, 100)
            # Add some price variations
            price_variation = random.uniform(0.9, 1.1)
            unit_price = round(product["unit_price"] * price_variation, 2)
            amount = quantity * unit_price

            items.append({
                "sku": product["sku"],
                "description": f"{product['description']} (Batch {i+1})",
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount
            })

        return items

    def _generate_minimal_line_items(self, count: int) -> List[Dict[str, Any]]:
        """Generate minimal line items for edge case testing."""
        items = []

        for i in range(count):
            items.append({
                "sku": f"MIN-{i+1:03d}",
                "description": "Basic Service",
                "quantity": 1,
                "unit_price": 100.00,
                "amount": 100.00
            })

        return items

    def _generate_high_value_items(self, count: int) -> List[Dict[str, Any]]:
        """Generate high-value line items."""
        items = []

        for i in range(count):
            items.append({
                "sku": f"PREM-{i+1:03d}",
                "description": f"Premium Enterprise Solution {i+1}",
                "quantity": 1,
                "unit_price": random.randint(25000, 100000),
                "amount": 0  # Will be calculated
            })
            items[-1]["amount"] = items[-1]["quantity"] * items[-1]["unit_price"]

        return items

    def _generate_many_items(self, count: int) -> List[Dict[str, Any]]:
        """Generate many line items for stress testing."""
        items = []

        for i in range(count):
            product = random.choice(self.products)
            quantity = random.randint(1, 5)
            unit_price = round(random.uniform(10.00, 500.00), 2)
            amount = quantity * unit_price

            items.append({
                "sku": f"STRESS-{i+1:04d}",
                "description": f"{product['description']} - Variant {i+1}",
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount
            })

        return items

    def _generate_error_scenario(self, vendor: Dict, customer: Dict, invoice_date: datetime, due_date: datetime) -> InvoiceData:
        """Generate invoice with intentional errors for testing validation."""
        items = [
            {
                "sku": "",  # Missing SKU
                "description": "",  # Missing description
                "quantity": -1,  # Invalid quantity
                "unit_price": -100.00,  # Invalid price
                "amount": 100.00  # Mismatched amount
            }
        ]

        # Generate a PO number
        po_number = f"PO-{invoice_date.strftime('%Y')}-{random.randint(10000, 99999)}"

        return InvoiceData(
            vendor_name="",  # Missing vendor name
            vendor_address=vendor["address"],
            vendor_phone=vendor["phone"],
            vendor_email=vendor["email"],
            vendor_tax_id=vendor["tax_id"],
            bill_to_name=customer["name"],
            bill_to_address=customer["address"],
            invoice_number="",  # Missing invoice number
            invoice_date="13/45/2024",  # Invalid date
            due_date="02/30/2024",  # Invalid date
            po_number=po_number,
            terms="NET 30",
            currency="USD",
            line_items=items,
            subtotal=-1000.00,  # Negative subtotal
            tax_rate=0.08,
            tax_amount=-80.00,  # Negative tax
            total=-1080.00,  # Negative total
            payment_terms="Payment due within 30 days",
            bank_name=vendor["bank"],
            bank_account=vendor["account"],
            bank_routing=vendor["routing"],
            notes="This invoice contains intentional errors for testing validation logic."
        )

    def _generate_notes(self, scenario: str) -> str:
        """Generate appropriate notes for the invoice."""
        notes_map = {
            "standard": "Thank you for your business! Payment is due within the specified terms.",
            "complex": "Multiple shipment locations. Please reference packing slips for detailed breakdown.",
            "high_value": "This high-value invoice requires approval signature. Please contact our sales department.",
            "minimal": "Basic service invoice.",
            "many_items": "Bulk order with multiple line items. Please review carefully."
        }
        return notes_map.get(scenario, "Thank you for your business!")

    def create_pdf_invoice(self, invoice_data: InvoiceData, filename: str) -> str:
        """Create a PDF invoice from invoice data."""
        filepath = self.output_dir / filename
        doc = SimpleDocTemplate(str(filepath), pagesize=letter, topMargin=0.75*inch)

        # Build the document
        story = []

        # Add header
        story.extend(self._create_header(invoice_data))
        story.append(Spacer(1, 20))

        # Add addresses
        story.extend(self._create_addresses(invoice_data))
        story.append(Spacer(1, 20))

        # Add invoice details
        story.extend(self._create_invoice_details(invoice_data))
        story.append(Spacer(1, 20))

        # Add line items table
        story.extend(self._create_line_items_table(invoice_data))
        story.append(Spacer(1, 20))

        # Add totals
        story.extend(self._create_totals_section(invoice_data))
        story.append(Spacer(1, 20))

        # Add payment information
        story.extend(self._create_payment_info(invoice_data))

        # Add notes if any
        if invoice_data.notes:
            story.append(Spacer(1, 20))
            story.extend(self._create_notes_section(invoice_data))

        # Add barcode/QR code if available
        if BARCODE_AVAILABLE or QRCODE_AVAILABLE:
            story.append(Spacer(1, 20))
            story.extend(self._create_codes(invoice_data))

        # Build PDF
        doc.build(story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)

        return str(filepath)

    def _create_header(self, data: InvoiceData) -> List:
        """Create invoice header."""
        elements = []

        # Invoice title
        elements.append(Paragraph("INVOICE", self.styles['InvoiceTitle']))

        return elements

    def _create_addresses(self, data: InvoiceData) -> List:
        """Create vendor and customer address section."""
        elements = []

        # Create address table
        address_data = [
            [
                Paragraph(f"<b>{data.vendor_name}</b><br/>{data.vendor_address}<br/>"
                         f"Phone: {data.vendor_phone}<br/>Email: {data.vendor_email}<br/>"
                         f"Tax ID: {data.vendor_tax_id}", self.styles['Normal']),
                Paragraph(f"<b>Bill To:</b><br/>{data.bill_to_name}<br/>"
                         f"{data.bill_to_address}", self.styles['Normal'])
            ]
        ]

        address_table = Table(address_data, colWidths=[4*inch, 4*inch])
        address_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))

        elements.append(address_table)
        return elements

    def _create_invoice_details(self, data: InvoiceData) -> List:
        """Create invoice details section."""
        elements = []

        # Create details table
        details_data = [
            ["Invoice Number:", data.invoice_number, "Date:", data.invoice_date],
            ["PO Number:", data.po_number, "Due Date:", data.due_date],
            ["Terms:", data.terms, "Currency:", data.currency]
        ]

        details_table = Table(details_data, colWidths=[1.5*inch, 2*inch, 1*inch, 2*inch])
        details_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), self.font_bold),
            ('FONTNAME', (2, 0), (2, -1), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))

        elements.append(details_table)
        return elements

    def _create_line_items_table(self, data: InvoiceData) -> List:
        """Create line items table."""
        elements = []

        # Table headers
        headers = ["SKU", "Description", "Quantity", "Unit Price", "Amount"]

        # Table data
        table_data = [headers]

        for item in data.line_items:
            table_data.append([
                item.get("sku", ""),
                item.get("description", ""),
                str(item.get("quantity", 0)),
                f"${item.get('unit_price', 0):.2f}",
                f"${item.get('amount', 0):.2f}"
            ])

        # Create table
        table = Table(table_data, colWidths=[0.8*inch, 3.5*inch, 0.8*inch, 1.2*inch, 1.2*inch])

        # Style the table
        table.setStyle(TableStyle([
            # Header styling
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#ecf0f1')),

            # Data styling
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (1, -1), 'LEFT'),

            # Borders
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#bdc3c7')),
            ('LINEBELOW', (0, 0), (-1, 0), 2, HexColor('#34495e')),

            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)
        return elements

    def _create_totals_section(self, data: InvoiceData) -> List:
        """Create totals section."""
        elements = []

        # Calculate totals
        subtotal = data.subtotal
        tax_amount = data.tax_amount
        freight = data.freight
        total = data.total

        # Create totals table
        totals_data = [
            ["Subtotal:", f"${subtotal:.2f}"],
        ]

        if freight > 0:
            totals_data.append(["Freight:", f"${freight:.2f}"])

        if tax_amount > 0:
            totals_data.append([f"Tax ({data.tax_rate*100:.1f}%):", f"${tax_amount:.2f}"])

        totals_data.extend([
            ["", ""],
            ["<b>TOTAL:</b>", f"<b>${total:.2f}</b>"]
        ])

        totals_table = Table(totals_data, colWidths=[6*inch, 1.5*inch])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (0, -1), (0, -1), self.font_bold),
            ('FONTNAME', (1, -1), (1, -1), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -2), 'RIGHT'),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('LINEABOVE', (0, -2), (-1, -2), 1, black),
        ]))

        elements.append(totals_table)
        return elements

    def _create_payment_info(self, data: InvoiceData) -> List:
        """Create payment information section."""
        elements = []

        payment_info = (
            f"<b>Payment Information:</b><br/>"
            f"Bank: {data.bank_name}<br/>"
            f"Account Number: {data.bank_account}<br/>"
            f"Routing Number: {data.bank_routing}<br/>"
            f"<b>Terms:</b> {data.payment_terms}"
        )

        elements.append(Paragraph(payment_info, self.styles['SmallText']))
        return elements

    def _create_notes_section(self, data: InvoiceData) -> List:
        """Create notes section."""
        elements = []

        notes_data = [
            ["Notes:", data.notes]
        ]

        notes_table = Table(notes_data, colWidths=[0.8*inch, 6.7*inch])
        notes_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))

        elements.append(notes_table)
        return elements

    def _create_codes(self, data: InvoiceData) -> List:
        """Create barcode and QR code if libraries are available."""
        elements = []

        try:
            # Create temporary files for codes
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as barcode_file:
                if BARCODE_AVAILABLE:
                    # Generate barcode
                    code128 = barcode.get_barcode_class('code128')
                    barcode_image = code128(data.invoice_number, writer=ImageWriter())
                    barcode_image.save(barcode_file.name)

                    # Add to story
                    elements.append(Paragraph("Invoice Barcode:", self.styles['SmallText']))
                    # Note: In a full implementation, you'd convert the barcode image to ReportLab format

            if QRCODE_AVAILABLE:
                # Generate QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(f"INV:{data.invoice_number}|DATE:{data.invoice_date}|TOTAL:${data.total:.2f}")
                qr.make(fit=True)

                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as qr_file:
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    qr_img.save(qr_file.name)

                    # Add to story
                    elements.append(Paragraph("Payment QR Code:", self.styles['SmallText']))
                    # Note: In a full implementation, you'd convert the QR image to ReportLab format

        except Exception as e:
            # If code generation fails, continue without codes
            print(f"Warning: Could not generate codes: {e}")

        return elements

    def _add_header_footer(self, canvas_obj, doc):
        """Add header and footer to each page."""
        canvas_obj.saveState()

        # Footer
        canvas_obj.setFont(self.font_normal, 8)
        canvas_obj.setFillColor(grey)
        footer_text = f"Page {doc.page} | Generated by Test Invoice Generator | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        canvas_obj.drawString(inch, 0.5 * inch, footer_text)

        # Add confidentiality notice
        canvas_obj.setFont(self.font_italic, 8)
        confidentiality = "This is a test document for AP Intake & Validation system testing"
        canvas_obj.drawCentredString(4.25 * inch, 0.3 * inch, confidentiality)

        canvas_obj.restoreState()

    def generate_all_scenarios(self) -> List[str]:
        """Generate all test invoice scenarios."""
        scenarios = [
            "standard",
            "complex",
            "minimal",
            "high_value",
            "many_items",
            "error_scenarios"
        ]

        generated_files = []

        for scenario in scenarios:
            print(f"Generating {scenario} invoice...")

            # Generate invoice data
            invoice_data = self.generate_invoice_data(scenario)

            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_invoice_{scenario}_{timestamp}.pdf"

            # Create PDF
            filepath = self.create_pdf_invoice(invoice_data, filename)
            generated_files.append(filepath)

            print(f"  Created: {filepath}")

        return generated_files

    def generate_custom_invoice(self, custom_data: Optional[Dict[str, Any]] = None) -> str:
        """Generate a custom invoice with provided data."""
        if custom_data:
            # Convert custom data to InvoiceData object
            invoice_data = InvoiceData(**custom_data)
        else:
            # Generate random invoice
            invoice_data = self.generate_invoice_data("standard")

        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"custom_invoice_{timestamp}.pdf"

        # Create PDF
        filepath = self.create_pdf_invoice(invoice_data, filename)
        print(f"Created custom invoice: {filepath}")

        return filepath


def main():
    """Main function to run the invoice generator."""
    parser = argparse.ArgumentParser(
        description="Generate test PDF invoices for AP Intake & Validation system"
    )
    parser.add_argument(
        "--scenario",
        choices=["standard", "complex", "minimal", "high_value", "many_items", "error_scenarios", "all"],
        default="all",
        help="Invoice scenario to generate (default: all)"
    )
    parser.add_argument(
        "--output-dir",
        default="./test_invoices",
        help="Output directory for generated invoices (default: ./test_invoices)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of invoices to generate (default: 1)"
    )

    args = parser.parse_args()

    # Create generator
    generator = TestInvoiceGenerator(args.output_dir)

    print(f"Generating test invoices in: {args.output_dir}")
    print("=" * 60)

    generated_files = []

    if args.scenario == "all":
        # Generate all scenarios
        generated_files = generator.generate_all_scenarios()
    else:
        # Generate specific scenario multiple times
        for i in range(args.count):
            invoice_data = generator.generate_invoice_data(args.scenario)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_invoice_{args.scenario}_{i+1:02d}_{timestamp}.pdf"
            filepath = generator.create_pdf_invoice(invoice_data, filename)
            generated_files.append(filepath)

    print("=" * 60)
    print(f"Generated {len(generated_files)} test invoices:")
    for filepath in generated_files:
        print(f"  - {filepath}")

    print("\nThese test invoices are ready for use with the AP Intake & Validation system.")
    print("You can upload them through the web interface or API to test document parsing and validation.")


if __name__ == "__main__":
    main()