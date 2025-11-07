"""
Sample document fixtures for testing document extraction and validation.
"""

import base64
from pathlib import Path
from typing import Dict, List, Any

# Sample PDF content (minimal valid PDF)
SAMPLE_PDF_CONTENT = base64.b64decode("""
JVBERi0xLjQKJeLjz9MKNCAwIG9iago8PC9MZW5ndGggNSAwIFIvRmlsdGVyIC9GbGF0ZURl
Y29kZT4+CnN0cmVhbQp4nE0KwCQABAwANyuzc3JTS1BIAQEAZHvZCwplbmRzdHJlYW0KZW5k
b2JqCjUgMCBvYmoKMTUKZW5kb2JqCjIgMCBvYmoKPDwvVHlwZSAvUGFnZSAvUGFyZW50IDMgMCBS
IC9SZXNvdXJjZXMgPDwvRm9udCA8PC9GMSAxIDAgUj4+Pj4gL01lZGlhQm94IFswIDAgNjEyIDc5
Ml0gL0NvbnRlbnRzIDQgMCBSPj4KZW5kb2JqCjMgMCBvYmoKPDwvVHlwZSAvUGFnZXMgL0NvdW50
IDEgL0tpZHMgWzIgMCBSXT4+CmVuZG9iago2IDAgb2JqCjw8L1R5cGUgL0ZvbnQgL1N1YnR5cGUg
L1R5cGUxIC9CYXNlRm9udCAvSGVsdmV0aWNhPj4KZW5kb2JqCjEgMCBvYmoKPDwvVHlwZSAvQ2F0
YWxvZyAvUGFnZXMgMyAwIFIgL1RpdGxlICjFj9GAr9aV0CkgPj4KZW5kb2JqCnhyZWYKMCA3CjAw
MDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAxMCAwMDAwMCBuIAowMDAwMDAwMDc0IDAwMDAwIG4g
CjAwMDAwMDAyMDYgMDAwMDAgbiAKMDAwMDAwMDM4NyAwMDAwMCBuIAowMDAwMDAwNDM2IDAwMDAw
IG4gCjAwMDAwMDA1ODUgMDAwMDAgbiAKdHJhaWxlcgo8PC9TaXplIDcgL1Jvb3QgMSAwIFIgL0lu
Zm8gNiAwIFI+PgpzdGFydHhyZWYKNzI0CiUlRU9GCg==
""")


