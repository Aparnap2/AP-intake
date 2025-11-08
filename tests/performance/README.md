# Performance Testing Suite for AP Intake & Validation System

This comprehensive performance testing suite provides thorough load testing, stress testing, and performance monitoring capabilities for the AP Intake & Validation System.

## 🚀 Quick Start

### Prerequisites

1. **Ensure the AP Intake service is running:**
   ```bash
   # Start with Docker
   docker-compose up -d

   # Or run locally
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Install required dependencies:**
   ```bash
   # For basic testing
   pip install httpx psutil pytest pytest-asyncio

   # For external load testing tools
   # Install Apache Bench (ab)
   sudo apt-get install apache2-utils  # Ubuntu/Debian
   brew install apache2               # macOS

   # Install wrk
   sudo apt-get install wrk           # Ubuntu/Debian
   brew install wrk                   # macOS

   # For database testing
   pip install psycopg2-binary numpy
   ```

### Quick Performance Check

Run a quick performance test to get immediate feedback:

```bash
cd tests/performance
python quick_performance_test.py
```

This will:
- Test basic API response times
- Check concurrent load handling (10 requests)
- Verify database query performance
- Monitor memory usage
- Check error rates

### Full Performance Test Suite

Run the comprehensive performance test suite:

```bash
cd tests/performance
python run_performance_tests.py --suite all --duration 10 --users 20
```

## 📊 Testing Components

### 1. Comprehensive Performance Tests (`comprehensive_performance_test.py`)

Custom Python-based load testing with detailed metrics collection.

**Features:**
- Concurrent user simulation
- Real-time resource monitoring
- Response time analysis (P50, P95, P99)
- Memory leak detection
- Sustained load testing

**Usage:**
```bash
# Run as pytest
pytest tests/performance/test_comprehensive_performance.py -v -s

# Run standalone
python comprehensive_performance_test.py --url http://localhost:8000 --users 50 --requests 10
```

**Key Metrics:**
- Response times (avg, median, P95, P99)
- Success rate
- Requests per second
- CPU and memory usage
- Error analysis

### 2. External Load Testing (`external_load_testing.py`)

Integration with professional load testing tools.

**Supported Tools:**
- **Apache Bench (ab):** Simple, reliable HTTP load testing
- **wrk:** Modern HTTP benchmarking tool
- **Custom Load Tester:** Advanced scenarios and mixed workloads

**Usage:**
```bash
# Test with Apache Bench
python external_load_testing.py --tool ab --users 25 --requests 500

# Test with wrk
python external_load_testing.py --tool wrk --users 50 --duration 60

# Test all tools
python external_load_testing.py --tool all --users 30 --duration 120
```

**Test Scenarios:**
- Basic GET requests
- POST requests with data
- File upload performance
- Mixed workload testing
- Comparative analysis between tools

### 3. Database Performance Testing (`database_performance_test.py`)

Comprehensive database performance analysis under load.

**Test Types:**
- Connection pool stress testing
- SELECT query performance (simple, moderate, complex)
- INSERT performance (single and batch)
- Transaction throughput
- Mixed database workloads
- Index performance analysis
- Database stress testing

**Usage:**
```bash
# Run all database tests
pytest tests/performance/test_database_performance.py -v

# Run specific test types
python database_performance_test.py --test connection_pool --connections 30
python database_performance_test.py --test select --operations 1000
python database_performance_test.py --test stress --duration 120
```

**Key Metrics:**
- Queries per second
- Average query time
- Connection pool efficiency
- Transaction throughput
- Index performance impact

### 4. Performance Monitoring (`performance_monitor.py`)

Real-time system monitoring during tests.

**Monitored Metrics:**
- **System:** CPU, memory, disk, network I/O
- **Database:** Connections, cache hit ratio, query performance
- **Application:** Request rates, response times, error rates

**Usage:**
```bash
# Monitor for 5 minutes
python performance_monitor.py --duration 300 --interval 1.0

# Export monitoring data
python performance_monitor.py --duration 600 --output monitoring_data.json

