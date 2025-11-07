#!/usr/bin/env python3
"""
Quick test to validate Celery configuration files without dependencies.
"""

import os
import sys
import re

def check_celery_app_config():
    """Check Celery app configuration in the file."""
    print("🔍 Checking Celery app configuration...")

    celery_app_file = "app/workers/celery_app.py"
    if not os.path.exists(celery_app_file):
        print(f"   ❌ {celery_app_file} not found")
        return False

    with open(celery_app_file, 'r') as f:
        content = f.read()

    # Check for Redis broker and backend
    if 'broker=settings.REDIS_URL' in content:
        print("   ✅ Redis broker configured")
    else:
        print("   ❌ Redis broker not configured")
        return False

    if 'backend=settings.REDIS_URL' in content:
        print("   ✅ Redis backend configured")
    else:
        print("   ❌ Redis backend not configured")
        return False

    # Check for task modules
    required_modules = [
        'app.workers.invoice_tasks',
        'app.workers.email_tasks',
        'app.workers.maintenance_tasks'
    ]

    for module in required_modules:
        if module in content:
            print(f"   ✅ {module} included")
        else:
            print(f"   ❌ {module} not included")
            return False

    # Check for queues
    if 'invoice_processing' in content and 'validation' in content:
        print("   ✅ Task queues configured")
    else:
        print("   ❌ Task queues not properly configured")
        return False

    # Check for beat schedule
    if 'beat_schedule' in content:
        print("   ✅ Celery Beat schedule configured")
    else:
        print("   ❌ Celery Beat schedule not configured")
        return False

    return True

def check_maintenance_tasks():
    """Check maintenance tasks file."""
    print("\n🔧 Checking maintenance tasks...")

    maintenance_file = "app/workers/maintenance_tasks.py"
    if not os.path.exists(maintenance_file):
        print(f"   ❌ {maintenance_file} not found")
        return False

    with open(maintenance_file, 'r') as f:
        content = f.read()

    required_tasks = [
        'cleanup_old_exports',
        'health_check',
        'backup_system_state',
        'monitor_worker_performance'
    ]

    for task in required_tasks:
        if f'def {task}' in content:
            print(f"   ✅ {task} defined")
        else:
            print(f"   ❌ {task} not found")
            return False

    # Check for Celery task decorators
    if '@celery_app.task' in content:
        print("   ✅ Celery task decorators found")
    else:
        print("   ❌ Celery task decorators not found")
        return False

    return True

def check_task_files():
    """Check task files exist and have proper structure."""
    print("\n📋 Checking task files...")

    task_files = [
        'app/workers/invoice_tasks.py',
        'app/workers/email_tasks.py'
    ]

    for task_file in task_files:
        if not os.path.exists(task_file):
            print(f"   ❌ {task_file} not found")
            return False

        with open(task_file, 'r') as f:
            content = f.read()

        if '@celery_app.task' in content:
            print(f"   ✅ {task_file} has Celery tasks")
        else:
            print(f"   ❌ {task_file} missing Celery tasks")
            return False

    return True

def check_docker_compose():
    """Check Docker Compose configuration."""
    print("\n🐳 Checking Docker Compose configuration...")

    compose_file = "docker-compose.yml"
    if not os.path.exists(compose_file):
        print(f"   ❌ {compose_file} not found")
        return False

    with open(compose_file, 'r') as f:
        content = f.read()

    # Check for Redis service
    if 'redis:' in content and 'image: redis:7-alpine' in content:
        print("   ✅ Redis service configured")
    else:
        print("   ❌ Redis service not properly configured")
        return False

    # Check that RabbitMQ is removed
    if 'rabbitmq:' in content:
        print("   ⚠️  RabbitMQ service still present (should be removed)")
    else:
        print("   ✅ RabbitMQ service removed")

    # Check for worker service
    if 'worker:' in content and 'celery -A app.workers.celery_app worker' in content:
        print("   ✅ Celery worker service configured")
    else:
        print("   ❌ Celery worker service not properly configured")
        return False

    # Check for scheduler service
    if 'scheduler:' in content and 'celery -A app.workers.celery_app beat' in content:
        print("   ✅ Celery scheduler service configured")
    else:
        print("   ❌ Celery scheduler service not properly configured")
        return False

    # Check environment variables
    if 'REDIS_URL=redis://redis:6379/0' in content:
        print("   ✅ Redis URL configured in services")
    else:
        print("   ❌ Redis URL not configured in services")
        return False

    # Check that RabbitMQ URL is removed
    if 'RABBITMQ_URL' in content:
        print("   ⚠️  RabbitMQ URL still present (should be removed)")
    else:
        print("   ✅ RabbitMQ URL removed")

    return True

def check_monitoring_endpoints():
    """Check monitoring endpoints."""
    print("\n📊 Checking monitoring endpoints...")

    monitoring_file = "app/api/api_v1/endpoints/celery_monitoring.py"
    if not os.path.exists(monitoring_file):
        print(f"   ❌ {monitoring_file} not found")
        return False

    with open(monitoring_file, 'r') as f:
        content = f.read()

    required_endpoints = [
        'get_celery_status',
        'get_task_info',
        'get_queue_info',
        'get_worker_info'
    ]

    for endpoint in required_endpoints:
        if f'def {endpoint}' in content:
            print(f"   ✅ {endpoint} endpoint defined")
        else:
            print(f"   ❌ {endpoint} endpoint not found")
            return False

    return True

def check_api_router():
    """Check that monitoring endpoints are included in API router."""
    print("\n🔗 Checking API router integration...")

    api_file = "app/api/api_v1/api.py"
    if not os.path.exists(api_file):
        print(f"   ❌ {api_file} not found")
        return False

    with open(api_file, 'r') as f:
        content = f.read()

    if 'celery_monitoring' in content and 'celery_monitoring.router' in content:
        print("   ✅ Celery monitoring endpoints included in API")
    else:
        print("   ❌ Celery monitoring endpoints not included in API")
        return False

    return True

def check_env_file():
    """Check .env file configuration."""
    print("\n🔧 Checking .env file...")

    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"   ❌ {env_file} not found")
        return False

    with open(env_file, 'r') as f:
        content = f.read()

    if 'REDIS_URL=' in content:
        print("   ✅ REDIS_URL configured")
    else:
        print("   ❌ REDIS_URL not configured")
        return False

    if 'DATABASE_URL=' in content:
        print("   ✅ DATABASE_URL configured")
    else:
        print("   ❌ DATABASE_URL not configured")
        return False

    return True

def main():
    """Run all quick checks."""
    print("🚀 Quick Celery Configuration Test")
    print("=" * 40)

    checks = [
        check_celery_app_config,
        check_maintenance_tasks,
        check_task_files,
        check_docker_compose,
        check_monitoring_endpoints,
        check_api_router,
        check_env_file,
    ]

    passed = 0
    failed = 0

    for check in checks:
        try:
            if check():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ❌ Check failed: {e}")
            failed += 1

    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 All configuration tests passed!")
        print("\n📝 Ready to start services:")
        print("   1. docker-compose up -d")
        print("   2. docker-compose logs -f worker")
        print("   3. Test API: curl http://localhost:8000/api/v1/celery/status")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed.")
        print("Please address the configuration issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())