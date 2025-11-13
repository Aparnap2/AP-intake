# Performance Optimization Guide

## Overview

This guide provides comprehensive performance optimization strategies for the AP Intake & Validation system. The system has been instrumented with enterprise-grade performance monitoring and load testing capabilities.

## Performance Architecture

### 1. Performance Monitoring Stack

**Components:**
- **Performance Middleware**: Real-time request tracking with detailed metrics
- **Database Performance Service**: Query analysis and optimization
- **Load Testing Service**: Automated load testing with Locust
- **Profiling Service**: CPU and memory profiling
- **Prometheus Integration**: Metrics collection and alerting

**Key Metrics Tracked:**
- API response times (P50, P95, P99)
- Database query performance
- Memory and CPU usage
- Request throughput and error rates
- SLO compliance metrics

### 2. Load Testing Framework

**Test Types:**
- **Smoke Tests**: Basic functionality validation (5 users, 2 minutes)
- **Light Load**: Normal operational load (20 users, 5 minutes)
- **Medium Load**: Peak operational load (50 users, 10 minutes)
- **Heavy Load**: Stress testing (100 users, 15 minutes)
- **Stress Tests**: Maximum capacity testing (200 users)
- **Volume Tests**: Long-duration stability (4 hours)
- **Spike Tests**: Sudden traffic surge testing

## Performance Targets

### SLO Definitions

| Metric | Target | Measurement Window |
|--------|--------|-------------------|
| API Response Time (P95) | < 500ms | 5 minutes |
| API Response Time (P99) | < 1000ms | 5 minutes |
| Invoice Processing Time (P50) | < 30 seconds | 1 hour |
| Invoice Processing Time (P95) | < 60 seconds | 1 hour |
| System Throughput | > 100 RPS | 1 hour |
| Error Rate | < 1% | 5 minutes |
| System Availability | > 99.9% | 1 day |
| Database Query Time (P95) | < 100ms | 5 minutes |
| Cache Hit Ratio | > 95% | 5 minutes |

### Resource Limits

| Resource | Warning Threshold | Critical Threshold |
|----------|------------------|-------------------|
| CPU Usage | 70% | 90% |
| Memory Usage | 80% | 95% |
| Database Connections | 80% of pool | 95% of pool |
| Disk I/O | 70% | 90% |

## Performance Optimization Strategies

### 1. Database Optimization

#### Query Performance
```python
# Use the database performance service to identify slow queries
from app.services.database_performance_service import database_performance_service

# Get slow queries
slow_queries = await database_performance_service.get_slow_queries(limit=50)

# Get query performance summary
performance = await database_performance_service.get_query_performance_summary()
```

**Optimization Techniques:**
- Add appropriate indexes for frequently queried columns
- Use query parameterization to prevent SQL injection
- Implement query result caching for repeated queries
- Optimize JOIN operations and subqueries
- Use database connection pooling

#### Connection Management
```python
# Monitor database connections
metrics = await database_performance_service.collect_database_metrics()

# Check connection pool utilization
pool_utilization = metrics.active_connections / metrics.total_connections
```

### 2. API Performance Optimization

#### Response Time Optimization
```python
# Use performance profiling middleware
from app.middleware.performance_middleware import PerformanceMiddleware

# Profile specific endpoints
@app.middleware("http")
async def performance_middleware(request: Request, call_next):
    # Automatic profiling is enabled via PerformanceMiddleware
    pass
```

**Best Practices:**
- Implement proper caching strategies
- Use async/await for I/O operations
- Optimize JSON serialization/deserialization
- Implement response compression
- Use pagination for large datasets

#### Caching Strategies
```python
# Redis caching for frequently accessed data
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Cache invoice data
cache_key = f"invoice:{invoice_id}"
cached_data = redis_client.get(cache_key)
if not cached_data:
    data = await get_invoice_from_db(invoice_id)
    redis_client.setex(cache_key, 3600, json.dumps(data))  # 1 hour TTL
```

### 3. Memory Optimization

#### Memory Profiling
```python
# Use the profiling service to identify memory hotspots
from app.services.performance_profiling_service import performance_profiling_service

# Profile a function
@performance_profiling_service.profile_function("process_invoice")
async def process_invoice(invoice_data):
    # Function implementation
    pass
```

