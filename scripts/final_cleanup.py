#!/usr/bin/env python3
"""
Final cleanup script to organize all files according to the project structure.
"""

import os
import shutil
from pathlib import Path

def final_cleanup():
    """Perform final cleanup of the root directory."""

    root_dir = Path("/home/aparna/Desktop/ap_intake")

    # Define files to keep in root
    essential_files = {
        "README.md",
        "CLAUDE.md",
        "start.sh",
        "pyproject.toml",
        "docker-compose.yml",
        "docker-compose.minimal.yml",
        "docker-compose.prod.yml",
        "Dockerfile",
        "Dockerfile.prod",
        "alembic.ini",
        "requirements.txt",
        "security_requirements.txt",
        "requirements-performance.txt",
        "uv.lock",
        "=1.0.0"  # keep this file as is
    }

    # Essential directories to keep
    essential_dirs = {
        "app",
        "web",
        "tests",
        "scripts",
        "docs",
        "alembic",
        "alembic_migrations",
        "config",
        "migrations",
        "storage",
        "inbox",
        "exports"
    }

    print("Starting final cleanup...")

    # Create necessary subdirectories
    (root_dir / "docs" / "reports").mkdir(parents=True, exist_ok=True)
    (root_dir / "fixtures").mkdir(exist_ok=True)
    (root_dir / "docs" / "guides").mkdir(parents=True, exist_ok=True)
    (root_dir / "docs" / "analysis").mkdir(parents=True, exist_ok=True)

    # Move MD files to docs/
    print("\n1. Moving documentation files...")
    md_files_to_move = [
        "UX_TESTING_ANALYSIS_REPORT.md",
        "SECURITY_ASSESSMENT_REPORT.md",
        "CFO_DIGEST_IMPLEMENTATION_SUMMARY.md",
        "CFO_DIGEST_QUICK_REFERENCE.md",
        "RBAC_IMPLEMENTATION_SUMMARY.md",
        "PERFORMANCE_OPTIMIZATION_GUIDE.md",
        "PERFORMANCE_IMPLEMENTATION_SUMMARY.md",
        "TEST_DEMO_README.md",
        "VALIDATION_FRAMEWORK_ANALYSIS_REPORT.md",
        "UI_HITL_TESTING_REPORT.md",
        "UI_TESTING_EXECUTION_SUMMARY.md",
        "COMPREHENSIVE_VALIDATION_ANALYSIS_FINAL_REPORT.md",
        "SECURITY_COMPLIANCE_TEST_REPORT.md",
        "COMPREHENSIVE_AP_AR_E2E_TEST_REPORT.md",
        "COMPREHENSIVE_SECURITY_COMPLIANCE_REPORT.md",
        "INTEGRATION_RELIABILITY_TESTING_SUMMARY.md",
        "ACCEPTANCE_CRITERIA_TEST_REPORT.md",
        "SECURITY_COMPLIANCE_EXECUTIVE_SUMMARY.md",
        "n8n-workflows-for-import.md",
        "N8N_INTEGRATION_GUIDE.md",
        "SWAPPABLE_INTEGRATION_GUIDE.md",
        "REORGANIZATION_SUMMARY.md",
        "prd.md"
    ]

    for md_file in md_files_to_move:
        src = root_dir / md_file
        if src.exists():
            dest = root_dir / "docs" / md_file
            if md_file.endswith("_GUIDE.md"):
                dest = root_dir / "docs" / "guides" / md_file
            elif md_file.endswith("_REPORT.md") or "TEST_REPORT" in md_file:
                dest = root_dir / "docs" / "analysis" / md_file
            print(f"Moving {src} -> {dest}")
            shutil.move(str(src), str(dest))

    # Move test files to tests/
    print("\n2. Moving test files...")
    test_files_to_move = [
        "validate_migrations.py",
        "test_enhanced_extraction_validation.py",
        "test_ar_models_simple.py",
        "test_n8n_simple.py",
        "test_ar_integration.py",
        "test_cfo_digest_integration.py",
        "ux_test_comprehensive.py",
        "test_rbac_system.py",
        "security_compliance_test.py",
        "acceptance_criteria_test_suite.py",
        "test_ap_intake.py"
    ]

    for test_file in test_files_to_move:
        src = root_dir / test_file
        if src.exists():
            dest = root_dir / "tests" / test_file
            print(f"Moving {src} -> {dest}")
            shutil.move(str(src), str(dest))

    # Move utility files to scripts/
    print("\n3. Moving utility files...")
    utility_files_to_move = [
        "fix_schema.py",
        "focused_security_audit.py",
        "run_security_audit.py",
        "fix_integrations.py",
        "database_performance_dashboard.py",
        "automated_security_validator.py",
        "init_database.sql",
        "batch_move_files.py",
        "final_cleanup.py"
    ]

    for util_file in utility_files_to_move:
        src = root_dir / util_file
        if src.exists():
            dest = root_dir / "scripts" / util_file
            print(f"Moving {src} -> {dest}")
            shutil.move(str(src), str(dest))

    # Move reports and other files
    print("\n4. Moving report files...")
    report_files = [
        ("frontend-screenshot.html", "docs/reports/"),
        ("MANUAL_UI_TEST_SCRIPT.js", "docs/reports/"),
        ("ux_test_playwright.js", "docs/reports/"),
        ("ux_test_results.json", "docs/reports/"),
        ("service_status_report.json", "docs/reports/"),
        ("focused_validation_diagnostic_report.txt", "docs/reports/"),
        ("focused_ap_ar_e2e_report_20251110_183320.json", "docs/reports/"),
        ("focused_ap_ar_e2e_report_20251113_110049.json", "docs/reports/"),
        ("sample_invoice.txt", "fixtures/")
    ]

    for report_file, dest_dir in report_files:
        src = root_dir / report_file
        if src.exists():
            dest = root_dir / dest_dir / report_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"Moving {src} -> {dest}")
            shutil.move(str(src), str(dest))

    # Move package.json to web/ if it's for frontend
    package_json = root_dir / "package.json"
    web_package_json = root_dir / "web" / "package.json"
    if package_json.exists() and not web_package_json.exists():
        print(f"Moving package.json to web/")
        shutil.move(str(package_json), str(web_package_json))

    # Clean up any remaining files that shouldn't be in root
    print("\n5. Final cleanup...")
    for item in root_dir.iterdir():
        if item.is_file():
            if item.name not in essential_files and not item.name.startswith('.'):
                print(f"Warning: Unexpected file in root: {item.name}")

    print("\n✅ Final cleanup completed!")
    print("\nRoot directory now contains only essential files:")

    # List current root directory contents
    for item in sorted(root_dir.iterdir()):
        if item.name.startswith('.'):
            continue
        if item.is_file():
            print(f"  📄 {item.name}")
        elif item.is_dir():
            print(f"  📁 {item.name}/")

if __name__ == "__main__":
    final_cleanup()