# Generate performance report
python performance_monitor.py --duration 300 --report performance_report.md
```

**Alerting:**
- Configurable performance thresholds
- Real-time alert generation
- Performance degradation detection

## 🎯 Test Scenarios

### Load Testing Scenarios

1. **Light Load (10 concurrent users)**
   ```bash
   python run_performance_tests.py --users 10 --duration 5 --suite load
   ```

2. **Medium Load (25 concurrent users)**
   ```bash
   python run_performance_tests.py --users 25 --duration 10 --suite load
   ```

3. **Heavy Load (50+ concurrent users)**
   ```bash
   python run_performance_tests.py --users 50 --duration 15 --suite load
   ```

### Stress Testing Scenarios

1. **Gradual Ramp-up Stress Test**
   ```bash
   python run_performance_tests.py --suite stress --users 100
   ```

2. **Sustained High Load**
   ```bash
   python run_performance_tests.py --suite endurance --duration 30 --users 25
   ```

3. **Database Stress Test**
   ```bash
   python database_performance_test.py --test stress --max-connections 100
   ```

### Performance Regression Testing

1. **Baseline Performance Test**
   ```bash
   python run_performance_tests.py --suite all --duration 5 --users 20 \
     --report-dir ./baseline_performance
   ```

2. **Compare with Previous Results**
   - Review performance reports
   - Check for response time degradation
   - Monitor throughput changes
   - Verify error rates remain stable

## 📈 Performance Targets

### API Performance Targets
- **Response Time:** < 200ms (average), < 500ms (P95)
- **Throughput:** > 100 requests/second
- **Success Rate:** > 99.5%
- **Error Rate:** < 0.5%

### Database Performance Targets
- **Query Response:** < 100ms (simple), < 500ms (complex)
- **Connection Pool:** < 80% utilization
- **Query Throughput:** > 1000 queries/second
- **Cache Hit Ratio:** > 95%

### System Resource Targets
- **CPU Usage:** < 80% (average), < 95% (peak)
- **Memory Usage:** < 85% (no memory leaks)
- **Disk I/O:** < 80% utilization
- **Network:** < 70% bandwidth utilization

## 📋 Test Reports

### Report Types

1. **JSON Results:** Machine-readable detailed metrics
2. **Markdown Reports:** Human-readable analysis and recommendations
3. **Monitoring Data:** Time-series performance metrics
4. **Comparative Reports:** Before/after performance analysis

### Report Contents

**Performance Summary:**
- Overall system health assessment
- Key performance indicators
- SLA compliance status
- Bottleneck identification

**Detailed Metrics:**
- Response time distributions
- Throughput measurements
- Resource utilization graphs
- Error analysis

**Recommendations:**
- Performance optimization suggestions
- Infrastructure scaling recommendations
- Configuration tuning advice
- Monitoring setup guidance

## 🔧 Configuration

### Performance Thresholds

Customize alert thresholds in `performance_monitor.py`:

```python
alert_thresholds = {
    "cpu_percent": 80.0,           # CPU usage alert threshold
    "memory_percent": 85.0,        # Memory usage alert threshold
    "disk_usage_percent": 90.0,    # Disk usage alert threshold
    "error_rate": 5.0,             # Error rate alert threshold (%)
    "avg_response_time_ms": 2000.0, # Response time alert threshold
    "queue_size": 100,             # Queue size alert threshold
    "database_connections": 80      # Database connection alert threshold
}
```

### Test Parameters

Adjust test parameters based on your environment:

```bash
# For development environments
python run_performance_tests.py --users 10 --duration 5 --suite load

# For staging environments
python run_performance_tests.py --users 50 --duration 15 --suite all