**Optimization Techniques:**
- Use generators instead of lists for large datasets
- Implement proper memory cleanup
- Use memory-efficient data structures
- Monitor for memory leaks
- Optimize image and file handling

### 4. CPU Optimization

#### Profiling CPU Usage
```python
# CPU profiling is automatically enabled in performance middleware
# Check profiling results
profile_summary = await performance_profiling_service.get_profile_summary()
```

**Optimization Strategies:**
- Optimize algorithmic complexity
- Use compiled extensions for CPU-intensive tasks
- Implement proper error handling to avoid exception overhead
- Use task queues for long-running operations
- Optimize regular expressions

## Load Testing and Validation

### Running Load Tests

```bash
# Install performance requirements
pip install -r requirements-performance.txt

# Run comprehensive performance validation
python scripts/performance_validation.py http://localhost:8000

# Run individual load tests
python tests/load_test/locustfile.py smoke    # Light test
python tests/load_test/locustfile.py medium   # Medium test
python tests/load_test/locustfile.py stress   # Stress test
```

### Load Test Scenarios

#### API Load Testing
```python
# Test API endpoints under load
scenarios = [
    {"endpoint": "/health", "weight": 3},
    {"endpoint": "/api/v1/invoices/", "weight": 2},
    {"endpoint": "/api/v1/auth/dev-token", "weight": 1},
    {"endpoint": "/metrics", "weight": 1}
]
```

#### Invoice Processing Load Testing
```python
# Test invoice processing workflow
async def test_invoice_processing_load():
    # Upload multiple invoices concurrently
    tasks = []
    for i in range(50):  # 50 concurrent uploads
        task = upload_invoice_task(f"invoice_{i}.pdf")
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results
```

### Performance Validation

```python
# Validate performance targets
async def validate_performance_targets():
    # API response times
    api_times = await get_api_response_times()
    assert api_times['p95'] < 500, f"P95 response time too high: {api_times['p95']}ms"

    # Throughput targets
    throughput = await measure_throughput()
    assert throughput > 100, f"Throughput too low: {throughput} RPS"

    # Error rates
    error_rate = await calculate_error_rate()
    assert error_rate < 0.01, f"Error rate too high: {error_rate:.2%}"
```

## Monitoring and Alerting

### Prometheus Metrics

The system exposes comprehensive metrics at `/metrics`:

```python
# Key metrics to monitor
# ap_intake_api_request_duration_seconds - API response times
# ap_intake_database_query_duration_ms - Database query times
# ap_intake_memory_usage_bytes - Memory usage
# ap_intake_cpu_usage_percent - CPU usage
# ap_intake_invoices_processed_total - Business metrics
# ap_intake_slo_achieved_percentage - SLO compliance
```

### Alerting Rules

```yaml
# Example Prometheus alerting rules
groups:
  - name: performance
    rules:
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, ap_intake_api_request_duration_seconds) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"

      - alert: HighErrorRate
        expr: rate(ap_intake_api_requests_total{status=~"5.."}[5m]) > 0.01
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: DatabaseSlowQueries
        expr: ap_intake_database_query_duration_ms{quantile="0.95"} > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow database queries detected"
```

### Performance Dashboard

Access performance dashboards at:
- **API Performance**: `/api/v1/performance/dashboard`
- **Database Health**: `/api/v1/performance/database/health`
- **Load Test Results**: `/api/v1/performance/load-test/{test_id}`

## Troubleshooting Performance Issues

### Common Performance Bottlenecks

#### 1. Slow Database Queries
**Symptoms:**
- High API response times
- Database connection exhaustion
- High CPU usage on database server

**Diagnosis:**
```python
# Check slow queries
slow_queries = await database_performance_service.get_slow_queries()
print(f"Found {len(slow_queries)} slow queries")

# Analyze query patterns
patterns = await database_performance_service.analyze_query_patterns()
```

**Solutions:**
- Add missing indexes
- Optimize query structure
- Implement query caching
- Use database connection pooling

#### 2. Memory Leaks
**Symptoms:**
- Increasing memory usage over time
- Out-of-memory errors
- Slow garbage collection

