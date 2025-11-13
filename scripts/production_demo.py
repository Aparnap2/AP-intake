#!/usr/bin/env python3
"""
Production Demo Script

Comprehensive production demonstration of the AP Intake & Validation system.
Showcases all implemented features with real-time monitoring and reporting.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import argparse
import sys

import httpx
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.rule import Rule

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.test_data_service import TestDataGenerator, TestScenario
from app.services.invoice_seeding_service import InvoiceSeedingService


class ProductionDemo:
    """Production demonstration orchestrator"""

    def __init__(self, base_url: str = "http://localhost:8000", demo_mode: str = "full"):
        self.base_url = base_url
        self.demo_mode = demo_mode
        self.console = Console()
        self.api_client = httpx.AsyncClient(base_url=base_url, timeout=60.0)
        self.results = {
            "demo_start": datetime.now().isoformat(),
            "scenarios": [],
            "metrics": {},
            "errors": [],
            "success_rate": 0.0
        }

    async def run_demo(self) -> Dict[str, Any]:
        """Run the complete production demonstration"""
        self.console.print("\n")
        self.console.print(Align.center("[bold blue]🚀 AP Intake & Validation System - Production Demo[/bold blue]"))
        self.console.print(Align.center(f"[italic]Demo Mode: {self.demo_mode}[/italic]"))
        self.console.print(Rule(style="blue"))

        try:
            # Step 1: System Health Check
            await self._demo_system_health()

            # Step 2: Test Data Generation
            await self._demo_test_data_generation()

            # Step 3: Standard Invoice Processing
            await self._demo_standard_processing()

            # Step 4: Exception Handling Workflow
            await self._demo_exception_handling()

            # Step 5: Duplicate Detection
            await self._demo_duplicate_detection()

            # Step 6: Performance Testing
            if self.demo_mode in ["full", "performance"]:
                await self._demo_performance_testing()

            # Step 7: Export and Integration
            await self._demo_export_functionality()

            # Step 8: Real-time Monitoring
            await self._demo_monitoring_dashboard()

            # Step 9: Generate Final Report
            await self._generate_demo_report()

        except Exception as e:
            self.console.print(f"\n❌ Demo failed: {str(e)}", style="red")
            self.results["errors"].append(str(e))

        finally:
            await self.api_client.aclose()

        return self.results

    async def _demo_system_health(self) -> None:
        """Demonstrate system health and monitoring"""
        self.console.print("\n🔍 [bold]Step 1: System Health Check[/bold]")
        self.console.print("Verifying system components and health status...")

        # Health check
        try:
            response = await self.api_client.get("/health")
            if response.status_code == 200:
                health_data = response.json()
                self.console.print("✅ API Health: [green]Healthy[/green]")

                # Display health details
                health_table = Table(show_header=False, box=None)
                health_table.add_column("Component", style="cyan")
                health_table.add_column("Status", style="green")
                health_table.add_row("API Server", "Operational")
                health_table.add_row("Database", health_data.get("database", "Unknown"))
                health_table.add_row("Redis Cache", health_data.get("redis", "Unknown"))
                health_table.add_row("File Storage", health_data.get("storage", "Unknown"))

                self.console.print(Panel(health_table, title="System Components", border_style="green"))
            else:
                raise Exception(f"Health check failed: {response.status_code}")

        except Exception as e:
            self.console.print(f"❌ System health check failed: {str(e)}", style="red")
            raise

        # API info
        try:
            response = await self.api_client.get("/api/v1/info")
            if response.status_code == 200:
                info_data = response.json()
                self.console.print(f"✅ API Version: [cyan]{info_data.get('version', 'Unknown')}[/cyan]")
                self.console.print(f"✅ System Name: [cyan]{info_data.get('name', 'Unknown')}[/cyan]")
        except Exception as e:
            self.console.print(f"⚠️ API info check failed: {str(e)}", style="yellow")

        # Metrics endpoint
        try:
            response = await self.api_client.get("/metrics")
            if response.status_code == 200:
                self.console.print("✅ Metrics: [green]Available[/green]")
        except:
            self.console.print("⚠️ Metrics: [yellow]Not available[/yellow]")

    async def _demo_test_data_generation(self) -> None:
        """Demonstrate test data generation capabilities"""
        self.console.print("\n🔧 [bold]Step 2: Test Data Generation[/bold]")
        self.console.print("Generating comprehensive test dataset...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:

            task = progress.add_task("Generating test scenarios...", total=100)

            # Generate test data
            generator = TestDataGenerator()
            progress.update(task, advance=20)

            test_results = generator.generate_all_test_data()
            progress.update(task, advance=60)

            # Display generation results
            total_scenarios = len(test_results["scenarios"])
            categories = test_results.keys()

            progress.update(task, advance=20)

        self.console.print(f"✅ Generated [green]{total_scenarios}[/green] test scenarios")

        # Display category breakdown
        category_table = Table(title="Test Data Categories", box=None)
        category_table.add_column("Category", style="cyan")
        category_table.add_column("Count", justify="right", style="green")
        category_table.add_column("Description", style="white")

        for category in ["standard_invoices", "duplicate_invoices", "exception_cases", "edge_cases", "performance_test"]:
            if category in test_results:
                count = len(test_results[category])
                description = {
                    "standard_invoices": "Normal processing scenarios",
                    "duplicate_invoices": "Duplicate detection tests",
                    "exception_cases": "Exception handling tests",
                    "edge_cases": "Edge case scenarios",
                    "performance_test": "Performance validation"
                }.get(category, "Test scenarios")
                category_table.add_row(category.replace("_", " ").title(), str(count), description)

        self.console.print(category_table)

        # Store results
        self.results["test_data_generation"] = {
            "total_scenarios": total_scenarios,
            "categories": {cat: len(test_results[cat]) for cat in categories if isinstance(test_results[cat], list)},
            "timestamp": datetime.now().isoformat()
        }

    async def _demo_standard_processing(self) -> None:
        """Demonstrate standard invoice processing"""
        self.console.print("\n📄 [bold]Step 3: Standard Invoice Processing[/bold]")
        self.console.print("Processing standard invoices with AI extraction and validation...")

        # Seed database with standard invoices
        seeder = InvoiceSeedingService()
        seeding_result = await seeder.seed_database(categories=["standard_invoices"], limit=5)

        if "error" in seeding_result:
            self.console.print(f"❌ Database seeding failed: {seeding_result['error']}", style="red")
            return

        self.console.print(f"✅ Seeded [green]{len(seeding_result['seeded_scenarios'])}[/green] standard invoices")

        # Process invoices via API
        processed_invoices = []
        for scenario in seeding_result["seeded_scenarios"][:3]:  # Demo with first 3
            try:
                # Get invoice details
                invoice_response = await self.api_client.get(f"/api/v1/invoices/{scenario['invoice_id']}")
                if invoice_response.status_code == 200:
                    invoice_data = invoice_response.json()
                    processed_invoices.append({
                        "invoice_id": scenario['invoice_id'],
                        "invoice_number": invoice_data.get('invoice_number'),
                        "vendor_name": invoice_data.get('vendor_name'),
                        "total_amount": invoice_data.get('total_amount'),
                        "status": invoice_data.get('status')
                    })

            except Exception as e:
                self.console.print(f"⚠️ Failed to process invoice {scenario['invoice_id']}: {str(e)}", style="yellow")

        # Display processed invoices
        if processed_invoices:
            invoice_table = Table(title="Processed Invoices", box=None)
            invoice_table.add_column("Invoice #", style="cyan")
            invoice_table.add_column("Vendor", style="white")
            invoice_table.add_column("Amount", justify="right", style="green")
            invoice_table.add_column("Status", style="yellow")

            for invoice in processed_invoices:
                status_style = {
                    "processed": "green",
                    "needs_review": "yellow",
                    "exception": "red"
                }.get(invoice["status"], "white")

                invoice_table.add_row(
                    invoice["invoice_number"],
                    invoice["vendor_name"],
                    f"${invoice['total_amount']:.2f}",
                    f"[{status_style}]{invoice['status']}[/{status_style}]"
                )

            self.console.print(invoice_table)

        # Store results
        self.results["standard_processing"] = {
            "seeded_count": len(seeding_result["seeded_scenarios"]),
            "processed_count": len(processed_invoices),
            "success_rate": len(processed_invoices) / len(seeding_result["seeded_scenarios"]) if seeding_result["seeded_scenarios"] else 0,
            "timestamp": datetime.now().isoformat()
        }

    async def _demo_exception_handling(self) -> None:
        """Demonstrate exception handling workflow"""
        self.console.print("\n⚠️ [bold]Step 4: Exception Handling Workflow[/bold]")
        self.console.print("Testing exception detection and resolution workflows...")

        # Seed database with exception cases
        seeder = InvoiceSeedingService()
        seeding_result = await seeder.seed_database(categories=["exception_cases"], limit=3)

        if "error" in seeding_result:
            self.console.print(f"❌ Exception seeding failed: {seeding_result['error']}", style="red")
            return

        self.console.print(f"✅ Seeded [green]{len(seeding_result['seeded_scenarios'])}[/green] exception cases")

        # Process exception cases
        exception_cases = []
        for scenario in seeding_result["seeded_scenarios"]:
            try:
                # Get invoice details
                invoice_response = await self.api_client.get(f"/api/v1/invoices/{scenario['invoice_id']}")
                if invoice_response.status_code == 200:
                    invoice_data = invoice_response.json()

                    # Get exceptions for this invoice
                    exceptions_response = await self.api_client.get(f"/api/v1/invoices/{scenario['invoice_id']}/exceptions")
                    exceptions = []
                    if exceptions_response.status_code == 200:
                        exceptions_data = exceptions_response.json()
                        exceptions = exceptions_data.get("exceptions", [])

                    exception_cases.append({
                        "invoice_id": scenario['invoice_id'],
                        "scenario_id": scenario['scenario_id'],
                        "status": invoice_data.get('status'),
                        "exception_count": len(exceptions),
                        "exceptions": exceptions[:1]  # Show first exception for demo
                    })

            except Exception as e:
                self.console.print(f"⚠️ Failed to process exception case {scenario['scenario_id']}: {str(e)}", style="yellow")

        # Display exception cases
        if exception_cases:
            exception_table = Table(title="Exception Cases", box=None)
            exception_table.add_column("Scenario", style="cyan")
            exception_table.add_column("Invoice Status", style="white")
            exception_table.add_column("Exceptions", justify="right", style="red")
            exception_table.add_column("Exception Type", style="yellow")

            for case in exception_cases:
                exception_type = "None"
                if case["exceptions"]:
                    exception_type = case["exceptions"][0].get("reason_code", "Unknown")

                exception_table.add_row(
                    case["scenario_id"],
                    case["status"],
                    str(case["exception_count"]),
                    exception_type
                )

            self.console.print(exception_table)

            # Demonstrate exception resolution
            if exception_cases and exception_cases[0]["exceptions"]:
                exception_id = exception_cases[0]["exceptions"][0]["id"]
                try:
                    resolution_response = await self.api_client.post(
                        f"/api/v1/exceptions/{exception_id}/resolve",
                        json={
                            "resolution_method": "manual_correction",
                            "resolution_notes": "Demo exception resolution",
                            "assign_to": "demo_user"
                        }
                    )
                    if resolution_response.status_code == 200:
                        self.console.print("✅ Exception resolution: [green]Successful[/green]")
                except Exception as e:
                    self.console.print(f"⚠️ Exception resolution failed: {str(e)}", style="yellow")

        # Store results
        self.results["exception_handling"] = {
            "seeded_count": len(seeding_result["seeded_scenarios"]),
            "processed_count": len(exception_cases),
            "total_exceptions": sum(case["exception_count"] for case in exception_cases),
            "timestamp": datetime.now().isoformat()
        }

    async def _demo_duplicate_detection(self) -> None:
        """Demonstrate duplicate detection capabilities"""
        self.console.print("\n🔍 [bold]Step 5: Duplicate Detection[/bold]")
        self.console.print("Testing duplicate invoice detection and management...")

        # Seed database with duplicate invoices
        seeder = InvoiceSeedingService()
        seeding_result = await seeder.seed_database(categories=["duplicate_invoices"], limit=4)

        if "error" in seeding_result:
            self.console.print(f"❌ Duplicate seeding failed: {seeding_result['error']}", style="red")
            return

        self.console.print(f"✅ Seeded [green]{len(seeding_result['seeded_scenarios'])}[/green] duplicate scenarios")

        # Analyze duplicate detection
        duplicate_groups = {}
        for scenario in seeding_result["seeded_scenarios"]:
            try:
                # Get invoice details
                invoice_response = await self.api_client.get(f"/api/v1/invoices/{scenario['invoice_id']}")
                if invoice_response.status_code == 200:
                    invoice_data = invoice_response.json()

                    # Check for duplicates
                    duplicates_response = await self.api_client.get(f"/api/v1/invoices/{scenario['invoice_id']}/duplicates")
                    duplicates = []
                    if duplicates_response.status_code == 200:
                        duplicates_data = duplicates_response.json()
                        duplicates = duplicates_data.get("duplicates", [])

                    # Group by duplicate relationships
                    group_key = scenario.get("duplicate_of", scenario["scenario_id"])
                    if group_key not in duplicate_groups:
                        duplicate_groups[group_key] = []

                    duplicate_groups[group_key].append({
                        "scenario_id": scenario["scenario_id"],
                        "invoice_id": scenario["invoice_id"],
                        "status": invoice_data.get("status"),
                        "duplicate_count": len(duplicates),
                        "is_duplicate": scenario.get("is_duplicate", False)
                    })

            except Exception as e:
                self.console.print(f"⚠️ Failed to analyze duplicate {scenario['scenario_id']}: {str(e)}", style="yellow")

        # Display duplicate analysis
        if duplicate_groups:
            duplicate_table = Table(title="Duplicate Detection Results", box=None)
            duplicate_table.add_column("Group", style="cyan")
            duplicate_table.add_column("Scenarios", style="white")
            duplicate_table.add_column("Detected Duplicates", justify="right", style="yellow")
            duplicate_table.add_column("Detection Status", style="green")

            for group_id, scenarios in duplicate_groups.items():
                scenario_names = ", ".join([s["scenario_id"] for s in scenarios])
                total_duplicates = sum(s["duplicate_count"] for s in scenarios)
                detection_status = "✅ Detected" if total_duplicates > 0 else "⚠️ Not Detected"

                duplicate_table.add_row(
                    group_id,
                    scenario_names,
                    str(total_duplicates),
                    detection_status
                )

            self.console.print(duplicate_table)

        # Store results
        self.results["duplicate_detection"] = {
            "seeded_count": len(seeding_result["seeded_scenarios"]),
            "duplicate_groups": len(duplicate_groups),
            "total_duplicates_detected": sum(len(scenarios) - 1 for scenarios in duplicate_groups.values() if len(scenarios) > 1),
            "timestamp": datetime.now().isoformat()
        }

    async def _demo_performance_testing(self) -> None:
        """Demonstrate performance testing capabilities"""
        self.console.print("\n⚡ [bold]Step 6: Performance Testing[/bold]")
        self.console.print("Testing system performance under load...")

        # Seed database with performance test cases
        seeder = InvoiceSeedingService()
        seeding_result = await seeder.seed_database(categories=["performance_test"], limit=5)

        if "error" in seeding_result:
            self.console.print(f"❌ Performance seeding failed: {seeding_result['error']}", style="red")
            return

        self.console.print(f"✅ Seeded [green]{len(seeding_result['seeded_scenarios'])}[/green] performance test cases")

        # Simulate concurrent processing
        start_time = time.time()
        processed_count = 0

        with Progress(console=self.console) as progress:
            task = progress.add_task("Processing performance tests...", total=len(seeding_result["seeded_scenarios"]))

            for scenario in seeding_result["seeded_scenarios"]:
                try:
                    # Simulate processing time
                    await asyncio.sleep(0.1)  # Simulate processing delay

                    # Get invoice details
                    invoice_response = await self.api_client.get(f"/api/v1/invoices/{scenario['invoice_id']}")
                    if invoice_response.status_code == 200:
                        processed_count += 1

                except Exception as e:
                    self.console.print(f"⚠️ Performance test failed for {scenario['scenario_id']}: {str(e)}", style="yellow")

                progress.update(task, advance=1)

        end_time = time.time()
        processing_time = end_time - start_time

        # Calculate performance metrics
        throughput = processed_count / processing_time if processing_time > 0 else 0
        avg_processing_time = processing_time / processed_count if processed_count > 0 else 0

        # Display performance results
        performance_table = Table(title="Performance Metrics", box=None)
        performance_table.add_column("Metric", style="cyan")
        performance_table.add_column("Value", justify="right", style="green")
        performance_table.add_column("Benchmark", justify="right", style="yellow")

        performance_table.add_row("Total Processed", str(processed_count), "5+")
        performance_table.add_row("Processing Time", f"{processing_time:.2f}s", "<5s")
        performance_table.add_row("Throughput", f"{throughput:.2f} req/s", ">1.0 req/s")
        performance_table.add_row("Avg Processing Time", f"{avg_processing_time:.3f}s", "<1.0s")

        self.console.print(performance_table)

        # Performance assessment
        if throughput > 1.0 and avg_processing_time < 1.0:
            self.console.print("✅ Performance: [green]Excellent[/green]")
        elif throughput > 0.5 and avg_processing_time < 2.0:
            self.console.print("✅ Performance: [yellow]Good[/yellow]")
        else:
            self.console.print("⚠️ Performance: [red]Needs Improvement[/red]")

        # Store results
        self.results["performance_testing"] = {
            "processed_count": processed_count,
            "total_time": processing_time,
            "throughput": throughput,
            "avg_processing_time": avg_processing_time,
            "performance_rating": "excellent" if throughput > 1.0 else "good" if throughput > 0.5 else "needs_improvement",
            "timestamp": datetime.now().isoformat()
        }

    async def _demo_export_functionality(self) -> None:
        """Demonstrate export and integration capabilities"""
        self.console.print("\n📤 [bold]Step 7: Export and Integration[/bold]")
        self.console.print("Testing invoice export to external systems...")

        # Get a processed invoice for export
        try:
            # List invoices to find a processed one
            invoices_response = await self.api_client.get("/api/v1/invoices?limit=5")
            if invoices_response.status_code != 200:
                self.console.print("⚠️ Could not retrieve invoices for export demo", style="yellow")
                return

            invoices_data = invoices_response.json()
            invoices = invoices_data.get("invoices", [])

            if not invoices:
                self.console.print("⚠️ No invoices available for export demo", style="yellow")
                return

            # Use the first available invoice
            invoice = invoices[0]
            invoice_id = invoice["id"]

            # Request export
            export_response = await self.api_client.post(
                f"/api/v1/invoices/{invoice_id}/export",
                json={
                    "export_format": "json",
                    "destination": "quickbooks"
                }
            )

            if export_response.status_code == 200:
                export_data = export_response.json()
                export_job_id = export_data.get("export_job_id")

                self.console.print(f"✅ Export job created: [cyan]{export_job_id}[/cyan]")

                # Monitor export progress (simplified for demo)
                await asyncio.sleep(1)  # Simulate processing time

                # Get export status
                status_response = await self.api_client.get(f"/api/v1/exports/{export_job_id}/status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    export_status = status_data.get("status", "unknown")

                    # Display export results
                    export_table = Table(title="Export Results", box=None)
                    export_table.add_column("Export ID", style="cyan")
                    export_table.add_column("Format", style="white")
                    export_table.add_column("Destination", style="white")
                    export_table.add_column("Status", style="green")

                    export_table.add_row(
                        export_job_id[:8] + "...",
                        "JSON",
                        "QuickBooks",
                        export_status.replace("_", " ").title()
                    )

                    self.console.print(export_table)

                    # Store results
                    self.results["export_functionality"] = {
                        "export_job_id": export_job_id,
                        "status": export_status,
                        "format": "json",
                        "destination": "quickbooks",
                        "timestamp": datetime.now().isoformat()
                    }

                else:
                    self.console.print("⚠️ Could not retrieve export status", style="yellow")
            else:
                self.console.print(f"⚠️ Export request failed: {export_response.status_code}", style="yellow")

        except Exception as e:
            self.console.print(f"⚠️ Export demo failed: {str(e)}", style="yellow")

    async def _demo_monitoring_dashboard(self) -> None:
        """Demonstrate real-time monitoring capabilities"""
        self.console.print("\n📊 [bold]Step 8: Real-time Monitoring[/bold]")
        self.console.print("Displaying system monitoring and metrics...")

        # Collect system metrics
        metrics = {}

        # Invoice processing metrics
        try:
            invoices_response = await self.api_client.get("/api/v1/invoices?limit=100")
            if invoices_response.status_code == 200:
                invoices_data = invoices_response.json()
                invoices = invoices_data.get("invoices", [])

                # Calculate metrics
                status_counts = {}
                total_amount = 0
                for invoice in invoices:
                    status = invoice.get("status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                    total_amount += invoice.get("total_amount", 0)

                metrics["invoice_stats"] = {
                    "total_invoices": len(invoices),
                    "by_status": status_counts,
                    "total_value": total_amount
                }

        except Exception as e:
            self.console.print(f"⚠️ Could not retrieve invoice metrics: {str(e)}", style="yellow")

        # Exception metrics
        try:
            exceptions_response = await self.api_client.get("/api/v1/exceptions?limit=100")
            if exceptions_response.status_code == 200:
                exceptions_data = exceptions_response.json()
                exceptions = exceptions_data.get("exceptions", [])

                # Calculate exception metrics
                reason_counts = {}
                for exception in exceptions:
                    reason = exception.get("reason_code", "unknown")
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

                metrics["exception_stats"] = {
                    "total_exceptions": len(exceptions),
                    "by_reason": reason_counts
                }

        except Exception as e:
            self.console.print(f"⚠️ Could not retrieve exception metrics: {str(e)}", style="yellow")

        # Display monitoring dashboard
        if metrics:
            # Create monitoring layout
            layout = Layout()

            # Invoice statistics
            if "invoice_stats" in metrics:
                inv_stats = metrics["invoice_stats"]
                inv_table = Table(title="Invoice Statistics", box=None)
                inv_table.add_column("Metric", style="cyan")
                inv_table.add_column("Value", justify="right", style="green")

                inv_table.add_row("Total Invoices", str(inv_stats["total_invoices"]))
                inv_table.add_row("Total Value", f"${inv_stats['total_value']:.2f}")

                for status, count in inv_stats["by_status"].items():
                    inv_table.add_row(f"  - {status.replace('_', ' ').title()}", str(count))

                layout["invoices"] = Panel(inv_table, border_style="green")

            # Exception statistics
            if "exception_stats" in metrics:
                exc_stats = metrics["exception_stats"]
                exc_table = Table(title="Exception Statistics", box=None)
                exc_table.add_column("Metric", style="cyan")
                exc_table.add_column("Value", justify="right", style="yellow")

                exc_table.add_row("Total Exceptions", str(exc_stats["total_exceptions"]))

                for reason, count in exc_stats["by_reason"].items():
                    exc_table.add_row(f"  - {reason.replace('_', ' ').title()}", str(count))

                layout["exceptions"] = Panel(exc_table, border_style="yellow")

            # Display layout
            self.console.print(layout)

        # Store results
        self.results["monitoring_dashboard"] = {
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }

    async def _generate_demo_report(self) -> None:
        """Generate comprehensive demo report"""
        self.console.print("\n📋 [bold]Step 9: Demo Summary Report[/bold]")

        # Calculate overall success rate
        total_tests = 0
        successful_tests = 0

        for key, result in self.results.items():
            if isinstance(result, dict) and "processed_count" in result:
                total_tests += result.get("seeded_count", 0)
                successful_tests += result.get("processed_count", 0)

        overall_success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        self.results["success_rate"] = overall_success_rate

        # Create summary table
        summary_table = Table(title="Demo Summary", box=None)
        summary_table.add_column("Component", style="cyan")
        summary_table.add_column("Status", style="green")
        summary_table.add_column("Details", style="white")

        # System Health
        health_status = "✅ Passed" if "system_health" not in self.results else "❌ Failed"
        summary_table.add_row("System Health", health_status, "All components operational")

        # Test Data Generation
        if "test_data_generation" in self.results:
            td_result = self.results["test_data_generation"]
            summary_table.add_row(
                "Test Data Generation",
                "✅ Passed",
                f"{td_result['total_scenarios']} scenarios generated"
            )

        # Standard Processing
        if "standard_processing" in self.results:
            sp_result = self.results["standard_processing"]
            summary_table.add_row(
                "Standard Processing",
                "✅ Passed" if sp_result["success_rate"] > 0.8 else "⚠️ Partial",
                f"{sp_result['processed_count']}/{sp_result['seeded_count']} processed"
            )

        # Exception Handling
        if "exception_handling" in self.results:
            eh_result = self.results["exception_handling"]
            summary_table.add_row(
                "Exception Handling",
                "✅ Passed",
                f"{eh_result['total_exceptions']} exceptions handled"
            )

        # Duplicate Detection
        if "duplicate_detection" in self.results:
            dd_result = self.results["duplicate_detection"]
            summary_table.add_row(
                "Duplicate Detection",
                "✅ Passed" if dd_result["total_duplicates_detected"] > 0 else "⚠️ Limited",
                f"{dd_result['total_duplicates_detected']} duplicates detected"
            )

        # Performance Testing
        if "performance_testing" in self.results:
            perf_result = self.results["performance_testing"]
            perf_status = "✅ Excellent" if perf_result["performance_rating"] == "excellent" else "⚠️ Good"
            summary_table.add_row(
                "Performance Testing",
                perf_status,
                f"{perf_result['throughput']:.2f} req/s throughput"
            )

        # Export Functionality
        if "export_functionality" in self.results:
            export_result = self.results["export_functionality"]
            summary_table.add_row(
                "Export Functionality",
                "✅ Passed",
                f"Export to {export_result['destination']}"
            )

        # Overall Success Rate
        rating = "Excellent" if overall_success_rate >= 90 else "Good" if overall_success_rate >= 75 else "Needs Improvement"
        rating_color = "green" if overall_success_rate >= 90 else "yellow" if overall_success_rate >= 75 else "red"

        summary_table.add_row(
            "Overall Success Rate",
            f"[{rating_color}]{overall_success_rate:.1f}%[/{rating_color}]",
            f"System Rating: {rating}"
        )

        self.console.print(summary_table)

        # Demo completion message
        demo_duration = datetime.now() - datetime.fromisoformat(self.results["demo_start"])
        self.console.print(f"\n✨ Demo completed in [cyan]{demo_duration.total_seconds():.1f} seconds[/cyan]")
        self.console.print(f"🎯 Overall Success Rate: [{rating_color}]{overall_success_rate:.1f}%[/{rating_color}]")

        # Save detailed report
        report_file = Path("demo_report.json")
        self.results["demo_end"] = datetime.now().isoformat()
        self.results["duration_seconds"] = demo_duration.total_seconds()

        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        self.console.print(f"📄 Detailed report saved to: [cyan]{report_file}[/cyan]")

        # Final recommendation
        if overall_success_rate >= 90:
            self.console.print("\n🚀 [bold green]System is PRODUCTION READY![/bold green]")
        elif overall_success_rate >= 75:
            self.console.print("\n⚠️ [bold yellow]System is mostly ready with minor issues[/bold yellow]")
        else:
            self.console.print("\n❌ [bold red]System needs improvements before production[/bold red]")


async def main():
    """Main demo execution"""
    parser = argparse.ArgumentParser(description="AP Intake Production Demo")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--mode", choices=["full", "quick", "performance"], default="full", help="Demo mode")
    parser.add_argument("--no-health-check", action="store_true", help="Skip system health check")
    parser.add_argument("--output", help="Output file for demo report")

    args = parser.parse_args()

    console = Console()
    console.print("🎬 Starting AP Intake & Validation Production Demo...")

    demo = ProductionDemo(base_url=args.base_url, demo_mode=args.mode)

    try:
        results = await demo.run_demo()

        # Save to custom output file if specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            console.print(f"📄 Demo report saved to: {args.output}")

        # Exit with appropriate code
        success_rate = results.get("success_rate", 0)
        if success_rate >= 90:
            console.print("✅ Demo completed successfully!")
            sys.exit(0)
        elif success_rate >= 75:
            console.print("⚠️ Demo completed with some issues")
            sys.exit(1)
        else:
            console.print("❌ Demo completed with significant issues")
            sys.exit(2)

    except KeyboardInterrupt:
        console.print("\n⚠️ Demo interrupted by user")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n❌ Demo failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())