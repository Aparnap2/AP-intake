#!/usr/bin/env python3
"""
Demo Report Generator

Automated report generation for AP Intake & Validation system demonstrations.
Generates comprehensive HTML and PDF reports with charts, metrics, and analysis.
"""

import json
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

import httpx
from jinja2 import Environment, FileSystemLoader, Template
from rich.console import Console

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.invoice_seeding_service import InvoiceSeedingService


class DemoReportGenerator:
    """Generate comprehensive demo reports"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.console = Console()
        self.api_client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self.report_data = {
            "generated_at": datetime.now().isoformat(),
            "system_info": {},
            "test_data": {},
            "processing_metrics": {},
            "exception_analysis": {},
            "performance_metrics": {},
            "export_statistics": {},
            "recommendations": []
        }

    async def generate_comprehensive_report(self, output_dir: str = "reports") -> Dict[str, Any]:
        """Generate comprehensive demo report"""
        self.console.print("📊 Generating comprehensive demo report...")

        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Collect all report data
        await self._collect_system_info()
        await self._collect_test_data_metrics()
        await self._collect_processing_metrics()
        await self._collect_exception_analysis()
        await self._collect_performance_metrics()
        await self._collect_export_statistics()

        # Generate recommendations
        self._generate_recommendations()

        # Generate HTML report
        html_report = await self._generate_html_report()
        html_file = output_path / "demo_report.html"
        with open(html_file, 'w') as f:
            f.write(html_report)

        # Generate JSON report
        json_file = output_path / "demo_data.json"
        with open(json_file, 'w') as f:
            json.dump(self.report_data, f, indent=2, default=str)

        # Generate summary report
        summary = self._generate_summary()
        summary_file = output_path / "demo_summary.txt"
        with open(summary_file, 'w') as f:
            f.write(summary)

        self.console.print(f"✅ Reports generated:")
        self.console.print(f"   • HTML Report: {html_file}")
        self.console.print(f"   • JSON Data: {json_file}")
        self.console.print(f"   • Summary: {summary_file}")

        return {
            "html_report": str(html_file),
            "json_report": str(json_file),
            "summary_report": str(summary_file),
            "data": self.report_data
        }

    async def _collect_system_info(self) -> None:
        """Collect system information"""
        self.console.print("🔍 Collecting system information...")

        try:
            # API health
            health_response = await self.api_client.get("/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                self.report_data["system_info"]["health"] = health_data

            # API info
            info_response = await self.api_client.get("/api/v1/info")
            if info_response.status_code == 200:
                info_data = info_response.json()
                self.report_data["system_info"]["api_info"] = info_data

            # Database statistics
            seeder = InvoiceSeedingService()
            db_stats = await seeder.get_seeding_statistics()
            self.report_data["system_info"]["database_stats"] = db_stats

        except Exception as e:
            self.console.print(f"⚠️ Failed to collect system info: {str(e)}")
            self.report_data["system_info"]["error"] = str(e)

    async def _collect_test_data_metrics(self) -> None:
        """Collect test data metrics"""
        self.console.print("📋 Collecting test data metrics...")

        try:
            # Load test metadata
            test_metadata_file = Path("tests/fixtures/test_data/test_scenarios.json")
            if test_metadata_file.exists():
                with open(test_metadata_file, 'r') as f:
                    test_data = json.load(f)

                # Analyze test scenarios
                categories = {}
                total_scenarios = len(test_data.get("scenarios", {}))

                for scenario_id, scenario in test_data.get("scenarios", {}).items():
                    category = scenario.get("category", "unknown")
                    if category not in categories:
                        categories[category] = {"count": 0, "tags": set()}
                    categories[category]["count"] += 1
                    categories[category]["tags"].update(scenario.get("test_tags", []))

                # Convert sets to lists for JSON serialization
                for category in categories:
                    categories[category]["tags"] = list(categories[category]["tags"])

                self.report_data["test_data"] = {
                    "total_scenarios": total_scenarios,
                    "categories": categories,
                    "metadata_loaded": True
                }
            else:
                self.report_data["test_data"] = {"error": "Test metadata file not found"}

        except Exception as e:
            self.console.print(f"⚠️ Failed to collect test data metrics: {str(e)}")
            self.report_data["test_data"]["error"] = str(e)

    async def _collect_processing_metrics(self) -> None:
        """Collect invoice processing metrics"""
        self.console.print("📄 Collecting processing metrics...")

        try:
            # Get invoice statistics
            invoices_response = await self.api_client.get("/api/v1/invoices?limit=1000")
            if invoices_response.status_code == 200:
                invoices_data = invoices_response.json()
                invoices = invoices_data.get("invoices", [])

                # Analyze invoices
                status_counts = {}
                vendor_counts = {}
                total_amount = 0
                currency_counts = {}
                processing_times = []

                for invoice in invoices:
                    # Status analysis
                    status = invoice.get("status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1

                    # Vendor analysis
                    vendor = invoice.get("vendor_name", "unknown")
                    vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1

                    # Financial analysis
                    total_amount += invoice.get("total_amount", 0)

                    # Currency analysis
                    currency = invoice.get("currency", "USD")
                    currency_counts[currency] = currency_counts.get(currency, 0) + 1

                    # Processing time (if available)
                    if "processing_time_ms" in invoice:
                        processing_times.append(invoice["processing_time_ms"])

                # Calculate statistics
                avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0

                self.report_data["processing_metrics"] = {
                    "total_invoices": len(invoices),
                    "status_distribution": status_counts,
                    "top_vendors": dict(sorted(vendor_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
                    "total_value": total_amount,
                    "average_invoice_value": total_amount / len(invoices) if invoices else 0,
                    "currency_distribution": currency_counts,
                    "average_processing_time_ms": avg_processing_time,
                    "processing_sample_size": len(processing_times)
                }

        except Exception as e:
            self.console.print(f"⚠️ Failed to collect processing metrics: {str(e)}")
            self.report_data["processing_metrics"]["error"] = str(e)

    async def _collect_exception_analysis(self) -> None:
        """Collect exception analysis data"""
        self.console.print("⚠️ Collecting exception analysis...")

        try:
            # Get exception statistics
            exceptions_response = await self.api_client.get("/api/v1/exceptions?limit=1000")
            if exceptions_response.status_code == 200:
                exceptions_data = exceptions_response.json()
                exceptions = exceptions_data.get("exceptions", [])

                # Analyze exceptions
                reason_counts = {}
                resolution_counts = {}
                severity_counts = {}
                aging_analysis = {"0-1d": 0, "1-7d": 0, "7-30d": 0, "30d+": 0}

                for exception in exceptions:
                    # Reason analysis
                    reason = exception.get("reason_code", "unknown")
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

                    # Resolution analysis
                    resolution = exception.get("resolution_status", "unresolved")
                    resolution_counts[resolution] = resolution_counts.get(resolution, 0) + 1

                    # Severity analysis
                    severity = exception.get("severity", "medium")
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1

                    # Aging analysis
                    created_at = exception.get("created_at")
                    if created_at:
                        created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        age_days = (datetime.now().replace(tzinfo=created_date.tzinfo) - created_date).days

                        if age_days <= 1:
                            aging_analysis["0-1d"] += 1
                        elif age_days <= 7:
                            aging_analysis["1-7d"] += 1
                        elif age_days <= 30:
                            aging_analysis["7-30d"] += 1
                        else:
                            aging_analysis["30d+"] += 1

                self.report_data["exception_analysis"] = {
                    "total_exceptions": len(exceptions),
                    "reason_distribution": reason_counts,
                    "resolution_distribution": resolution_counts,
                    "severity_distribution": severity_counts,
                    "aging_analysis": aging_analysis,
                    "resolution_rate": (resolution_counts.get("resolved", 0) / len(exceptions) * 100) if exceptions else 0
                }

        except Exception as e:
            self.console.print(f"⚠️ Failed to collect exception analysis: {str(e)}")
            self.report_data["exception_analysis"]["error"] = str(e)

    async def _collect_performance_metrics(self) -> None:
        """Collect performance metrics"""
        self.console.print("⚡ Collecting performance metrics...")

        try:
            # Get metrics endpoint data
            metrics_response = await self.api_client.get("/metrics")
            if metrics_response.status_code == 200:
                # Parse Prometheus metrics
                metrics_text = metrics_response.text
                performance_data = self._parse_prometheus_metrics(metrics_text)

                self.report_data["performance_metrics"] = performance_data
            else:
                # Use simulated performance data if metrics endpoint not available
                self.report_data["performance_metrics"] = {
                    "http_requests_total": "simulated",
                    "http_request_duration_seconds": "simulated",
                    "note": "Metrics endpoint not available, using simulated data"
                }

        except Exception as e:
            self.console.print(f"⚠️ Failed to collect performance metrics: {str(e)}")
            self.report_data["performance_metrics"]["error"] = str(e)

    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """Parse Prometheus metrics text"""
        metrics = {}
        lines = metrics_text.split('\n')

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                if '{' in line and '}' in line:
                    # Metric with labels
                    metric_part, value_part = line.split(' ', 1)
                    metric_name = metric_part.split('{')[0]
                    if metric_name not in metrics:
                        metrics[metric_name] = []
                    metrics[metric_name].append({
                        "full_line": line,
                        "value": float(value_part)
                    })
                else:
                    # Simple metric
                    parts = line.split(' ')
                    if len(parts) >= 2:
                        metrics[parts[0]] = float(parts[1])

        return metrics

    async def _collect_export_statistics(self) -> None:
        """Collect export statistics"""
        self.console.print("📤 Collecting export statistics...")

        try:
            # Get export statistics (simplified - would need specific export endpoints)
            exports_response = await self.api_client.get("/api/v1/exports")
            if exports_response.status_code == 200:
                exports_data = exports_response.json()
                exports = exports_data.get("exports", [])

                # Analyze exports
                format_counts = {}
                destination_counts = {}
                status_counts = {}

                for export in exports:
                    # Format analysis
                    format_type = export.get("format", "unknown")
                    format_counts[format_type] = format_counts.get(format_type, 0) + 1

                    # Destination analysis
                    destination = export.get("destination", "unknown")
                    destination_counts[destination] = destination_counts.get(destination, 0) + 1

                    # Status analysis
                    status = export.get("status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1

                self.report_data["export_statistics"] = {
                    "total_exports": len(exports),
                    "format_distribution": format_counts,
                    "destination_distribution": destination_counts,
                    "status_distribution": status_counts,
                    "success_rate": (status_counts.get("completed", 0) / len(exports) * 100) if exports else 0
                }

        except Exception as e:
            self.console.print(f"⚠️ Failed to collect export statistics: {str(e)}")
            self.report_data["export_statistics"]["error"] = str(e)

    def _generate_recommendations(self) -> None:
        """Generate recommendations based on collected data"""
        recommendations = []

        # Processing recommendations
        processing_metrics = self.report_data.get("processing_metrics", {})
        if processing_metrics.get("average_processing_time_ms", 0) > 5000:
            recommendations.append({
                "category": "Performance",
                "priority": "High",
                "title": "High Processing Times Detected",
                "description": f"Average processing time is {processing_metrics.get('average_processing_time_ms', 0):.0f}ms. Consider optimizing processing pipeline or increasing resources."
            })

        # Exception recommendations
        exception_analysis = self.report_data.get("exception_analysis", {})
        if exception_analysis.get("resolution_rate", 100) < 80:
            recommendations.append({
                "category": "Quality",
                "priority": "Medium",
                "title": "Low Exception Resolution Rate",
                "description": f"Exception resolution rate is {exception_analysis.get('resolution_rate', 0):.1f}%. Consider improving exception handling workflows."
            })

        # Test data recommendations
        test_data = self.report_data.get("test_data", {})
        if test_data.get("total_scenarios", 0) < 50:
            recommendations.append({
                "category": "Testing",
                "priority": "Medium",
                "title": "Limited Test Coverage",
                "description": f"Only {test_data.get('total_scenarios', 0)} test scenarios available. Consider expanding test data coverage."
            })

        # Export recommendations
        export_stats = self.report_data.get("export_statistics", {})
        if export_stats.get("success_rate", 100) < 95:
            recommendations.append({
                "category": "Integration",
                "priority": "High",
                "title": "Export Success Rate Issues",
                "description": f"Export success rate is {export_stats.get('success_rate', 0):.1f}%. Review export configurations and target system connectivity."
            })

        # Add positive recommendations if everything looks good
        if not recommendations:
            recommendations.append({
                "category": "Overall",
                "priority": "Info",
                "title": "System Performing Well",
                "description": "All metrics are within acceptable ranges. Continue monitoring and maintaining current performance levels."
            })

        self.report_data["recommendations"] = recommendations

    async def _generate_html_report(self) -> str:
        """Generate HTML report"""
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AP Intake & Validation - Demo Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .content {
            padding: 30px;
        }
        .section {
            margin-bottom: 40px;
        }
        .section h2 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border-left: 4px solid #3498db;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        .metric-label {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .chart-container {
            position: relative;
            height: 400px;
            margin: 20px 0;
        }
        .recommendations {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 20px;
        }
        .recommendation {
            margin-bottom: 15px;
            padding: 15px;
            background: white;
            border-radius: 5px;
            border-left: 4px solid #f39c12;
        }
        .recommendation.high {
            border-left-color: #e74c3c;
        }
        .recommendation.medium {
            border-left-color: #f39c12;
        }
        .recommendation.low {
            border-left-color: #27ae60;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-success { background-color: #27ae60; }
        .status-warning { background-color: #f39c12; }
        .status-error { background-color: #e74c3c; }
        .footer {
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 20px;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .data-table th,
        .data-table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        .data-table th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        .data-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AP Intake & Validation System</h1>
            <p>Production Demo Report</p>
            <p>Generated on: {{ generated_at }}</p>
        </div>

        <div class="content">
            <!-- System Overview -->
            <div class="section">
                <h2>System Overview</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value">{{ processing_metrics.total_invoices or 0 }}</div>
                        <div class="metric-label">Total Invoices Processed</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{ "%.1f"|format(exception_analysis.resolution_rate or 0) }}%</div>
                        <div class="metric-label">Exception Resolution Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{ test_data.total_scenarios or 0 }}</div>
                        <div class="metric-label">Test Scenarios</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${{ "%.0f"|format(processing_metrics.total_value or 0) }}</div>
                        <div class="metric-label">Total Value Processed</div>
                    </div>
                </div>
            </div>

            <!-- Processing Metrics -->
            <div class="section">
                <h2>Processing Metrics</h2>
                <div class="chart-container">
                    <canvas id="statusChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="vendorChart"></canvas>
                </div>
            </div>

            <!-- Exception Analysis -->
            <div class="section">
                <h2>Exception Analysis</h2>
                <div class="chart-container">
                    <canvas id="exceptionChart"></canvas>
                </div>
                {% if exception_analysis.total_exceptions > 0 %}
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Total Exceptions</td>
                            <td>{{ exception_analysis.total_exceptions }}</td>
                        </tr>
                        <tr>
                            <td>Resolution Rate</td>
                            <td>{{ "%.1f"|format(exception_analysis.resolution_rate) }}%</td>
                        </tr>
                        <tr>
                            <td>Most Common Reason</td>
                            <td>{{ exception_analysis.reason_distribution.items()|first|first if exception_analysis.reason_distribution else 'N/A' }}</td>
                        </tr>
                    </tbody>
                </table>
                {% endif %}
            </div>

            <!-- Recommendations -->
            <div class="section">
                <h2>Recommendations</h2>
                <div class="recommendations">
                    {% for rec in recommendations %}
                    <div class="recommendation {{ rec.priority.lower() }}">
                        <h4>
                            <span class="status-indicator status-{{ 'error' if rec.priority == 'High' else 'warning' if rec.priority == 'Medium' else 'success' }}"></span>
                            {{ rec.title }}
                        </h4>
                        <p><strong>Category:</strong> {{ rec.category }} | <strong>Priority:</strong> {{ rec.priority }}</p>
                        <p>{{ rec.description }}</p>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Generated by AP Intake & Validation System | Demo Report</p>
        </div>
    </div>

    <script>
        // Status Distribution Chart
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        const statusData = {{ processing_metrics.status_distribution|tojson if processing_metrics.status_distribution else '{}' }};
        new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(statusData),
                datasets: [{
                    data: Object.values(statusData),
                    backgroundColor: ['#3498db', '#e74c3c', '#f39c12', '#27ae60', '#9b59b6']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Invoice Status Distribution'
                    }
                }
            }
        });

        // Top Vendors Chart
        const vendorCtx = document.getElementById('vendorChart').getContext('2d');
        const vendorData = {{ processing_metrics.top_vendors|tojson if processing_metrics.top_vendors else '{}' }};
        new Chart(vendorCtx, {
            type: 'bar',
            data: {
                labels: Object.keys(vendorData).slice(0, 5),
                datasets: [{
                    label: 'Invoice Count',
                    data: Object.values(vendorData).slice(0, 5),
                    backgroundColor: '#3498db'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Top 5 Vendors by Invoice Count'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });

        // Exception Reasons Chart
        const exceptionCtx = document.getElementById('exceptionChart').getContext('2d');
        const exceptionData = {{ exception_analysis.reason_distribution|tojson if exception_analysis.reason_distribution else '{}' }};
        if (Object.keys(exceptionData).length > 0) {
            new Chart(exceptionCtx, {
                type: 'bar',
                data: {
                    labels: Object.keys(exceptionData),
                    datasets: [{
                        label: 'Exception Count',
                        data: Object.values(exceptionData),
                        backgroundColor: '#e74c3c'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Exceptions by Reason Code'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    </script>
</body>
</html>
        """

        template = Template(html_template)
        return template.render(**self.report_data)

    def _generate_summary(self) -> str:
        """Generate text summary"""
        summary = []
        summary.append("AP Intake & Validation System - Demo Summary")
        summary.append("=" * 50)
        summary.append(f"Generated: {self.report_data['generated_at']}")
        summary.append("")

        # System Overview
        summary.append("SYSTEM OVERVIEW")
        summary.append("-" * 20)
        processing_metrics = self.report_data.get("processing_metrics", {})
        summary.append(f"Total Invoices: {processing_metrics.get('total_invoices', 0)}")
        summary.append(f"Total Value: ${processing_metrics.get('total_value', 0):,.2f}")
        summary.append(f"Average Invoice Value: ${processing_metrics.get('average_invoice_value', 0):,.2f}")
        summary.append("")

        # Exception Analysis
        exception_analysis = self.report_data.get("exception_analysis", {})
        summary.append("EXCEPTION ANALYSIS")
        summary.append("-" * 20)
        summary.append(f"Total Exceptions: {exception_analysis.get('total_exceptions', 0)}")
        summary.append(f"Resolution Rate: {exception_analysis.get('resolution_rate', 0):.1f}%")
        summary.append("")

        # Test Data
        test_data = self.report_data.get("test_data", {})
        summary.append("TEST DATA")
        summary.append("-" * 20)
        summary.append(f"Total Scenarios: {test_data.get('total_scenarios', 0)}")
        if test_data.get("categories"):
            summary.append("Categories:")
            for category, info in test_data["categories"].items():
                summary.append(f"  - {category}: {info.get('count', 0)} scenarios")
        summary.append("")

        # Recommendations
        recommendations = self.report_data.get("recommendations", [])
        summary.append("RECOMMENDATIONS")
        summary.append("-" * 20)
        if recommendations:
            for rec in recommendations:
                summary.append(f"[{rec['priority']}] {rec['title']}")
                summary.append(f"    {rec['description']}")
                summary.append("")
        else:
            summary.append("No recommendations - system performing well")
            summary.append("")

        return "\n".join(summary)


async def main():
    """Main report generation"""
    parser = argparse.ArgumentParser(description="Generate demo report")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--output", default="reports", help="Output directory")

    args = parser.parse_args()

    console = Console()
    console.print("📊 Starting demo report generation...")

    generator = DemoReportGenerator(base_url=args.base_url)
    results = await generator.generate_comprehensive_report(output_dir=args.output)

    console.print(f"✅ Report generation complete!")
    console.print(f"📄 Open {results['html_report']} in your browser to view the report")


if __name__ == "__main__":
    asyncio.run(main())