**Diagnosis:**
```python
# Profile memory usage
profile_result = await performance_profiling_service.get_profile_summary()
memory_timeline = profile_result.get("memory_timeline", [])

# Check for memory growth
if memory_timeline[-1]["memory_mb"] > memory_timeline[0]["memory_mb"] * 1.5:
    print("Potential memory leak detected")
```

**Solutions:**
- Identify and fix memory leaks
- Optimize data structures
- Implement proper cleanup
- Use memory profiling tools

#### 3. CPU Bottlenecks
**Symptoms:**
- High CPU usage
- Slow response times
- System overload

**Diagnosis:**
```python
# Profile CPU usage
trends = await performance_profiling_service.analyze_performance_trends()
cpu_functions = trends.get("performance_trends", {}).get("cpu_functions", [])
```

**Solutions:**
- Optimize algorithms
- Use caching
- Implement task queues
- Scale horizontally

## Performance Testing Best Practices

### 1. Test Environment Setup
- Use production-like data volumes
- Test with realistic user scenarios
- Monitor system resources during tests
- Test different load patterns

### 2. Test Data Management
- Use realistic test data
- Vary data sizes and complexity
- Test with edge cases
- Clean up test data after runs

### 3. Test Execution
- Start with smoke tests
- Gradually increase load
- Monitor for breaking points
- Document performance baselines

### 4. Results Analysis
- Analyze response time distributions
- Check error rates under load
- Monitor resource utilization
- Identify performance bottlenecks

## Performance Monitoring Checklist

### Daily Monitoring
- [ ] Check API response times (P95 < 500ms)
- [ ] Monitor error rates (< 1%)
- [ ] Verify system availability (> 99.9%)
- [ ] Check database performance metrics
- [ ] Review system resource usage

### Weekly Monitoring
- [ ] Analyze performance trends
- [ ] Review slow query logs
- [ ] Check cache hit ratios
- [ ] Validate SLO compliance
- [ ] Review capacity planning

### Monthly Monitoring
- [ ] Comprehensive performance reports
- [ ] Load testing validation
- [ ] Database maintenance
- [ ] Performance optimization review
- [ ] Capacity assessment

## Continuous Performance Optimization

### 1. Automated Performance Testing
```yaml
# CI/CD pipeline integration
performance_test:
  stage: test
  script:
    - python scripts/performance_validation.py
  artifacts:
    reports:
      performance: performance_results.json
```

### 2. Performance Regression Detection
```python
# Automated regression testing
async def check_performance_regression():
    current_metrics = await get_current_performance_metrics()
    baseline_metrics = await get_baseline_metrics()

    for metric, threshold in PERFORMANCE_THRESHOLDS.items():
        current_value = current_metrics.get(metric, 0)
        baseline_value = baseline_metrics.get(metric, 0)

        if current_value > baseline_value * (1 + threshold):
            alert_performance_regression(metric, current_value, baseline_value)
```

### 3. Performance Budgets
```python
# Define performance budgets
PERFORMANCE_BUDGETS = {
    "api_response_time_p95": 500,  # ms
    "database_query_time_p95": 100,  # ms
    "memory_usage_mb": 500,
    "cpu_usage_percent": 70
}

# Validate against budgets
async def validate_performance_budgets(metrics):
    violations = []
    for metric, budget in PERFORMANCE_BUDGETS.items():
        if metrics.get(metric, 0) > budget:
            violations.append({
                "metric": metric,
                "budget": budget,
                "actual": metrics[metric],
                "violation_percentage": ((metrics[metric] - budget) / budget) * 100
            })

    return violations
```

## Conclusion

This comprehensive performance optimization guide provides the tools and strategies needed to maintain high performance for the AP Intake & Validation system. Regular monitoring, load testing, and optimization are essential for ensuring the system meets its performance targets and provides a reliable user experience.

Key takeaways:
1. **Monitor Continuously**: Use the built-in performance monitoring tools
2. **Test Regularly**: Run load tests to validate performance under stress
3. **Optimize Proactively**: Address performance issues before they impact users
4. **Maintain SLOs**: Ensure service level objectives are consistently met
5. **Scale Appropriately**: Plan for growth and scale resources as needed

For additional support or questions about performance optimization, refer to the performance monitoring API documentation or run the performance validation script to assess current system performance.