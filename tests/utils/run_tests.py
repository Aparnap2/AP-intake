#!/usr/bin/env python3
"""
Comprehensive test runner for AP Intake & Validation system.

This script provides different test execution modes and reporting options
to accommodate various testing scenarios in CI/CD and development workflows.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def run_command(cmd: List[str], description: str) -> int:
    """Run a command with error handling and output."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)

    if result.returncode == 0:
        print(f"✅ {description} - PASSED")
    else:
        print(f"❌ {description} - FAILED (exit code: {result.returncode})")

    return result.returncode


def run_unit_tests(coverage: bool = True, verbose: bool = False) -> int:
    """Run unit tests with optional coverage."""
    cmd = ["python", "-m", "pytest", "tests/unit", "-m", "not slow and not performance"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=85"
        ])

    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose: bool = False) -> int:
    """Run integration tests."""
    cmd = ["python", "-m", "pytest", "tests/integration", "-m", "not slow and not performance"]

    if verbose:
        cmd.append("-v")

    return run_command(cmd, "Integration Tests")


def run_performance_tests(verbose: bool = False) -> int:
    """Run performance tests."""
    cmd = ["python", "-m", "pytest", "tests/performance", "-m", "performance", "--benchmark-only"]

    if verbose:
        cmd.append("-v")

    return run_command(cmd, "Performance Tests")


def run_load_tests(verbose: bool = False) -> int:
    """Run load tests."""
    cmd = ["python", "-m", "pytest", "tests/performance", "-m", "load"]

    if verbose:
        cmd.append("-v")

    return run_command(cmd, "Load Tests")


def run_e2e_tests(verbose: bool = False) -> int:
    """Run end-to-end tests."""
    cmd = ["python", "-m", "pytest", "tests/e2e", "-m", "e2e"]

    if verbose:
        cmd.append("-v")

    return run_command(cmd, "End-to-End Tests")


def run_all_tests(
    include_slow: bool = False,
    include_performance: bool = False,
    include_load: bool = False,
    coverage: bool = True,
    verbose: bool = False,
    parallel: bool = False,
    workers: Optional[int] = None
) -> int:
    """Run all tests based on specified options."""

    # Base test command
    markers = ["not slow", "not performance", "not load"]

    if include_slow:
        markers = [m for m in markers if m != "not slow"]

    if include_performance:
        markers = [m for m in markers if m != "not performance"]

    if include_load:
        markers = [m for m in markers if m != "not load"]

    cmd = ["python", "-m", "pytest", "tests"]

    if markers:
        cmd.extend(["-m", " and ".join(markers)])

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])

    if parallel:
        cmd.extend(["-n", str(workers or "auto")])

    return run_command(cmd, "All Tests")


def run_quick_tests() -> int:
    """Run quick tests for development feedback."""
    cmd = [
        "python", "-m", "pytest",
        "tests/unit",
        "tests/integration/api/test_invoices.py",
        "-m", "not slow and not performance and not load",
        "--tb=short",
        "-q"
    ]

    return run_command(cmd, "Quick Tests")


def run_ci_tests() -> int:
    """Run comprehensive tests for CI/CD pipeline."""
    exit_code = 0

    # Unit tests with coverage
    exit_code |= run_unit_tests(coverage=True, verbose=False)
    if exit_code != 0:
        return exit_code

    # Integration tests
    exit_code |= run_integration_tests(verbose=False)
    if exit_code != 0:
        return exit_code

    # Performance regression tests (only basic ones, not slow)
    cmd = [
        "python", "-m", "pytest",
        "tests/performance/test_api_performance.py::TestPerformanceRegression",
        "-m", "performance and not slow",
        "--benchmark-only"
    ]
    exit_code |= run_command(cmd, "Performance Regression Tests")

    return exit_code


def run_smoke_tests() -> int:
    """Run smoke tests to verify basic functionality."""
    smoke_tests = [
        "tests/unit/test_docling_service.py::TestDoclingService::test_service_initialization",
        "tests/unit/test_validation_service_enhanced.py::TestValidationServiceBasicValidation::test_validate_invoice_success",
        "tests/integration/api/test_invoices.py::TestInvoiceUploadEndpoint::test_upload_invoice_success",
        "tests/integration/api/test_invoices.py::TestInvoiceListEndpoint::test_list_invoices_default",
    ]

    cmd = ["python", "-m", "pytest", "-v"] + smoke_tests
    return run_command(cmd, "Smoke Tests")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Test runner for AP Intake & Validation system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --unit                          # Run unit tests
  %(prog)s --integration                   # Run integration tests
  %(prog)s --performance                   # Run performance tests
  %(prog)s --all --coverage                # Run all tests with coverage
  %(prog)s --ci                            # Run CI test suite
  %(prog)s --quick                         # Run quick tests for development
  %(prog)s --smoke                         # Run smoke tests
  %(prog)s --all --parallel --workers 4    # Run all tests in parallel
        """
    )

    # Test type options
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--load", action="store_true", help="Run load tests")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    # Preset options
    parser.add_argument("--ci", action="store_true", help="Run CI test suite")
    parser.add_argument("--quick", action="store_true", help="Run quick tests for development")
    parser.add_argument("--smoke", action="store_true", help="Run smoke tests")

    # Configuration options
    parser.add_argument("--coverage", action="store_true", default=True, help="Generate coverage report")
    parser.add_argument("--no-coverage", dest="coverage", action="store_false", help="Skip coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--workers", type=int, help="Number of parallel workers")

    # Test inclusion options
    parser.add_argument("--include-slow", action="store_true", help="Include slow tests")
    parser.add_argument("--include-performance", action="store_true", help="Include performance tests")
    parser.add_argument("--include-load", action="store_true", help="Include load tests")

    args = parser.parse_args()

    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Validate arguments
    if sum([args.unit, args.integration, args.performance, args.load, args.e2e, args.all, args.ci, args.quick, args.smoke]) == 0:
        parser.print_help()
        return 1

    exit_code = 0

    # Run tests based on arguments
    if args.ci:
        exit_code = run_ci_tests()
    elif args.quick:
        exit_code = run_quick_tests()
    elif args.smoke:
        exit_code = run_smoke_tests()
    elif args.all:
        exit_code = run_all_tests(
            include_slow=args.include_slow,
            include_performance=args.include_performance,
            include_load=args.include_load,
            coverage=args.coverage,
            verbose=args.verbose,
            parallel=args.parallel,
            workers=args.workers
        )
    else:
        if args.unit:
            exit_code |= run_unit_tests(coverage=args.coverage, verbose=args.verbose)

        if args.integration:
            exit_code |= run_integration_tests(verbose=args.verbose)

        if args.performance:
            exit_code |= run_performance_tests(verbose=args.verbose)

        if args.load:
            exit_code |= run_load_tests(verbose=args.verbose)

        if args.e2e:
            exit_code |= run_e2e_tests(verbose=args.verbose)

    # Print summary
    print(f"\n{'='*60}")
    if exit_code == 0:
        print("🎉 All tests PASSED!")
    else:
        print("💥 Some tests FAILED!")
    print(f"{'='*60}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())