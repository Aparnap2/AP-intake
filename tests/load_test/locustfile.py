"""
Comprehensive load testing for AP Intake & Validation system using Locust.
"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any

from locust import HttpUser, task, between, events
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging

# Sample data for load testing
SAMPLE_VENDORS = ["Acme Corp", "Tech Solutions Inc", "Global Services Ltd", "Innovation Labs", "Enterprise Systems"]
SAMPLE_CATEGORIES = ["Software", "Hardware", "Consulting", "Cloud Services", "Infrastructure"]

class APIntakeUser(HttpUser):
    """
    Simulates realistic user behavior for the AP Intake & Validation system.
    """

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

    def on_start(self):
        """Called when a simulated user starts."""
        # Get dev token for authentication
        response = self.client.get("/api/v1/auth/dev-token")
        if response.status_code == 200:
            token_data = response.json()
            self.client.headers.update({
                "Authorization": f"Bearer {token_data['access_token']}"
            })
            self.user_id = token_data.get("user_id", "load-test-user")
        else:
            self.user_id = f"load-test-{uuid.uuid4().hex[:8]}"

        # Initialize user state
        self.uploaded_files = []
        self.current_invoices = []

        self.environment.events.request.add_listener(self._track_request_metrics)

    def on_stop(self):
        """Called when a simulated user stops."""
        self.environment.events.request.remove_listener(self._track_request_metrics)

    def _track_request_metrics(self, request_type, name, response_time, response_length, exception, **kwargs):
        """Track additional request metrics."""
        # Custom metrics tracking can be added here
        pass

    @task(3)
    def health_check(self):
        """Check system health - high frequency task."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") != "healthy":
                    response.failure(f"Unhealthy status: {data.get('status')}")
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(2)
    def get_metrics(self):
        """Get system metrics - medium frequency task."""
        self.client.get("/metrics")

    @task(2)
    def check_slos(self):
        """Check SLO status - medium frequency task."""
        with self.client.get("/api/v1/metrics/slos/dashboard?time_range_days=7", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate SLO dashboard structure
                if "slos" not in data:
                    response.failure("Missing SLOs in dashboard data")
                elif "summary" not in data:
                    response.failure("Missing summary in dashboard data")
            else:
                response.failure(f"SLO dashboard request failed: {response.status_code}")

    @task(5)
    def list_invoices(self):
        """List invoices - high frequency task."""
        params = {
            "limit": random.choice([10, 25, 50, 100]),
            "offset": random.choice([0, 10, 25, 50]),
        }

        # Add random filters
        if random.random() < 0.3:
            params["status"] = random.choice(["processing", "ready", "exception", "approved"])

        if random.random() < 0.2:
            params["vendor"] = random.choice(SAMPLE_VENDORS)

        self.client.get("/api/v1/invoices/", params=params)

    @task(1)
    def get_invoice_details(self):
        """Get detailed invoice information - low frequency task."""
        if self.current_invoices:
            invoice_id = random.choice(self.current_invoices)
            self.client.get(f"/api/v1/invoices/{invoice_id}")

    @task(4)
    def upload_invoice(self):
        """Upload a new invoice - high frequency task."""
        # Generate sample invoice data
        invoice_data = self._generate_sample_invoice()

        # Create multipart form data
        files = {
            "file": ("sample_invoice.pdf", b"%PDF-1.4 sample content", "application/pdf")
        }

        data = {
            "vendor_id": invoice_data["vendor_id"],
            "source_type": "api",
            "source_reference": f"load-test-{uuid.uuid4().hex[:8]}",
            "uploaded_by": self.user_id,
            "metadata": json.dumps(invoice_data.get("metadata", {}))
        }

        with self.client.post("/api/v1/ingestion/upload", files=files, data=data, catch_response=True) as response:
            if response.status_code in [200, 201, 202]:
                invoice_response = response.json()
                invoice_id = invoice_response.get("id")
                if invoice_id:
                    self.current_invoices.append(invoice_id)
                    # Keep only recent invoices in memory
                    if len(self.current_invoices) > 100:
                        self.current_invoices = self.current_invoices[-50:]
            else:
                response.failure(f"Invoice upload failed: {response.status_code}")

    @task(1)
    def check_processing_status(self):
        """Check processing status for uploaded invoices."""
        if self.current_invoices:
            invoice_id = random.choice(self.current_invoices)
            self.client.get(f"/api/v1/ingestion/status/{invoice_id}")

    @task(1)
    def get_validation_results(self):
        """Get validation results for invoices."""
        if self.current_invoices:
            invoice_id = random.choice(self.current_invoices)
            self.client.get(f"/api/v1/validation/invoice/{invoice_id}")

    @task(1)
    def check_exceptions(self):
        """Check for processing exceptions."""
        params = {
            "limit": random.choice([10, 25, 50]),
            "severity": random.choice(["low", "medium", "high", "critical"]),
            "status": random.choice(["open", "in_progress", "resolved"])
        }
        self.client.get("/api/v1/exceptions/", params=params)

    @task(1)
    def get_analytics(self):
        """Get analytics data."""
        time_ranges = ["7d", "30d", "90d"]
        params = {
            "time_range": random.choice(time_ranges),
            "metrics": random.choice(["processing_time", "validation_rate", "exception_rate"])
        }
        self.client.get("/api/v1/analytics/kpi", params=params)

    def _generate_sample_invoice(self) -> Dict[str, Any]:
        """Generate sample invoice data for testing."""
        invoice_id = str(uuid.uuid4())
        vendor = random.choice(SAMPLE_VENDORS)

        return {
            "vendor_id": str(uuid.uuid4()),
            "invoice_number": f"INV-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            "invoice_date": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
            "due_date": (datetime.now() + timedelta(days=random.randint(15, 45))).isoformat(),
            "total_amount": round(random.uniform(100, 10000), 2),
            "vendor": vendor,
            "category": random.choice(SAMPLE_CATEGORIES),
            "metadata": {
                "department": random.choice(["IT", "Operations", "Finance", "Marketing"]),
                "cost_center": f"CC-{random.randint(100, 999)}",
                "project_code": f"PROJ-{random.randint(1000, 9999)}",
                "urgent": random.random() < 0.1,  # 10% urgent invoices
                "recurring": random.random() < 0.2   # 20% recurring invoices
            }
        }


class AdminUser(HttpUser):
    """
    Simulates admin user behavior for system management tasks.
    """

    wait_time = between(5, 15)  # Less frequent admin operations

    def on_start(self):
        """Called when admin user starts."""
        # Get admin token
        response = self.client.get("/api/v1/auth/dev-token")
        if response.status_code == 200:
            token_data = response.json()
            self.client.headers.update({
                "Authorization": f"Bearer {token_data['access_token']}"
            })

    @task(2)
    def get_system_metrics(self):
        """Get detailed system metrics."""
        self.client.get("/api/v1/metrics/system")

    @task(1)
    def get_performance_metrics(self):
        """Get performance metrics."""
        self.client.get("/api/v1/metrics/performance")

    @task(1)
    def check_database_health(self):
        """Check database health."""
        self.client.get("/api/v1/monitoring/database/health")

    @task(1)
    def get_worker_status(self):
        """Check background worker status."""
        self.client.get("/api/v1/celery/monitoring/workers")

    @task(1)
    def check_queues(self):
        """Check queue status."""
        self.client.get("/api/v1/celery/monitoring/queues")

    @task(1)
    def get_error_logs(self):
        """Get recent error logs."""
        params = {
            "limit": random.choice([25, 50, 100]),
            "level": "ERROR",
            "hours": random.choice([1, 6, 24])
        }
        self.client.get("/api/v1/observability/logs", params=params)


class StressTestUser(HttpUser):
    """
    High-intensity user for stress testing.
    """

    wait_time = between(0.1, 1)  # Very frequent requests

    def on_start(self):
        """Called when stress test user starts."""
        response = self.client.get("/api/v1/auth/dev-token")
        if response.status_code == 200:
            token_data = response.json()
            self.client.headers.update({
                "Authorization": f"Bearer {token_data['access_token']}"
            })

    @task(10)
    def rapid_health_checks(self):
        """Rapid health checks for stress testing."""
        self.client.get("/health")

    @task(5)
    def rapid_invoice_lists(self):
        """Rapid invoice listing."""
        self.client.get("/api/v1/invoices/?limit=10")

    @task(3)
    def rapid_uploads(self):
        """Rapid file uploads for stress testing."""
        files = {
            "file": ("stress_test.pdf", b"%PDF-1.4 stress test content", "application/pdf")
        }
        data = {
            "vendor_id": str(uuid.uuid4()),
            "source_type": "api",
            "source_reference": f"stress-test-{uuid.uuid4().hex[:8]}",
            "uploaded_by": "stress-test-user"
        }
        self.client.post("/api/v1/ingestion/upload", files=files, data=data)

    @task(2)
    def rapid_metrics_check(self):
        """Rapid metrics checking."""
        self.client.get("/metrics")


# Custom event listeners for additional metrics collection
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """
    Track custom request metrics.
    """
    if exception:
        print(f"Request failed: {request_type} {name} - {exception}")

    # Log slow requests
    if response_time > 5000:  # > 5 seconds
        print(f"Slow request: {request_type} {name} took {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Called when load test starts.
    """
    print("=" * 50)
    print("LOAD TEST STARTING")
    print("=" * 50)
    print(f"Test started at: {datetime.now().isoformat()}")
    print(f"Target host: {environment.host}")
    print(f"Number of users: {environment.parsed_options.num_users}")
    print(f"Hatch rate: {environment.parsed_options.hatch_rate}")
    print(f"Run time: {environment.parsed_options.run_time or 'unlimited'}")
    print("=" * 50)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Called when load test stops.
    """
    print("=" * 50)
    print("LOAD TEST COMPLETED")
    print("=" * 50)
    print(f"Test completed at: {datetime.now().isoformat()}")

    # Print summary statistics
    stats = environment.stats

    print("\nOverall Statistics:")
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Failure rate: {stats.total.fail_ratio:.2%}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Min response time: {stats.total.min_response_time:.2f}ms")
    print(f"Max response time: {stats.total.max_response_time:.2f}ms")

    print("\nRequests per second:")
    print(f"Current: {stats.total.current_rps:.2f}")
    print(f"Average: {stats.total.avg_rps:.2f}")

    print("\nSlowest endpoints:")
    sorted_stats = sorted(stats.entries.items(), key=lambda x: x[1].avg_response_time, reverse=True)
    for name, stats_obj in sorted_stats[:5]:
        print(f"  {name}: {stats_obj.avg_response_time:.2f}ms avg")

    print("\nMost requested endpoints:")
    sorted_by_requests = sorted(stats.entries.items(), key=lambda x: x[1].num_requests, reverse=True)
    for name, stats_obj in sorted_by_requests[:5]:
        print(f"  {name}: {stats_obj.num_requests} requests")

    print("=" * 50)


if __name__ == "__main__":
    """
    Run load tests directly.
    """
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "smoke":
            # Smoke test - light load
            print("Running smoke test...")
            system = Environment(user_classes=[APIntakeUser])
            system.create_local_runner()
            system.runner.start(1, hatch_rate=1)
            system.runner.greenlet.join()

        elif sys.argv[1] == "light":
            # Light load test
            print("Running light load test...")
            system = Environment(user_classes=[APIntakeUser])
            system.create_local_runner()
            system.runner.start(10, hatch_rate=2)
            system.runner.greenlet.join()

        elif sys.argv[1] == "medium":
            # Medium load test
            print("Running medium load test...")
            system = Environment(user_classes=[APIntakeUser, AdminUser])
            system.create_local_runner()
            system.runner.start(50, hatch_rate=5)
            system.runner.greenlet.join()

        elif sys.argv[1] == "stress":
            # Stress test
            print("Running stress test...")
            system = Environment(user_classes=[APIntakeUser, AdminUser, StressTestUser])
            system.create_local_runner()
            system.runner.start(100, hatch_rate=10)
            system.runner.greenlet.join()
    else:
        print("Usage: python locustfile.py [smoke|light|medium|stress]")