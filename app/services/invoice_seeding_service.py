"""
Invoice Seeding Service

Database seeding service for loading test invoices and their metadata
into the AP Intake & Validation system for testing and demonstration purposes.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import get_async_session
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ingestion import IngestionJob, IngestionStatus
from app.models.validation import ValidationSession, ValidationRule
from app.models.extraction import FieldExtraction, ExtractionSession
from app.models.schemas import PreparedBill
from app.services.test_data_service import TestScenario, TestDataGenerator


class InvoiceSeedingService:
    """Service for seeding test invoice data into the database"""

    def __init__(self):
        self.test_data_dir = Path("tests/fixtures/test_data")
        self.invoice_files_dir = Path("tests/fixtures/test_invoices")
        self.expected_results_dir = Path("tests/fixtures/expected_results")

    async def load_test_scenarios(self) -> Dict[str, TestScenario]:
        """Load test scenarios from metadata files"""
        scenarios = {}

        metadata_file = self.test_data_dir / "test_scenarios.json"
        if not metadata_file.exists():
            print(f"❌ Test metadata file not found: {metadata_file}")
            print("Run test data generation first: python -m app.services.test_data_service")
            return scenarios

        with open(metadata_file, 'r') as f:
            data = json.load(f)

        if "scenarios" not in data:
            print("❌ No scenarios found in test metadata")
            return scenarios

        for scenario_id, scenario_data in data["scenarios"].items():
            # Convert dates back to datetime objects
            expected_extraction = scenario_data.get("expected_extraction", {})
            if "invoice_date" in expected_extraction:
                if isinstance(expected_extraction["invoice_date"], str):
                    expected_extraction["invoice_date"] = datetime.fromisoformat(expected_extraction["invoice_date"])
            if "due_date" in expected_extraction:
                if isinstance(expected_extraction["due_date"], str):
                    expected_extraction["due_date"] = datetime.fromisoformat(expected_extraction["due_date"])

            # Create TestScenario object
            scenario = TestScenario(
                scenario_id=scenario_data["scenario_id"],
                name=scenario_data["name"],
                description=scenario_data["description"],
                category=scenario_data["category"],
                expected_extraction=expected_extraction,
                expected_validation=scenario_data["expected_validation"],
                test_tags=scenario_data["test_tags"],
                file_name=scenario_data["file_name"],
                is_duplicate=scenario_data.get("is_duplicate", False),
                duplicate_of=scenario_data.get("duplicate_of"),
                expected_exception_code=scenario_data.get("expected_exception_code")
            )

            scenarios[scenario_id] = scenario

        print(f"✅ Loaded {len(scenarios)} test scenarios from metadata")
        return scenarios

    async def seed_database(self, categories: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """Seed database with test invoice data"""
        print("🌱 Starting database seeding...")

        # Load test scenarios
        scenarios = await self.load_test_scenarios()
        if not scenarios:
            return {"error": "No test scenarios found"}

        # Filter by categories if specified
        if categories:
            filtered_scenarios = {
                scenario_id: scenario
                for scenario_id, scenario in scenarios.items()
                if scenario.category in categories
            }
            print(f"📋 Filtering by categories: {categories}")
        else:
            filtered_scenarios = scenarios

        # Apply limit if specified
        if limit:
            filtered_scenarios = dict(list(filtered_scenarios.items())[:limit])
            print(f"📊 Limiting to {limit} scenarios")

        print(f"🎯 Seeding {len(filtered_scenarios)} scenarios into database")

        results = {
            "seeded_scenarios": [],
            "failed_scenarios": [],
            "statistics": {
                "total_scenarios": len(filtered_scenarios),
                "by_category": {},
                "by_status": {}
            }
        }

        async for session in get_async_session():
            try:
                # Seed each scenario
                for scenario_id, scenario in filtered_scenarios.items():
                    try:
                        result = await self._seed_scenario(session, scenario)
                        if result["success"]:
                            results["seeded_scenarios"].append({
                                "scenario_id": scenario_id,
                                "invoice_id": result["invoice_id"],
                                "category": scenario.category
                            })

                            # Update statistics
                            category = scenario.category
                            results["statistics"]["by_category"][category] = \
                                results["statistics"]["by_category"].get(category, 0) + 1

                            status = result.get("status", "unknown")
                            results["statistics"]["by_status"][status] = \
                                results["statistics"]["by_status"].get(status, 0) + 1

                        else:
                            results["failed_scenarios"].append({
                                "scenario_id": scenario_id,
                                "error": result["error"]
                            })

                    except Exception as e:
                        print(f"❌ Failed to seed scenario {scenario_id}: {str(e)}")
                        results["failed_scenarios"].append({
                            "scenario_id": scenario_id,
                            "error": str(e)
                        })

                await session.commit()

            except Exception as e:
                await session.rollback()
                print(f"❌ Database seeding failed: {str(e)}")
                return {"error": f"Database seeding failed: {str(e)}"}

        print(f"✅ Database seeding complete:")
        print(f"   • Successfully seeded: {len(results['seeded_scenarios'])}")
        print(f"   • Failed: {len(results['failed_scenarios'])}")

        # Print category breakdown
        if results["statistics"]["by_category"]:
            print(f"\n📊 By Category:")
            for category, count in results["statistics"]["by_category"].items():
                print(f"   • {category}: {count}")

        return results

    async def _seed_scenario(self, session: AsyncSession, scenario: TestScenario) -> Dict[str, Any]:
        """Seed a single test scenario into the database"""
        try:
            # Check if scenario already exists
            existing = await session.execute(
                select(Invoice).where(Invoice.invoice_number == scenario.expected_extraction.get("invoice_number", ""))
            )
            if existing.scalar_one_or_none():
                return {
                    "success": False,
                    "error": "Invoice number already exists",
                    "invoice_id": None
                }

            # Create ingestion job
            ingestion_job = IngestionJob(
                id=uuid.uuid4(),
                filename=scenario.file_name,
                file_path=str(self.invoice_files_dir / scenario.file_name),
                file_size=0,  # Would calculate actual file size
                file_hash=f"hash_{scenario.scenario_id}",  # Would calculate actual hash
                source_type="test_seeding",
                source_reference=scenario.scenario_id,
                status=IngestionStatus.COMPLETED,
                metadata={
                    "scenario_id": scenario.scenario_id,
                    "category": scenario.category,
                    "test_tags": scenario.test_tags,
                    "expected_validation": scenario.expected_validation,
                    "is_duplicate": scenario.is_duplicate,
                    "duplicate_of": scenario.duplicate_of,
                    "expected_exception_code": scenario.expected_exception_code
                }
            )
            session.add(ingestion_job)

            # Create extraction session
            extraction_session = ExtractionSession(
                id=uuid.uuid4(),
                ingestion_job_id=ingestion_job.id,
                status="completed",
                confidence_score=0.95,
                processing_time_ms=150.0,
                llm_patching_enabled=True,
                llm_patching_applied=False,
                extraction_metadata={
                    "extraction_method": "test_seeding",
                    "confidence_threshold": 0.8,
                    "field_count": len(scenario.expected_extraction)
                }
            )
            session.add(extraction_session)

            # Create invoice record
            expected_extraction = scenario.expected_extraction
            invoice = Invoice(
                id=uuid.uuid4(),
                ingestion_job_id=ingestion_job.id,
                extraction_session_id=extraction_session.id,
                invoice_number=expected_extraction.get("invoice_number", f"TEST-{scenario.scenario_id}"),
                vendor_name=expected_extraction.get("vendor_name", "Test Vendor"),
                total_amount=Decimal(str(expected_extraction.get("total_amount", 0.0))),
                invoice_date=expected_extraction.get("invoice_date", datetime.now()),
                due_date=expected_extraction.get("due_date", datetime.now() + timedelta(days=30)),
                currency=expected_extraction.get("currency", "USD"),
                status=self._determine_invoice_status(scenario),
                metadata={
                    "scenario_id": scenario.scenario_id,
                    "category": scenario.category,
                    "test_description": scenario.description,
                    "line_items_count": expected_extraction.get("line_items_count", 1),
                    "expected_validation": scenario.expected_validation
                }
            )
            session.add(invoice)

            # Create field extractions
            for field_name, field_value in expected_extraction.items():
                if field_name not in ["invoice_date", "due_date"]:  # Handle dates separately
                    field_extraction = FieldExtraction(
                        id=uuid.uuid4(),
                        extraction_session_id=extraction_session.id,
                        field_name=field_name,
                        field_value=str(field_value),
                        confidence_score=0.95,
                        bbox_coordinates=[0, 0, 100, 100],  # Mock coordinates
                        extraction_metadata={
                            "scenario_id": scenario.scenario_id,
                            "extraction_method": "test_seeding"
                        }
                    )
                    session.add(field_extraction)

            # Create validation session
            validation_session = ValidationSession(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                status="completed" if scenario.expected_validation.get("structural_pass", True) else "failed",
                validation_rules_applied=self._get_validation_rules_for_scenario(scenario),
                validation_metadata={
                    "scenario_id": scenario.scenario_id,
                    "expected_results": scenario.expected_validation,
                    "validation_timestamp": datetime.now().isoformat()
                }
            )
            session.add(validation_session)

            # Add validation rule results
            for rule_name, expected_pass in scenario.expected_validation.items():
                if rule_name.endswith("_pass"):
                    rule = ValidationRule(
                        id=uuid.uuid4(),
                        validation_session_id=validation_session.id,
                        rule_name=rule_name.replace("_pass", ""),
                        rule_type="structural" if "structural" in rule_name else "math" if "math" in rule_name else "business",
                        passed=expected_pass,
                        confidence_score=0.9 if expected_pass else 0.1,
                        rule_metadata={
                            "scenario_id": scenario.scenario_id,
                            "expected_result": expected_pass
                        }
                    )
                    session.add(rule)

            return {
                "success": True,
                "invoice_id": str(invoice.id),
                "status": invoice.status.value,
                "validation_status": validation_session.status
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "invoice_id": None
            }

    def _determine_invoice_status(self, scenario: TestScenario) -> InvoiceStatus:
        """Determine invoice status based on scenario expectations"""
        expected_validation = scenario.expected_validation

        # Check if validation should pass
        validation_passed = all(
            expected_validation.get(key, True)
            for key in ["structural_pass", "math_pass", "business_rules_pass", "duplicate_pass"]
        )

        if not validation_passed:
            if scenario.expected_exception_code:
                return InvoiceStatus.EXCEPTION
            else:
                return InvoiceStatus.NEEDS_REVIEW

        # Check for duplicate
        if scenario.is_duplicate or not expected_validation.get("duplicate_pass", True):
            return InvoiceStatus.DUPLICATE

        # Normal processing
        return InvoiceStatus.PROCESSED

    def _get_validation_rules_for_scenario(self, scenario: TestScenario) -> List[str]:
        """Get list of validation rules that should be applied to this scenario"""
        rules = ["structural_validation", "math_validation", "business_rules_validation", "duplicate_detection"]

        # Add category-specific rules
        if scenario.category == "exception_cases":
            rules.append("exception_handling")
        elif scenario.category == "edge_cases":
            rules.append("edge_case_validation")
        elif scenario.category == "performance_test":
            rules.append("performance_validation")

        return rules

    async def clear_test_data(self) -> Dict[str, Any]:
        """Clear all test data from database"""
        print("🧹 Clearing test data from database...")

        results = {
            "deleted_invoices": 0,
            "deleted_ingestion_jobs": 0,
            "deleted_extraction_sessions": 0,
            "deleted_validation_sessions": 0,
            "deleted_field_extractions": 0,
            "deleted_validation_rules": 0
        }

        async for session in get_async_session():
            try:
                # Delete validation rules first (foreign key dependency)
                from sqlalchemy import delete
                from app.models.validation import ValidationRule
                stmt = delete(ValidationRule).where(
                    ValidationRule.validation_session_id.in_(
                        select(ValidationSession.id).where(
                            ValidationSession.invoice_id.in_(
                                select(Invoice.id).where(
                                    Invoice.metadata["scenario_id"].isnot(None)
                                )
                            )
                        )
                    )
                )
                result = await session.execute(stmt)
                results["deleted_validation_rules"] = result.rowcount

                # Delete validation sessions
                from app.models.validation import ValidationSession
                stmt = delete(ValidationSession).where(
                    ValidationSession.invoice_id.in_(
                        select(Invoice.id).where(
                            Invoice.metadata["scenario_id"].isnot(None)
                        )
                    )
                )
                result = await session.execute(stmt)
                results["deleted_validation_sessions"] = result.rowcount

                # Delete field extractions
                from app.models.extraction import FieldExtraction
                stmt = delete(FieldExtraction).where(
                    FieldExtraction.extraction_session_id.in_(
                        select(ExtractionSession.id).where(
                            ExtractionSession.ingestion_job_id.in_(
                                select(IngestionJob.id).where(
                                    IngestionJob.metadata["scenario_id"].isnot(None)
                                )
                            )
                        )
                    )
                )
                result = await session.execute(stmt)
                results["deleted_field_extractions"] = result.rowcount

                # Delete extraction sessions
                from app.models.extraction import ExtractionSession
                stmt = delete(ExtractionSession).where(
                    ExtractionSession.ingestion_job_id.in_(
                        select(IngestionJob.id).where(
                            IngestionJob.metadata["scenario_id"].isnot(None)
                        )
                    )
                )
                result = await session.execute(stmt)
                results["deleted_extraction_sessions"] = result.rowcount

                # Delete invoices
                from app.models.invoice import Invoice
                stmt = delete(Invoice).where(Invoice.metadata["scenario_id"].isnot(None))
                result = await session.execute(stmt)
                results["deleted_invoices"] = result.rowcount

                # Delete ingestion jobs
                from app.models.ingestion import IngestionJob
                stmt = delete(IngestionJob).where(IngestionJob.metadata["scenario_id"].isnot(None))
                result = await session.execute(stmt)
                results["deleted_ingestion_jobs"] = result.rowcount

                await session.commit()

            except Exception as e:
                await session.rollback()
                print(f"❌ Failed to clear test data: {str(e)}")
                return {"error": f"Failed to clear test data: {str(e)}"}

        print(f"✅ Test data cleared:")
        for item_type, count in results.items():
            print(f"   • {item_type}: {count}")

        return results

    async def get_seeding_statistics(self) -> Dict[str, Any]:
        """Get statistics about current test data in database"""
        async for session in get_async_session():
            try:
                # Count invoices by scenario category
                category_query = select(Invoice.metadata["category"]).where(
                    Invoice.metadata["scenario_id"].isnot(None)
                )
                result = await session.execute(category_query)
                categories = [row[0] for row in result.fetchall()]

                # Count invoices by status
                status_query = select(Invoice.status).where(
                    Invoice.metadata["scenario_id"].isnot(None)
                )
                result = await session.execute(status_query)
                statuses = [row[0] for row in result.fetchall()]

                # Total counts
                total_invoices = len(categories)
                total_ingestion_jobs = await session.scalar(
                    select(IngestionJob).where(IngestionJob.metadata["scenario_id"].isnot(None)).count()
                )
                total_validation_sessions = await session.scalar(
                    select(ValidationSession).where(
                        ValidationSession.invoice_id.in_(
                            select(Invoice.id).where(Invoice.metadata["scenario_id"].isnot(None))
                        )
                    ).count()
                )

                # Category breakdown
                category_counts = {}
                for category in categories:
                    category_counts[category] = category_counts.get(category, 0) + 1

                # Status breakdown
                status_counts = {}
                for status in statuses:
                    status_counts[status.value] = status_counts.get(status.value, 0) + 1

                return {
                    "total_test_invoices": total_invoices,
                    "total_ingestion_jobs": total_ingestion_jobs,
                    "total_validation_sessions": total_validation_sessions,
                    "categories": category_counts,
                    "statuses": status_counts,
                    "last_updated": datetime.now().isoformat()
                }

            except Exception as e:
                print(f"❌ Failed to get statistics: {str(e)}")
                return {"error": f"Failed to get statistics: {str(e)}"}


async def seed_test_data(categories: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """Main function to seed test data"""
    seeder = InvoiceSeedingService()
    return await seeder.seed_database(categories, limit)


async def clear_test_data() -> Dict[str, Any]:
    """Main function to clear test data"""
    seeder = InvoiceSeedingService()
    return await seeder.clear_test_data()


async def get_seeding_stats() -> Dict[str, Any]:
    """Main function to get seeding statistics"""
    seeder = InvoiceSeedingService()
    return await seeder.get_seeding_statistics()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Invoice Seeding Service")
    parser.add_argument("action", choices=["seed", "clear", "stats", "generate-and-seed"])
    parser.add_argument("--categories", nargs="+", help="Categories to seed")
    parser.add_argument("--limit", type=int, help="Limit number of scenarios to seed")

    args = parser.parse_args()

    if args.action == "generate-and-seed":
        print("🔧 Generating test data first...")
        from app.services.test_data_service import generate_test_data
        asyncio.run(generate_test_data())
        print("\n🌱 Seeding database...")
        result = asyncio.run(seed_test_data(args.categories, args.limit))
    elif args.action == "seed":
        result = asyncio.run(seed_test_data(args.categories, args.limit))
    elif args.action == "clear":
        result = asyncio.run(clear_test_data())
    elif args.action == "stats":
        result = asyncio.run(get_seeding_stats())

    if isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))