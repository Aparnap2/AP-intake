#!/usr/bin/env python3

import os
import shutil
from pathlib import Path

def move_md_files():
    """Move all .md files except README.md and CLAUDE.md to docs/ directory"""
    root_dir = Path("/home/aparna/Desktop/ap_intake")
    docs_dir = root_dir / "docs"

    # Create docs directory if it doesn't exist
    docs_dir.mkdir(exist_ok=True)

    # Files to keep in root
    keep_files = {"README.md", "CLAUDE.md"}

    # Move all .md files except the ones to keep
    for md_file in root_dir.glob("*.md"):
        if md_file.name not in keep_files:
            dest = docs_dir / md_file.name
            print(f"Moving {md_file} -> {dest}")
            shutil.move(str(md_file), str(dest))

def move_test_files():
    """Move all test .py files to tests/ directory"""
    root_dir = Path("/home/aparna/Desktop/ap_intake")
    tests_dir = root_dir / "tests"

    # Create tests directory if it doesn't exist
    tests_dir.mkdir(exist_ok=True)

    # Test file patterns to move
    test_patterns = [
        "test_*.py",
        "*_test.py",
        "acceptance_criteria_test_suite.py",
        "security_compliance_test.py",
        "ux_test_comprehensive.py",
    ]

    for pattern in test_patterns:
        for test_file in root_dir.glob(pattern):
            # Skip if already in tests directory
            if tests_dir in test_file.parents:
                continue

            dest = tests_dir / test_file.name
            print(f"Moving {test_file} -> {dest}")
            shutil.move(str(test_file), str(dest))

def move_utility_files():
    """Move all utility .py files to scripts/ directory"""
    root_dir = Path("/home/aparna/Desktop/ap_intake")
    scripts_dir = root_dir / "scripts"

    # Create scripts directory if it doesn't exist
    scripts_dir.mkdir(exist_ok=True)

    # Utility file patterns to move
    utility_patterns = [
        "validate_migrations.py",
        "fix_schema.py",
        "focused_security_audit.py",
        "run_security_audit.py",
        "fix_integrations.py",
        "database_performance_dashboard.py",
        "automated_security_validator.py",
    ]

    for pattern in utility_patterns:
        for util_file in root_dir.glob(pattern):
            # Skip if already in scripts directory
            if scripts_dir in util_file.parents:
                continue

            dest = scripts_dir / util_file.name
            print(f"Moving {util_file} -> {dest}")
            shutil.move(str(util_file), str(dest))

def cleanup_other_files():
    """Move other files to appropriate directories"""
    root_dir = Path("/home/aparna/Desktop/ap_intake")

    # Move reports and other specialized files
    report_files = [
        "frontend-screenshot.html",
        "MANUAL_UI_TEST_SCRIPT.js",
        "ux_test_playwright.js",
        "ux_test_results.json",
        "package.json",
        "sample_invoice.txt",
    ]

    # Move to appropriate directories
    for report_file in report_files:
        src = root_dir / report_file
        if src.exists():
            if report_file.endswith('.html') or report_file.endswith('.js') or report_file.endswith('.json'):
                # Move to docs/reports
                reports_dir = root_dir / "docs" / "reports"
                reports_dir.mkdir(parents=True, exist_ok=True)
                dest = reports_dir / report_file
            elif report_file == "package.json":
                # Move to web directory
                dest = root_dir / "web" / report_file
            elif report_file == "sample_invoice.txt":
                # Move to fixtures or data directory
                fixtures_dir = root_dir / "fixtures"
                fixtures_dir.mkdir(exist_ok=True)
                dest = fixtures_dir / report_file
            else:
                # Default to scripts
                dest = root_dir / "scripts" / report_file

            if dest != src:
                print(f"Moving {src} -> {dest}")
                shutil.move(str(src), str(dest))

if __name__ == "__main__":
    print("Starting batch file organization...")

    try:
        print("\n1. Moving .md files to docs/...")
        move_md_files()

        print("\n2. Moving test files to tests/...")
        move_test_files()

        print("\n3. Moving utility files to scripts/...")
        move_utility_files()

        print("\n4. Cleaning up other files...")
        cleanup_other_files()

        print("\nFile organization completed successfully!")

    except Exception as e:
        print(f"Error during file organization: {e}")
        import traceback
        traceback.print_exc()