# For production-like testing
python run_performance_tests.py --users 100 --duration 30 --suite all
```

## 🚨 Troubleshooting

### Common Issues

1. **Service Not Running**
   ```
   ❌ Cannot connect to service at http://localhost:8000
   ```
   **Solution:** Start the AP Intake service before running tests

2. **Permission Denied for External Tools**
   ```
   ❌ Apache Bench (ab) is not available
   ```
   **Solution:** Install Apache Bench or wrk:
   ```bash
   sudo apt-get install apache2-utils wrk
   ```

3. **Database Connection Errors**
   ```
   ❌ Failed to collect database metrics
   ```
   **Solution:** Ensure database is running and accessible

4. **High Memory Usage**
   ```
   ⚠️ High memory increase: 150MB
   ```
   **Solution:** Check for memory leaks in application code

5. **Low Success Rate**
   ```
   ❌ Success rate under load: 85%
   ```
   **Solution:** Investigate application logs for errors

### Performance Issues Diagnosis

1. **Slow Response Times**
   - Check database query performance
   - Verify external service response times
   - Analyze application code bottlenecks

2. **High Error Rates**
   - Review application logs
   - Check database connection limits
   - Verify resource availability

3. **Memory Leaks**
   - Monitor memory usage over time
   - Check for unclosed database connections
   - Review file handle management

4. **Database Performance**
   - Analyze slow query logs
   - Check index usage
   - Monitor connection pool efficiency

## 📚 Best Practices

### Test Environment Setup

1. **Isolated Testing Environment**
   - Use dedicated test infrastructure
   - Avoid testing on production systems
   - Ensure consistent test data

2. **Realistic Test Data**
   - Use production-like data volumes
   - Include various data patterns
   - Test with different file sizes

3. **Consistent Test Conditions**
   - Run tests at similar times
   - Document system configuration
   - Monitor background processes

### Test Execution

1. **Baseline Establishment**
   - Run initial baseline tests
   - Document performance expectations
   - Establish monitoring baseline

2. **Gradual Load Increase**
   - Start with light loads
   - Gradually increase concurrency
   - Monitor system behavior

3. **Multiple Test Runs**
   - Run tests multiple times
   - Average results for consistency
   - Identify performance variations

### Results Analysis

1. **Comprehensive Documentation**
   - Document test conditions
   - Save detailed metrics
   - Track performance trends

2. **Root Cause Analysis**
   - Investigate performance issues
   - Identify bottleneck sources
   - Document improvement actions

3. **Continuous Improvement**
   - Regular performance testing
   - Monitor production performance
   - Update performance targets

## 🔗 Integration with CI/CD

### GitHub Actions Example

```yaml
name: Performance Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  performance-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        sudo apt-get install -y apache2-utils wrk

    - name: Start application
      run: |
        docker-compose up -d
        sleep 30

    - name: Run quick performance test
      run: |
        cd tests/performance
        python quick_performance_test.py --url http://localhost:8000

    - name: Run full performance suite
      run: |
        cd tests/performance
        python run_performance_tests.py --suite load --duration 5 --users 20

    - name: Upload performance reports
      uses: actions/upload-artifact@v2
      with:
        name: performance-reports
        path: tests/performance/performance_reports/
```

### Performance Gates

Set up performance gates in your CI/CD pipeline:

```bash
# Example performance gate script
#!/bin/bash

python quick_performance_test.py --url $SERVICE_URL

# Check if performance meets minimum standards
if [ $? -ne 0 ]; then
    echo "Performance tests failed"
    exit 1
fi

# Parse results for specific metrics
SUCCESS_RATE=$(cat quick_performance_test_*.json | jq '.tests.concurrent_load.success_rate')

if (( $(echo "$SUCCESS_RATE < 95" | bc -l) )); then
    echo "Success rate below 95%: $SUCCESS_RATE%"
    exit 1
fi

echo "Performance tests passed"
```

## 📞 Support

For questions or issues with the performance testing suite:

1. **Check the logs:** Review detailed test output for error messages
2. **Verify prerequisites:** Ensure all dependencies are installed
3. **Test environment:** Confirm the AP Intake service is running and accessible
4. **Documentation:** Review this README and inline code documentation
5. **Issues:** Report bugs or request features via the project issue tracker

---

**Happy Performance Testing! 🚀**