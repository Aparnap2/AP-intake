# Testing Guide for AP Intake & Validation

This comprehensive guide covers all aspects of testing the AP Intake & Validation system, from running tests to writing new ones.

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Test Types](#test-types)
5. [Writing Tests](#writing-tests)
6. [Test Data Management](#test-data-management)
7. [Performance Testing](#performance-testing)
8. [CI/CD Integration](#cicd-integration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Overview

The AP Intake & Validation system uses a multi-layered testing strategy based on the testing pyramid:

- **Unit Tests (70%)**: Test individual components and business logic
- **Integration Tests (25%)**: Test API endpoints and external service integrations
- **End-to-End Tests (5%)**: Test complete workflows and performance

### Key Technologies

- **pytest**: Primary testing framework
- **pytest-asyncio**: Async testing support
- **pytest-cov**: Coverage reporting
- **Factory Boy**: Test data generation
- **httpx**: Async HTTP client for API testing
- **Faker**: Realistic test data generation

## Test Structure

```
tests/
├── unit/                   # Unit tests (70%)
│   ├── services/
│   │   ├── test_docling_service.py
│   │   ├── test_validation_service.py
│   │   ├── test_validation_service_enhanced.py
│   │   └── test_storage_service.py
│   ├── models/
│   └── utils/
├── integration/            # Integration tests (25%)
│   ├── api/
│   │   └── test_invoices.py
│   ├── database/
│   └── external/
├── performance/            # Performance and load tests
│   ├── test_api_performance.py
│   └── test_load_testing.py
├── e2e/                    # End-to-end tests (5%)
├── factories/              # Test data factories
│   ├── __init__.py
│   ├── invoice_factory.py
│   ├── vendor_factory.py
│   ├── extraction_factory.py
│   └── user_factory.py
├── fixtures/               # Test fixtures
└── conftest/              # Test configuration
    └── test_config.py
```

## Running Tests

### Using the Test Runner Script

The preferred way to run tests is using the provided test runner script:

```bash
# Run unit tests with coverage
python scripts/run_tests.py --unit

# Run integration tests
python scripts/run_tests.py --integration

# Run performance tests
python scripts/run_tests.py --performance

# Run load tests
python scripts/run_tests.py --load

# Run all tests
python scripts/run_tests.py --all --coverage

# Run CI test suite
python scripts/run_tests.py --ci

# Run quick tests for development
python scripts/run_tests.py --quick

# Run smoke tests
python scripts/run_tests.py --smoke

# Run tests in parallel
python scripts/run_tests.py --all --parallel --workers 4
```

### Using pytest Directly

You can also use pytest directly:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_validation_service.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific markers
pytest -m "unit"
pytest -m "integration"
pytest -m "performance"
pytest -m "not slow"

# Run in parallel
pytest -n auto

# Run with verbose output
pytest -v
```

### Test Markers

The test suite uses several markers to categorize tests:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.e2e`: End-to-end tests
- `@pytest.mark.load`: Load tests

## Test Types

### Unit Tests

Unit tests test individual components in isolation:

```python
@pytest.mark.asyncio
async def test_validate_invoice_success(validation_service, valid_extraction_data):
    """Test successful invoice validation."""
    result = await validation_service.validate_invoice(valid_extraction_data)

    assert result is not None
    assert result["passed"] is True
    assert result["confidence_score"] >= 0.8
```

### Integration Tests

Integration tests test how components work together:

```python
@pytest.mark.asyncio
async def test_upload_invoice_success(async_client, db_session):
    """Test successful invoice upload."""
    pdf_content = b"%PDF-1.4\nfake pdf content"
    file_data = io.BytesIO(pdf_content)
    files = {"file": ("test_invoice.pdf", file_data, "application/pdf")}

    with patch.object(StorageService, 'store_file', new_callable=AsyncMock):
        response = await async_client.post("/api/v1/invoices/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
```

### Performance Tests

Performance tests measure response times and resource usage:

```python
@pytest.mark.performance
async def test_upload_small_file_performance(async_client, sample_pdf_content):
    """Test upload performance with small file (1MB)."""
    metrics = await measure_async_execution(upload_file)

    assert metrics["success"]
    assert metrics["duration_ms"] < 1000
    assert metrics["memory_delta_mb"] < 50
```

## Writing Tests

### Test Structure

Follow the AAA pattern (Arrange, Act, Assert):

```python
@pytest.mark.asyncio
async def test_invoice_processing_workflow():
    # Arrange
    invoice_data = ExtractionDataFactory()
    validation_service = ValidationService()

    # Act
    result = await validation_service.validate_invoice(invoice_data)

    # Assert
    assert result["passed"] is True
    assert "issues" in result
    assert len(result["issues"]) == 0
```

### Using Fixtures

Leverage existing fixtures for common setup:

```python
async def test_with_sample_data(async_client, db_session, sample_invoice_record):
    """Test using sample invoice record fixture."""
    response = await async_client.get(f"/api/v1/invoices/{sample_invoice_record.id}")
    assert response.status_code == 200
```

### Mocking External Services

Use mocks for external dependencies:

```python
async def test_with_mocked_service():
    """Test with mocked storage service."""
    with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
        mock_storage.return_value = {"file_path": "/tmp/test.pdf"}

        # Test code that uses StorageService
        result = await process_invoice("test.pdf")

        mock_storage.assert_called_once()
```

## Test Data Management

### Using Factory Boy

Use factories for generating realistic test data:

```python
# Create a single invoice
invoice = InvoiceFactory.create(status=InvoiceStatus.PROCESSED)

# Create multiple invoices
invoices = InvoiceFactory.create_batch(10, status=InvoiceStatus.RECEIVED)

# Create with custom attributes
high_value_invoice = InvoiceFactory.create(
    file_size=50000,
    status=InvoiceStatus.REVIEW
)
```

### Available Factories

- `InvoiceFactory`: Generate invoice records
- `VendorFactory`: Generate vendor records
- `ExtractionDataFactory`: Generate document extraction data
- `UserFactory`: Generate user records

### Specialized Factories

- `LowConfidenceExtractionFactory`: Data with low confidence scores
- `CorruptedExtractionFactory`: Invalid/incomplete data
- `ProcessedInvoiceFactory`: Fully processed invoices
- `HighValueInvoiceFactory`: Large invoice amounts

## Performance Testing

### Running Performance Tests

```bash
# Run all performance tests
python scripts/run_tests.py --performance

# Run specific performance test
pytest tests/performance/test_api_performance.py::TestInvoiceUploadPerformance::test_upload_small_file_performance -v
```

### Performance Metrics

Performance tests measure:

- **Response Time**: Time to complete operations
- **Memory Usage**: Memory consumption during tests
- **CPU Usage**: Processor utilization
- **Throughput**: Requests per second
- **Success Rate**: Percentage of successful operations

### Performance Benchmarks

Default performance expectations:

- **File Upload**: <1s for 1MB files
- **List API**: <500ms for 100 records
- **Get API**: <100ms for single record
- **Memory Usage**: <50MB increase per operation
- **Success Rate**: >95% under load

## Load Testing

### Running Load Tests

```bash
# Run load tests
python scripts/run_tests.py --load

# Run specific load test
pytest tests/performance/test_load_testing.py::TestLoadTesting::test_upload_load_test_small -v -s
```

### Load Test Scenarios

- **Concurrent Uploads**: Multiple simultaneous file uploads
- **Sustained Load**: Extended period of continuous requests
- **Mixed Workload**: Different types of API operations
- **Resource Monitoring**: System resource usage under load

### Load Test Metrics

- **Concurrent Users**: Number of simultaneous users
- **Requests Per Second**: Throughput measurement
- **Response Time Percentiles**: P50, P95, P99 response times
- **Error Rate**: Percentage of failed requests
- **Resource Utilization**: CPU and memory usage

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        run: python scripts/run_tests.py --ci

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: python scripts/run_tests.py --quick
        language: system
        pass_filenames: false
        always_run: true
```

## Best Practices

### Test Writing

1. **Descriptive Names**: Use clear, descriptive test method names
2. **Single Responsibility**: Test one thing per test
3. **Test Independence**: Tests should not depend on each other
4. **Arrange-Act-Assert**: Follow AAA pattern
5. **Realistic Data**: Use factories for realistic test data

### Test Organization

1. **Logical Grouping**: Group related tests in classes
2. **Markers Usage**: Use appropriate markers for test categorization
3. **Fixtures**: Use fixtures for common setup/teardown
4. **Mocks**: Mock external dependencies

### Performance Testing

1. **Baselines**: Establish performance baselines
2. **Isolation**: Run performance tests in isolation
3. **Environment**: Use consistent testing environment
4. **Monitoring**: Monitor system resources during tests

### CI/CD

1. **Fast Feedback**: Run quick tests first
2. **Parallel Execution**: Use parallel test execution
3. **Coverage Gates**: Set minimum coverage thresholds
4. **Performance Gates**: Set performance regression checks

## Troubleshooting

### Common Issues

#### Test Database Issues

```bash
# Reset test database
python scripts/cleanup_test_db.py

# Check database connection
python scripts/check_db_connection.py
```

#### Async Test Issues

```python
# Ensure async tests are properly marked
@pytest.mark.asyncio
async def test_async_function():
    await some_async_function()
```

#### Factory Issues

```python
# Ensure factories are properly imported
from tests.factories import InvoiceFactory, VendorFactory

# Check factory configuration
factory = InvoiceFactory()
invoice = factory.build()
```

#### Performance Test Issues

```bash
# Run performance tests with more memory
pytest tests/performance/ -v --benchmark-only --benchmark-sort=mean

# Check system resources
python scripts/check_system_resources.py
```

### Debugging Tips

1. **Verbose Output**: Use `-v` flag for detailed output
2. **Print Statements**: Add debug prints for troubleshooting
3. **Breakpoints**: Use `breakpoint()` for interactive debugging
4. **Test Isolation**: Run single tests to isolate issues
5. **Log Analysis**: Check application logs for errors

### Getting Help

1. **Documentation**: Check the test documentation
2. **Examples**: Look at existing tests for examples
3. **Team Communication**: Ask team members for guidance
4. **Issue Tracking**: Create issues for test failures

## Continuous Improvement

### Test Metrics to Track

- **Test Coverage**: Maintain >85% coverage
- **Test Execution Time**: Keep test runs under 10 minutes
- **Flaky Tests**: Eliminate all flaky tests
- **Performance Regression**: Monitor for performance degradation

### Regular Reviews

1. **Weekly**: Review test failures and flaky tests
2. **Monthly**: Review coverage and performance metrics
3. **Quarterly**: Review and update testing strategy
4. **Annually**: Major testing framework and tool updates

### Test Maintenance

1. **Regular Updates**: Keep test dependencies updated
2. **Refactoring**: Refactor tests for better maintainability
3. **Documentation**: Keep test documentation current
4. **Training**: Regular team training on testing best practices

This testing guide provides a comprehensive foundation for maintaining high-quality tests in the AP Intake & Validation system. Regular review and updates to this guide ensure it continues to meet the evolving needs of the project.