#!/usr/bin/env python3
"""
Test script to validate the generated PDF invoices with the AP Intake & Validation system.

This script:
1. Tests generated PDF invoices with the Docling service
2. Validates extraction results with the validation service
3. Provides confidence scores and validation results
"""

import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.services.docling_service import DoclingService
from app.services.validation_service import ValidationService
from app.core.config import settings


async def test_invoice_processing(pdf_path: str) -> Dict[str, Any]:
    """Test a single PDF invoice with the AP system."""
    print(f"\n{'='*60}")
    print(f"Testing: {pdf_path}")
    print(f"{'='*60}")

    # Initialize services
    docling_service = DoclingService()
    validation_service = ValidationService()

    try:
        # Step 1: Extract data using Docling
        print("1. Extracting data with Docling...")
        extraction_result = await docling_service.extract_from_file(pdf_path)

        print(f"   ✓ Extraction completed")
        print(f"   ✓ Overall confidence: {extraction_result.get('overall_confidence', 0):.2f}")
        print(f"   ✓ Pages processed: {extraction_result['metadata']['pages_processed']}")
        print(f"   ✓ Parser version: {extraction_result['metadata']['parser_version']}")

        # Display extracted header data
        header = extraction_result.get('header', {})
        print("\n   Extracted Header Data:")
        for key, value in header.items():
            print(f"      {key}: {value}")

        # Display extracted line items
        lines = extraction_result.get('lines', [])
        print(f"\n   Extracted Line Items: {len(lines)} found")
        for i, line in enumerate(lines[:3]):  # Show first 3 items
            print(f"      {i+1}. {line.get('description', 'No description')} - ${line.get('amount', 0):.2f}")
        if len(lines) > 3:
            print(f"      ... and {len(lines) - 3} more items")

        # Step 2: Validate extracted data
        print("\n2. Validating extracted data...")
        validation_result = await validation_service.validate_invoice(
            extraction_result=extraction_result,
            strict_mode=False
        )

        # Check if validation passed
        if validation_result.get('passed', False):
            print(f"   ✓ Validation PASSED")
        else:
            print(f"   ✗ Validation FAILED")

            # Show validation issues
            issues = validation_result.get('issues', [])
            if issues:
                print(f"   Issues found: {len(issues)}")
                for issue in issues[:5]:  # Show first 5 issues
                    print(f"      - {issue.get('code', 'Unknown')}: {issue.get('message', 'No message')}")
                if len(issues) > 5:
                    print(f"      ... and {len(issues) - 5} more issues")

        # Step 3: Show confidence breakdown
        confidence = extraction_result.get('confidence', {})
        header_confidence = confidence.get('header', {})
        lines_confidence = confidence.get('lines', [])

        print(f"\n3. Confidence Analysis:")
        print(f"   Header Confidence:")
        for field, conf in header_confidence.items():
            if field != 'overall':
                print(f"      {field}: {conf:.2f}")

        if lines_confidence:
            avg_line_confidence = sum(lines_confidence) / len(lines_confidence)
            print(f"   Average Line Item Confidence: {avg_line_confidence:.2f}")

        return {
            'file_path': pdf_path,
            'extraction_success': True,
            'extraction_result': extraction_result,
            'validation_passed': validation_result.get('passed', False),
            'validation_result': validation_result,
            'overall_confidence': extraction_result.get('overall_confidence', 0)
        }

    except Exception as e:
        print(f"   ✗ Error processing invoice: {str(e)}")
        return {
            'file_path': pdf_path,
            'extraction_success': False,
            'error': str(e),
            'overall_confidence': 0.0
        }


async def test_all_invoices(test_dir: str = "./test_invoices") -> List[Dict[str, Any]]:
    """Test all PDF invoices in the test directory."""
    test_dir_path = Path(test_dir)

    if not test_dir_path.exists():
        print(f"Test directory not found: {test_dir}")
        return []

    # Find all PDF files
    pdf_files = list(test_dir_path.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in: {test_dir}")
        return []

    print(f"Found {len(pdf_files)} PDF invoices to test:")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name}")

    # Test each invoice
    results = []
    for pdf_file in pdf_files:
        result = await test_invoice_processing(str(pdf_file))
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    successful_extractions = sum(1 for r in results if r.get('extraction_success', False))
    valid_invoices = sum(1 for r in results if r.get('validation_passed', False))

    print(f"Total invoices tested: {len(results)}")
    print(f"Successful extractions: {successful_extractions}/{len(results)} ({successful_extractions/len(results)*100:.1f}%)")
    print(f"Validated invoices: {valid_invoices}/{len(results)} ({valid_invoices/len(results)*100:.1f}%)")

    # Average confidence
    avg_confidence = sum(r.get('overall_confidence', 0) for r in results) / len(results)
    print(f"Average extraction confidence: {avg_confidence:.2f}")

    # Best and worst performers
    if results:
        best_result = max(results, key=lambda r: r.get('overall_confidence', 0))
        worst_result = min(results, key=lambda r: r.get('overall_confidence', 0))

        print(f"\nBest extraction:")
        print(f"  File: {Path(best_result['file_path']).name}")
        print(f"  Confidence: {best_result.get('overall_confidence', 0):.2f}")
        print(f"  Validated: {best_result.get('validation_passed', False)}")

        print(f"\nWorst extraction:")
        print(f"  File: {Path(worst_result['file_path']).name}")
        print(f"  Confidence: {worst_result.get('overall_confidence', 0):.2f}")
        print(f"  Validated: {worst_result.get('validation_passed', False)}")

    return results


async def main():
    """Main function to run the test."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test generated PDF invoices with AP Intake & Validation system"
    )
    parser.add_argument(
        "--file",
        help="Specific PDF file to test (default: test all in ./test_invoices)"
    )
    parser.add_argument(
        "--dir",
        default="./test_invoices",
        help="Directory containing PDF invoices to test (default: ./test_invoices)"
    )
    parser.add_argument(
        "--output",
        help="Save test results to JSON file"
    )

    args = parser.parse_args()

    print("AP Intake & Validation System - Invoice Testing")
    print("=" * 60)

    if args.file:
        # Test specific file
        results = [await test_invoice_processing(args.file)]
    else:
        # Test all files in directory
        results = await test_all_invoices(args.dir)

    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nTest results saved to: {output_path}")

    print(f"\nTesting completed!")


if __name__ == "__main__":
    asyncio.run(main())