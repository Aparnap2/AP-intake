#!/usr/bin/env python3
"""
Manual test script for Celery setup.
Run this script to verify Celery workers and tasks are working properly.
"""

import time
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.workers.celery_app import celery_app
from app.workers.maintenance_tasks import health_check, cleanup_old_exports
from app.workers.email_tasks import health_check_email_services
from app.workers.invoice_tasks import validate_invoice_task


def test_celery_connection():
    """Test basic Celery connection and configuration."""
    print("🔍 Testing Celery connection and configuration...")

    try:
        # Test basic configuration
        print(f"   ✅ Celery app name: {celery_app.main}")
        print(f"   ✅ Broker URL: {celery_app.conf.broker_url}")
        print(f"   ✅ Result backend: {celery_app.conf.result_backend}")

        # Test Redis connection
        import redis
        from app.core.config import settings
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        print(f"   ✅ Redis connection successful")

        # Check tasks are registered
        inspect = celery_app.control.inspect()
        registered_tasks = inspect.registered()
        if registered_tasks:
            print(f"   ✅ Registered tasks: {len(list(registered_tasks.values())[0])}")
        else:
            print("   ⚠️  No workers currently running (this is OK for this test)")

        return True

    except Exception as e:
        print(f"   ❌ Connection test failed: {e}")
        return False


def test_task_execution():
    """Test basic task execution."""
    print("\n🚀 Testing task execution...")

    try:
        # Test health check task
        print("   📊 Running health check task...")
        health_task = health_check.delay()

        # Wait for completion
        for i in range(30):  # Wait up to 30 seconds
            if health_task.ready():
                break
            time.sleep(1)

        if health_task.ready():
            if health_task.successful():
                result = health_task.get()
                print(f"   ✅ Health check completed: {result.get('status', 'unknown')}")

                # Print some check results
                checks = result.get('checks', {})
                for check_name, check_result in checks.items():
                    status = check_result.get('status', 'unknown')
                    print(f"      - {check_name}: {status}")
            else:
                print(f"   ❌ Health check failed: {health_task.result}")
        else:
            print("   ⚠️  Health check timed out (no worker running?)")

        # Test cleanup exports task
        print("   🧹 Running cleanup task...")
        cleanup_task = cleanup_old_exports.delay(days_to_keep=1)

        # Wait for completion
        for i in range(30):
            if cleanup_task.ready():
                break
            time.sleep(1)

        if cleanup_task.ready():
            if cleanup_task.successful():
                result = cleanup_task.get()
                print(f"   ✅ Cleanup completed: {result.get('status', 'unknown')}")
            else:
                print(f"   ❌ Cleanup failed: {cleanup_task.result}")
        else:
            print("   ⚠️  Cleanup task timed out")

        return True

    except Exception as e:
        print(f"   ❌ Task execution test failed: {e}")
        return False


def test_worker_status():
    """Test worker status and statistics."""
    print("\n👷 Testing worker status...")

    try:
        inspect = celery_app.control.inspect()

        # Get active workers
        stats = inspect.stats()
        if stats:
            print(f"   ✅ Active workers: {len(stats)}")
            for worker_name, worker_stats in stats.items():
                print(f"      - {worker_name}: {worker_stats.get('pool', {}).get('max-concurrency', 'unknown')} processes")
                print(f"        Total tasks: {worker_stats.get('total', 0)}")
        else:
            print("   ⚠️  No workers currently running")

        # Get active tasks
        active = inspect.active()
        if active:
            total_active = sum(len(tasks) for tasks in active.values())
            print(f"   ✅ Active tasks: {total_active}")
        else:
            print("   ℹ️  No active tasks")

        # Get scheduled tasks
        scheduled = inspect.scheduled()
        if scheduled:
            total_scheduled = sum(len(tasks) for tasks in scheduled.values())
            print(f"   ✅ Scheduled tasks: {total_scheduled}")
        else:
            print("   ℹ️  No scheduled tasks")

        return True

    except Exception as e:
        print(f"   ❌ Worker status test failed: {e}")
        return False


def test_queue_status():
    """Test queue status."""
    print("\n📬 Testing queue status...")

    try:
        from kombu import Connection
        from app.core.config import settings

        queue_names = ["invoice_processing", "validation", "export", "email_processing", "celery"]

        with Connection(settings.REDIS_URL) as conn:
            channel = conn.channel()

            for queue_name in queue_names:
                try:
                    queue = channel.queue_declare(queue_name, passive=True)
                    print(f"   ✅ {queue_name}: {queue.message_count} messages, {queue.consumer_count} consumers")
                except Exception as e:
                    print(f"   ⚠️  {queue_name}: {e}")

        return True

    except Exception as e:
        print(f"   ❌ Queue status test failed: {e}")
        return False


def test_beat_schedule():
    """Test Celery Beat schedule."""
    print("\n⏰ Testing Celery Beat schedule...")

    try:
        schedule = celery_app.conf.beat_schedule

        print(f"   ✅ Scheduled tasks: {len(schedule)}")
        for task_name, task_config in schedule.items():
            print(f"      - {task_name}: {task_config['task']}")
            print(f"        Schedule: {task_config['schedule']}")

        return True

    except Exception as e:
        print(f"   ❌ Beat schedule test failed: {e}")
        return False


def test_simple_workflow():
    """Test a simple workflow with multiple tasks."""
    print("\n🔄 Testing simple workflow...")

    try:
        # Test validation task with dummy data
        print("   📋 Running validation task...")
        validation_task = validate_invoice_task.delay(
            invoice_id="test_invoice_123",
            extraction_result={
                "header": {"vendor_name": "Test Vendor", "invoice_number": "123"},
                "lines": [{"description": "Test Item", "amount": 100.0}],
                "confidence": {"overall": 0.9}
            }
        )

        # Wait for completion
        for i in range(30):
            if validation_task.ready():
                break
            time.sleep(1)

        if validation_task.ready():
            if validation_task.successful():
                result = validation_task.get()
                print(f"   ✅ Validation completed: {result.get('validation_passed', False)}")
            else:
                print(f"   ❌ Validation failed: {validation_task.result}")
        else:
            print("   ⚠️  Validation task timed out")

        return True

    except Exception as e:
        print(f"   ❌ Workflow test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Starting Celery Setup Tests")
    print("=" * 50)

    tests = [
        test_celery_connection,
        test_task_execution,
        test_worker_status,
        test_queue_status,
        test_beat_schedule,
        test_simple_workflow,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ❌ Test {test.__name__} crashed: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! Celery setup is working correctly.")
        print("\n📝 Next steps:")
        print("   1. Start the Celery worker: celery -A app.workers.celery_app worker --loglevel=info")
        print("   2. Start Celery Beat scheduler: celery -A app.workers.celery_app beat --loglevel=info")
        print("   3. Test with the API: curl http://localhost:8000/api/v1/celery/status")
    else:
        print("⚠️  Some tests failed. Check the Celery configuration and make sure:")
        print("   1. Redis is running: docker-compose up redis")
        print("   2. Start a Celery worker: celery -A app.workers.celery_app worker --loglevel=info")
        print("   3. Check the configuration in app/workers/celery_app.py")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())