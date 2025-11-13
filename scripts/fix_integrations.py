#!/usr/bin/env python3
"""
Quick Fix Script for AP Intake & Validation System Integration Issues

This script provides automated fixes for the most critical integration issues
discovered during testing. Run this script to quickly resolve common configuration
problems and get services running.

USAGE:
    python fix_integrations.py

PREREQUISITES:
    - Docker and Docker Compose installed
    - Project directory accessible
    - Sufficient system resources
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path

def print_header(title):
    """Print formatted header."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_success(message):
    """Print success message."""
    print(f"✅ {message}")

def print_error(message):
    """Print error message."""
    print(f"❌ {message}")

def print_warning(message):
    """Print warning message."""
    print(f"⚠️  {message}")

def print_info(message):
    """Print info message."""
    print(f"ℹ️  {message}")

def run_command(command, description, check=True):
    """Run shell command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=check,
            timeout=30
        )
        if result.returncode == 0:
            print_success(f"{description} - SUCCESS")
            return True, result.stdout
        else:
            print_error(f"{description} - FAILED: {result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print_error(f"{description} - TIMEOUT")
        return False, "Command timed out"
    except Exception as e:
        print_error(f"{description} - ERROR: {e}")
        return False, str(e)

def check_docker_services():
    """Check current Docker service status."""
    print_header("Checking Current Docker Services")

    success, output = run_command(
        "docker-compose ps",
        "Checking Docker Compose services",
        check=False
    )

    if success:
        print_info("Current Docker services status:")
        print(output)
        return True
    else:
        print_error("Failed to check Docker services")
        return False

def start_infrastructure_services():
    """Start core infrastructure services."""
    print_header("Starting Infrastructure Services")

    services = ["postgres", "redis", "minio"]
    started_services = []

    for service in services:
        success, _ = run_command(
            f"docker-compose up -d {service}",
            f"Starting {service}"
        )
        if success:
            started_services.append(service)

    if started_services:
        print_success(f"Started services: {', '.join(started_services)}")
        # Wait for services to be healthy
        print_info("Waiting for services to be healthy...")
        time.sleep(10)
        return True
    else:
        print_error("Failed to start any infrastructure services")
        return False

def start_background_services():
    """Start background processing services."""
    print_header("Starting Background Processing Services")

    # Start RabbitMQ first
    success, _ = run_command(
        "docker-compose up -d rabbitmq",
        "Starting RabbitMQ message broker"
    )

    if not success:
        print_warning("RabbitMQ may not be defined in docker-compose.yml")

    # Wait for RabbitMQ
    time.sleep(5)

    # Start workers and scheduler
    services = ["worker", "scheduler"]
    started_services = []

    for service in services:
        success, _ = run_command(
            f"docker-compose up -d {service}",
            f"Starting {service}",
            check=False  # Don't fail if services don't exist
        )
        if success:
            started_services.append(service)

    if started_services:
        print_success(f"Started background services: {', '.join(started_services)}")
        return True
    else:
        print_warning("No background services were started (may not be configured)")
        return False

def verify_service_health():
    """Verify service health after startup."""
    print_header("Verifying Service Health")

    health_checks = [
        ("PostgreSQL", "docker exec ap_intake_postgres_1 pg_isready -U postgres"),
        ("Redis", "docker exec ap_intake_redis_1 redis-cli ping"),
        ("MinIO", "curl -s http://localhost:9002/minio/health/live"),
    ]

    healthy_services = []

    for service_name, command in health_checks:
        success, output = run_command(command, f"Checking {service_name}", check=False)
        if success:
            if service_name == "PostgreSQL" and "accepting connections" in output:
                healthy_services.append(service_name)
            elif service_name == "Redis" and "PONG" in output:
                healthy_services.append(service_name)
            elif service_name == "MinIO" and output:
                healthy_services.append(service_name)
        else:
            print_warning(f"{service_name} health check failed")

    if healthy_services:
        print_success(f"Healthy services: {', '.join(healthy_services)}")
        return True
    else:
        print_error("No services passed health checks")
        return False

def update_env_file():
    """Update .env file with better default values."""
    print_header("Updating Environment Configuration")

    env_file = Path(".env")
    if not env_file.exists():
        print_error(".env file not found")
        return False

    # Read current .env
    with open(env_file, 'r') as f:
        env_content = f.read()

    # Update with better defaults
    updates = {
        "OPENROUTER_API_KEY": "sk-or-v1-YOUR_ACTUAL_API_KEY_HERE",
        "GMAIL_CLIENT_ID": "your-gmail-client-id.apps.googleusercontent.com",
        "GMAIL_CLIENT_SECRET": "your-gmail-client-secret",
        "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
        "REDIS_URL": "redis://localhost:6380/0"
    }

    for key, value in updates.items():
        if key not in env_content:
            env_content += f"\n# {key} - Update with actual values\n{key}={value}\n"

    # Write updated .env
    with open(env_file, 'w') as f:
        f.write(env_content)

    print_success("Environment file updated with placeholder values")
    print_warning("Please update the placeholder values with actual credentials")
    return True

def create_service_status_report():
    """Create a detailed service status report."""
    print_header("Generating Service Status Report")

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "services": {}
    }

    # Check each service
    service_commands = {
        "PostgreSQL": "docker exec ap_intake_postgres_1 pg_isready -U postgres",
        "Redis": "docker exec ap_intake_redis_1 redis-cli ping",
        "MinIO_API": "curl -s -w '%{http_code}' http://localhost:9002/minio/health/live",
        "MinIO_Console": "curl -s -w '%{http_code}' http://localhost:9003",
        "OpenRouter_API": "curl -s -w '%{http_code}' https://openrouter.ai/api/v1/models",
        "Gmail_OAuth": "curl -s -w '%{http_code}' https://accounts.google.com/.well-known/openid-configuration"
    }

    for service_name, command in service_commands.items():
        try:
            success, output = run_command(command, f"Checking {service_name}", check=False)
            if success:
                status = "OPERATIONAL"
                details = output.strip()[:100]
            else:
                status = "FAILED"
                details = output[:100] if output else "Command failed"

            report["services"][service_name] = {
                "status": status,
                "details": details,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            report["services"][service_name] = {
                "status": "ERROR",
                "details": str(e),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

    # Save report
    report_file = "service_status_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print_success(f"Service status report saved to {report_file}")

    # Print summary
    operational = sum(1 for s in report["services"].values() if s["status"] == "OPERATIONAL")
    total = len(report["services"])
    print_info(f"Services operational: {operational}/{total} ({operational/total*100:.1f}%)")

    return True

def print_next_steps():
    """Print recommended next steps."""
    print_header("Recommended Next Steps")

    steps = [
        "1. 🔑 Configure OpenRouter API Key:",
        "   - Get API key from https://openrouter.ai/keys",
        "   - Update OPENROUTER_API_KEY in .env file",
        "",
        "2. 📧 Configure Gmail API:",
        "   - Create Google Cloud Project",
        "   - Enable Gmail API",
        "   - Create OAuth 2.0 credentials",
        "   - Update GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env",
        "",
        "3. 🚀 Test the Application:",
        "   - docker-compose up -d api",
        "   - Visit http://localhost:8000/docs for API documentation",
        "   - Test file upload and processing",
        "",
        "4. 🔒 Security Hardening:",
        "   - Change default MinIO credentials",
        "   - Configure Redis authentication",
        "   - Enable SSL/TLS for production",
        "",
        "5. 📊 Monitoring Setup:",
        "   - Implement health check monitoring",
        "   - Set up log aggregation",
        "   - Configure alerting",
        "",
        "6. 🧪 Run Integration Tests:",
        "   - python simple_integration_test.py",
        "   - Review test results and fix remaining issues"
    ]

    for step in steps:
        print(step)

def main():
    """Main function to fix integration issues."""
    print_header("AP Intake & Validation System - Integration Fix Script")
    print_info("This script will help fix common integration issues and start services.")
    print_info("Please ensure Docker and Docker Compose are installed and running.")

    # Step 1: Check current status
    if not check_docker_services():
        print_error("Docker services check failed")
        return False

    # Step 2: Start infrastructure services
    if not start_infrastructure_services():
        print_error("Failed to start infrastructure services")
        return False

    # Step 3: Start background services
    start_background_services()

    # Step 4: Verify service health
    if not verify_service_health():
        print_warning("Some services may not be fully operational")

    # Step 5: Update environment configuration
    update_env_file()

    # Step 6: Create status report
    create_service_status_report()

    # Step 7: Print next steps
    print_next_steps()

    print_header("Fix Script Complete")
    print_success("Integration fix script completed successfully!")
    print_info("Review the service status report and follow the next steps above.")

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Script failed with error: {e}")
        sys.exit(1)