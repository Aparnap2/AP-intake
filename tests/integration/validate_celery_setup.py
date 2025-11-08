#!/usr/bin/env python3
"""
Validate Celery setup and dependencies before starting services.
"""

import sys
import os

def check_dependencies():
    """Check if required dependencies are available."""
    print("🔍 Checking dependencies...")

    required_modules = [
        'celery',
        'redis',
        'kombu',
        'sqlalchemy',
        'fastapi',
        'pydantic'
    ]

    missing_modules = []

    for module in required_modules:
        try:
            __import__(module)
            print(f"   ✅ {module}")
        except ImportError:
            print(f"   ❌ {module} (missing)")
            missing_modules.append(module)

    if missing_modules:
        print(f"\n❌ Missing dependencies: {', '.join(missing_modules)}")
        print("Install with: pip install " + " ".join(missing_modules))
        return False
    else:
        print("   ✅ All dependencies found")
        return True

def check_configuration():
    """Check configuration files."""
    print("\n📋 Checking configuration files...")

    required_files = [
        'app/workers/celery_app.py',
        'app/workers/invoice_tasks.py',
        'app/workers/email_tasks.py',
        'app/workers/maintenance_tasks.py',
        'docker-compose.yml',
        '.env.example'
    ]

    missing_files = []

    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (missing)")
            missing_files.append(file_path)

    if missing_files:
        print(f"\n❌ Missing files: {', '.join(missing_files)}")
        return False
    else:
        print("   ✅ All configuration files found")
        return True

def check_directories():
    """Check required directories."""
    print("\n📁 Checking directories...")

    required_dirs = [
        'app/workers',
        'app/models',
        'app/services',
        'logs',
        'tests'
    ]

    missing_dirs = []

    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print(f"   ✅ {dir_path}")
        else:
            print(f"   ❌ {dir_path} (missing)")
            missing_dirs.append(dir_path)

    if missing_dirs:
        print(f"\n❌ Missing directories: {', '.join(missing_dirs)}")
        print("Create with: mkdir -p " + " ".join(missing_dirs))
        return False
    else:
        print("   ✅ All directories found")
        return True

def check_env_file():
    """Check .env file configuration."""
    print("\n🔧 Checking environment configuration...")

    if os.path.exists('.env'):
        print("   ✅ .env file exists")

        # Check key environment variables
        with open('.env', 'r') as f:
            content = f.read()

        key_vars = [
            'REDIS_URL',
            'DATABASE_URL'
        ]

        missing_vars = []
        for var in key_vars:
            if var in content:
                print(f"   ✅ {var} configured")
            else:
                print(f"   ⚠️  {var} not found in .env")
                missing_vars.append(var)

        if missing_vars:
            print(f"   ⚠️  Consider adding: {', '.join(missing_vars)}")
            print("   You can use .env.example as a template")

        return True
    else:
        print("   ⚠️  .env file not found")
        if os.path.exists('.env.example'):
            print("   💡 Copy .env.example to .env and configure")
        return False

def check_redis_connectivity():
    """Check Redis connectivity."""
    print("\n🔗 Checking Redis connectivity...")

    try:
        import redis
        from app.core.config import settings

        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        print(f"   ✅ Redis connection successful: {settings.REDIS_URL}")
        return True
    except ImportError:
        print("   ⚠️  Redis module not installed")
        return False
    except Exception as e:
        print(f"   ❌ Redis connection failed: {e}")
        print("   Make sure Redis is running: docker-compose up redis")
        return False

def check_docker_compose():
    """Check Docker Compose configuration."""
    print("\n🐳 Checking Docker Compose setup...")

    if not os.path.exists('docker-compose.yml'):
        print("   ❌ docker-compose.yml not found")
        return False

    # Check for Redis service
    try:
        import yaml
        with open('docker-compose.yml', 'r') as f:
            compose_config = yaml.safe_load(f)

        if 'services' in compose_config:
            services = compose_config['services']

            if 'redis' in services:
                print("   ✅ Redis service configured")
            else:
                print("   ❌ Redis service not found in docker-compose.yml")
                return False

            if 'worker' in services:
                print("   ✅ Celery worker service configured")
            else:
                print("   ❌ Celery worker service not found")
                return False

            if 'scheduler' in services:
                print("   ✅ Celery scheduler service configured")
            else:
                print("   ❌ Celery scheduler service not found")
                return False

            # Check for RabbitMQ (should not exist)
            if 'rabbitmq' in services:
                print("   ⚠️  RabbitMQ service found (should be removed)")

            print("   ✅ Docker Compose configuration looks good")
            return True
        else:
            print("   ❌ No services found in docker-compose.yml")
            return False

    except ImportError:
        print("   ⚠️  PyYAML not installed, cannot validate docker-compose.yml")
        return True  # Don't fail the check for this
    except Exception as e:
        print(f"   ❌ Error reading docker-compose.yml: {e}")
        return False

def main():
    """Run all validation checks."""
    print("🔍 Celery Setup Validation")
    print("=" * 40)

    # Check basic setup
    checks = [
        check_configuration,
        check_directories,
        check_env_file,
        check_docker_compose,
    ]

    # Check dependencies if modules are available
    try:
        import sys
        sys.path.insert(0, '.')
        checks.append(check_dependencies)
        checks.append(check_redis_connectivity)
    except Exception:
        print("⚠️  Skipping dependency checks (modules not available)")

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
    print(f"📊 Validation Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 All validation checks passed!")
        print("\n📝 Next steps:")
        print("   1. Copy .env.example to .env (if not exists)")
        print("   2. Configure environment variables in .env")
        print("   3. Start services: docker-compose up -d")
        print("   4. Check status: docker-compose ps")
        print("   5. Run tests: python scripts/test_celery_setup.py")
        return 0
    else:
        print(f"\n⚠️  {failed} validation check(s) failed.")
        print("Please address the issues above before starting the services.")
        return 1

if __name__ == "__main__":
    sys.exit(main())