class SampleDocuments:
    """Collection of sample documents for testing."""

    @staticmethod
    def get_simple_invoice() -> bytes:
        """Get a simple PDF invoice content."""
        return SAMPLE_PDF_CONTENT

    @staticmethod
    def get_text_invoice_content() -> str:
        """Get text representation of invoice for testing."""
        return """
        INVOICE

        Vendor: Test Vendor Inc
        Address: 123 Test Street, Test City, TX 75001
        Phone: (555) 123-4567
        Email: billing@testvendor.com

        Bill To:
        Test Company Inc
        456 Company Ave
        Business City, NY 10001

        Invoice Number: INV-2024-001
        Invoice Date: 01/15/2024
        Due Date: 02/15/2024
        PO Number: PO-2024-001

        Item Description           Quantity   Unit Price   Amount
        ----------------------------------------------------------
        Test Product 1           2          $500.00      $1,000.00
        Test Product 2           1          $250.00      $250.00
        Test Service              10         $100.00      $1,000.00

        ----------------------------------------------------------
        Subtotal:                             $2,250.00
        Tax (10%):                            $225.00
        Total:                                $2,475.00

        Payment Terms: NET 30
        Thank you for your business!
        """

    @staticmethod
    def get_complex_invoice_content() -> str:
        """Get complex invoice content with multiple line items and taxes."""
        return """
        ABC SUPPLY COMPANY
        789 Industrial Blvd
        Manufacturing Park, MI 48001

        INVOICE

        Invoice #: ABC-2024-12345
        Date: January 20, 2024
        Due: February 19, 2024

        Customer ID: CUST-789
        PO #: PO-2024-98765

        Bill To:
        Global Manufacturing Inc
        321 Factory Road
        Industrial City, MI 48501
        Attn: Accounts Payable

        Ship To:
        Global Manufacturing Inc
        321 Factory Road
        Industrial City, MI 48501
        Attn: Receiving Department

        ITEM | DESCRIPTION | QTY | UNIT | UNIT PRICE | AMOUNT
        -----|-------------|-----|------|------------|--------
        1001 | Steel Rods 10mm | 500 | EA | $5.25 | $2,625.00
        1002 | Steel Rods 20mm | 250 | EA | $8.75 | $2,187.50
        2001 | Industrial Bolts M12 | 1000 | BX | $15.50 | $15,500.00
        2002 | Industrial Bolts M16 | 500 | BX | $22.75 | $11,375.00
        3001 | Welding Supplies | 25 | KIT | $125.00 | $3,125.00
        4001 | Safety Equipment | 10 | SET | $89.99 | $899.90
        5001 | Tools & Accessories | 5 | PKG | $45.50 | $227.50

        Subtotal: $35,939.90
        Freight: $250.00
        Handling: $75.00
        Subtotal after charges: $36,264.90

        Tax:
        State Tax (6%): $2,175.89
        Local Tax (2%): $725.30
        Total Tax: $2,901.19

        TOTAL INVOICE: $39,166.09

        Terms: NET 45 DAYS
        Late Payment: 1.5% per month
        """

    @staticmethod
    def get_invalid_invoice_content() -> str:
        """Get invalid invoice content for negative testing."""
        return """
        This is not a valid invoice document.
        It lacks proper structure and required fields.
        No vendor name, no invoice number, no amounts.
        Just random text content.
        """

    @staticmethod
    def get_invoice_with_errors() -> str:
        """Get invoice content with common extraction errors."""
        return """
        Invoice #:
        Date: 32/13/2024  # Invalid date
        Vendor:

        Total: -$100.00  # Negative amount

        Line Items:
        (No line items listed)

        Tax: abc  # Invalid tax amount
        """

    @staticmethod
    def get_invoice_variations() -> List[Dict[str, Any]]:
        """Get various invoice formats for testing robustness."""
        return [
            {
                "name": "Standard Invoice",
                "content": SampleDocuments.get_text_invoice_content(),
                "expected_fields": {
                    "vendor_name": "Test Vendor Inc",
                    "invoice_no": "INV-2024-001",
                    "total": 2475.00
                }
            },
            {
                "name": "Complex Invoice",
                "content": SampleDocuments.get_complex_invoice_content(),
                "expected_fields": {
                    "vendor_name": "ABC SUPPLY COMPANY",
                    "invoice_no": "ABC-2024-12345",
                    "total": 39166.09
                }
            },
            {
                "name": "Invalid Invoice",
                "content": SampleDocuments.get_invalid_invoice_content(),
                "expected_fields": {}
            },
            {
                "name": "Invoice with Errors",
                "content": SampleDocuments.get_invoice_with_errors(),
                "expected_fields": {}
            }
        ]

    @staticmethod
    def create_temp_invoice_file(content: str, suffix: str = ".txt") -> Path:
        """Create temporary invoice file for testing."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=suffix) as f:
            f.write(content)
            return Path(f.name)

    @staticmethod
    def create_temp_pdf_file() -> Path:
        """Create temporary PDF file for testing."""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(SAMPLE_PDF_CONTENT)
            return Path(f.name)


class ValidationTestCases:
    """Test cases for validation scenarios."""

    @staticmethod
    def get_valid_invoices() -> List[Dict[str, Any]]:
        """Get valid invoice test cases."""
        return [
            {
                "name": "Simple Valid Invoice",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor Inc",
                        "invoice_no": "INV-001",
                        "invoice_date": "2024-01-15",
                        "due_date": "2024-02-15",
                        "currency": "USD",
                        "subtotal": 1000.00,
                        "tax": 100.00,
                        "total": 1100.00,
                    },
                    "lines": [
                        {
                            "description": "Test Product",
                            "quantity": 2,
                            "unit_price": 500.00,
                            "amount": 1000.00
                        }
                    ],
                    "overall_confidence": 0.95
                },
                "expected_result": "passed"
            },
            {
                "name": "High Value Invoice",
                "data": {
                    "header": {
                        "vendor_name": "Premium Vendor LLC",
                        "invoice_no": "PREM-2024-001",
                        "invoice_date": "2024-01-20",
                        "total": 50000.00,
                        "currency": "USD",
                    },
                    "lines": [
                        {
                            "description": "Premium Service",
                            "quantity": 1,
                            "unit_price": 50000.00,
                            "amount": 50000.00
                        }
                    ],
                    "overall_confidence": 0.98
                },
                "expected_result": "passed"
            }
        ]

    @staticmethod
    def get_invalid_invoices() -> List[Dict[str, Any]]:
        """Get invalid invoice test cases."""
        return [
            {
                "name": "Missing Required Fields",
                "data": {
                    "header": {
                        "vendor_name": "",  # Missing
                        "invoice_no": None,  # Missing
                        "total": 1000.00,
                    },
                    "lines": [],
                    "overall_confidence": 0.8
                },
                "expected_errors": [
                    "MISSING_REQUIRED_FIELD",
                    "NO_LINE_ITEMS"
                ]
            },
            {
                "name": "Invalid Amounts",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_no": "INV-001",
                        "total": -100.00,  # Negative
                        "subtotal": 1000.00,
                        "tax": 100.00,
                    },
                    "lines": [
                        {
                            "description": "Test Product",
                            "amount": 1000.00
                        }
                    ],
                    "overall_confidence": 0.9
                },
                "expected_errors": [
                    "TOTAL_MISMATCH",
                    "INVALID_AMOUNT"
                ]
            },
            {
                "name": "Date Format Issues",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_no": "INV-001",
                        "invoice_date": "32/13/2024",  # Invalid
                        "due_date": "2024-02-30",  # Invalid
                        "total": 1000.00,
                    },
                    "lines": [
                        {
                            "description": "Test Product",
                            "amount": 1000.00
                        }
                    ],
                    "overall_confidence": 0.7
                },
                "expected_errors": [
                    "INVALID_FIELD_FORMAT"
                ]
            }
        ]

    @staticmethod
    def get_boundary_cases() -> List[Dict[str, Any]]:
        """Get boundary test cases."""
        return [
            {
                "name": "Minimum Amount",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_no": "INV-001",
                        "total": 0.01,  # Minimum
                    },
                    "lines": [
                        {
                            "description": "Test Product",
                            "amount": 0.01
                        }
                    ],
                    "overall_confidence": 0.8
                }
            },
            {
                "name": "Maximum Amount",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_no": "INV-001",
                        "total": 1000000.00,  # Maximum
                    },
                    "lines": [
                        {
                            "description": "Test Product",
                            "amount": 1000000.00
                        }
                    ],
                    "overall_confidence": 0.9
                }
            },
            {
                "name": "Many Line Items",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_no": "INV-001",
                        "total": 1000.00,
                    },
                    "lines": [
                        {
                            "description": f"Test Product {i+1}",
                            "amount": 1.00
                        } for i in range(1000)  # 1000 line items
                    ],
                    "overall_confidence": 0.7
                }
            }
        ]


class PerformanceTestScenarios:
    """Performance testing scenarios."""

    @staticmethod
    def get_load_test_scenarios() -> List[Dict[str, Any]]:
        """Get load test scenarios."""
        return [
            {
                "name": "Concurrent Processing",
                "concurrent_users": 10,
                "requests_per_user": 5,
                "duration_seconds": 60,
                "expected_avg_response_time": 2000,  # ms
                "expected_success_rate": 0.95
            },
            {
                "name": "Peak Load",
                "concurrent_users": 50,
                "requests_per_user": 10,
                "duration_seconds": 120,
                "expected_avg_response_time": 5000,  # ms
                "expected_success_rate": 0.90
            },
            {
                "name": "Stress Test",
                "concurrent_users": 100,
                "requests_per_user": 20,
                "duration_seconds": 300,
                "expected_avg_response_time": 10000,  # ms
                "expected_success_rate": 0.80
            }
        ]

    @staticmethod
    def get_volume_test_scenarios() -> List[Dict[str, Any]]:
        """Get volume test scenarios."""
        return [
            {
                "name": "Small Batch",
                "invoice_count": 10,
                "expected_duration_seconds": 30
            },
            {
                "name": "Medium Batch",
                "invoice_count": 100,
                "expected_duration_seconds": 300
            },
            {
                "name": "Large Batch",
                "invoice_count": 1000,
                "expected_duration_seconds": 1800
            }
        ]