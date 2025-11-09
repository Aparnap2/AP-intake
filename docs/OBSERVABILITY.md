# Observability and Runbook System

This document describes the comprehensive observability and runbook system implemented for the AP Intake platform, providing end-to-end monitoring, alerting, and automated incident response capabilities.

## Overview

The observability system provides:

- **Distributed Tracing**: End-to-end request tracing across all system components
- **Metrics Collection**: Comprehensive performance and business metrics
- **Alert Management**: Multi-tier alerting with intelligent escalation
- **Runbook Execution**: Automated incident response and recovery procedures
- **SLO Monitoring**: Service Level Objective tracking and reporting
- **System Health Monitoring**: Real-time component health checks

## Architecture

### Core Components

1. **Tracing Service** (`app/services/tracing_service.py`)
   - OpenTelemetry-based distributed tracing
   - Cost tracking per operation
   - Span correlation and context propagation

2. **Alert Service** (`app/services/alert_service.py`)
   - Rule-based alert generation
   - Multi-channel notifications
   - Escalation policy management

3. **Runbook Service** (`app/services/runbook_service.py`)
   - Automated recovery procedures
   - Step-by-step execution tracking
   - Approval workflows for critical actions

4. **Metrics Service** (`app/services/metrics_service.py`)
   - SLO calculation and tracking
   - Performance metrics aggregation
   - KPI dashboard data

5. **Prometheus Service** (`app/services/prometheus_service.py`)
   - Metrics exposition
   - Custom metric registration
   - Time-series data collection

### Data Models

- **TraceSpan**: Distributed trace data with cost tracking
- **AlertRule/Alert**: Alert definitions and instances
- **RunbookExecution/RunbookStepExecution**: Runbook execution tracking
- **SystemHealthCheck**: Component health monitoring
- **PerformanceMetric**: System and business metrics
- **AnomalyDetection**: Anomaly identification and tracking

## Configuration

### Environment Variables

```bash
# OpenTelemetry Configuration
OTEL_ENABLED=true
OTEL_SERVICE_NAME=ap-intake-api
JAEGER_ENDPOINT=http://jaeger:14268/api/traces
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# SLO Monitoring
SLO_ENABLED=true
METRICS_RETENTION_DAYS=90

# Alert Configuration
ALERT_EMAIL_ENABLED=true
ALERT_SLACK_ENABLED=true
ALERT_PAGERDUTY_ENABLED=false

# Runbook Configuration
RUNBOOK_APPROVAL_REQUIRED=true
EMERGENCY_DRILL_ENABLED=true
```

### Database Migration

Create observability tables:

```bash
# Copy migration file
cp migrations/versions/create_observability_tables.py migrations/versions/

# Run migration
docker-compose exec api alembic upgrade head
```

## Usage

### Distributed Tracing

The tracing service automatically instruments:

- API requests and responses
- Database queries
- External service calls
- Background job execution
- Custom business operations

```python
from app.services.tracing_service import tracing_service

# Trace a custom operation
async with tracing_service.trace_span(
    "invoice.processing",
    tracing_service.SpanMetadata(
        component="invoice_processor",
        operation="process_invoice",
        invoice_id=invoice.id,
        workflow_id=workflow.id
    )
) as span_context:
    # Track costs
    tracing_service.track_cost(
        span_context,
        llm_tokens=100,
        llm_cost=0.01
    )

    # Add events
    tracing_service.add_event(
        span_context,
        "validation_completed",
        {"validation_passed": True}
    )
```

### Alert Management

Create and manage alerts programmatically:

```python
from app.services.alert_service import alert_service, AlertSeverity

# Create custom alert
alert = await alert_service.create_custom_alert(
    name="High Processing Queue",
    description="Processing queue size exceeded threshold",
    severity=AlertSeverity.WARNING,
    context={"queue_size": 1500, "threshold": 1000}
)

# Acknowledge alert
await alert_service.acknowledge_alert(
    alert.id,
    acknowledged_by="ops@company.com",
    note="Investigating the issue"
)
```

### Runbook Execution

Execute automated recovery procedures:

```python
from app.services.runbook_service import runbook_service

# Execute emergency rollback
execution = await runbook_service.trigger_runbook(
    runbook_id="emergency_rollback",
    trigger_context={
        "reason": "Data corruption detected",
        "rollback_window_hours": 24
    },
    user_id="ops_user"
)

# Execute emergency drill
drill_execution = await runbook_service.execute_emergency_drill(
    drill_type="export_rollback",
    execution_context={"initiated_via": "dashboard"}
)
```

## Available Runbooks

### Emergency Runbooks

1. **Emergency Staged Export Rollback**
   - Rollback exports within time window
   - Validate rollback eligibility
   - Execute automated rollback
   - Notify stakeholders

2. **Dead Letter Queue Recovery**
   - Analyze DLQ contents
   - Identify recovery candidates
   - Execute batch retry
   - Archive permanent failures

3. **Invoice Processing Recovery**
   - Identify failed invoices
   - Determine recovery strategy
   - Execute from last good state
   - Validate recovery results

4. **System Recovery**
   - Assess system state
   - Validate backup integrity
   - Restore from backups
   - Restart services

### Performance Runbooks

1. **Performance Degradation Response**
   - Identify bottlenecks
   - Clear temporary caches
   - Restart problematic services
   - Scale resources if needed

2. **Database Connection Pool Issues**
   - Analyze connection pool usage
   - Identify connection leaks
   - Restart database connections
   - Optimize pool configuration

### Data Integrity Runbooks

1. **Data Integrity Check and Repair**
   - Scan for corruption
   - Isolate affected records
   - Execute data repair
   - Rebuild indices

### Security Runbooks

1. **Security Incident Response**
   - Assess security incident
   - Contain threat
   - Preserve evidence
   - Rotate credentials

## Dashboard and Monitoring

### Metrics Dashboard

Access the observability dashboard at:
- **Development**: http://localhost:3000/observability
- **Production**: https://ap-intake.company.com/observability

The dashboard provides:

- Real-time KPI metrics
- System health status
- Active alerts
- Performance trends
- Anomaly detection results

### Grafana Dashboards

Import the provided Grafana dashboard configurations:

```bash
# Import dashboard
curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H "Authorization: Bearer ${GRAFANA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @monitoring/grafana-dashboards/ap-intake-overview.json
```

Available dashboards:
- **AP Intake System Overview**: Primary system metrics
- **SLO Monitoring**: Service level objectives
- **Performance Analysis**: Detailed performance metrics
- **Alert Summary**: Active and historical alerts

### API Endpoints

#### Metrics and Monitoring

```bash
# Get metrics summary
GET /api/v1/observability/metrics/summary?time_range_hours=24

# Get SLO dashboard data
GET /api/v1/observability/slo/dashboard?time_range_days=7

# Get system health
GET /api/v1/observability/system-health?component=database&hours=24

# Get trace data
GET /api/v1/observability/traces?component=api&limit=100
```

#### Alert Management

```bash
# Get active alerts
GET /api/v1/observability/alerts?severity=warning&status=active

# Acknowledge alert
POST /api/v1/observability/alerts/{alert_id}/acknowledge
{
  "note": "Investigating the issue"
}

# Resolve alert
POST /api/v1/observability/alerts/{alert_id}/resolve
{
  "resolution_note": "Fixed the underlying issue"
}
```

#### Runbook Management

```bash
# List available runbooks
GET /api/v1/observability/runbooks

# Execute runbook
POST /api/v1/observability/runbooks/{runbook_id}/execute
{
  "trigger_context": {
    "reason": "Manual execution",
    "scope": "production"
  }
}

# Get execution status
GET /api/v1/observability/runbooks/executions/{execution_id}

# Cancel execution
POST /api/v1/observability/runbooks/executions/{execution_id}/cancel
{
  "reason": "No longer needed"
}
```

#### Emergency Drills

```bash
# Execute emergency drill
POST /api/v1/observability/emergency-drill
{
  "drill_type": "export_rollback",
  "execution_context": {
    "initiated_via": "dashboard"
  }
}
```

## Emergency Procedures

### 2-Minute Emergency Drills

Practice emergency response with automated drills:

1. **Export Rollback Drill**: Test staged export rollback
2. **DLQ Recovery Drill**: Test dead letter queue recovery
3. **Invoice Recovery Drill**: Test failed invoice recovery
4. **Performance Drill**: Test performance issue response

Execute via dashboard or API:
```bash
# Via API
curl -X POST http://localhost:8000/api/v1/observability/emergency-drill \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "drill_type": "export_rollback",
    "execution_context": {"initiated_via": "api"}
  }'
```

### Incident Response Playbook

1. **Detection**
   - Monitor alerts and SLO breaches
   - Check observability dashboard
   - Verify system health

2. **Assessment**
   - Determine impact scope
   - Identify affected components
   - Assess business impact

3. **Response**
   - Execute appropriate runbook
   - Communicate with stakeholders
   - Document actions taken

4. **Recovery**
   - Verify system recovery
   - Monitor for recurrence
   - Update documentation

5. **Post-Incident**
   - Conduct root cause analysis
   - Update runbooks if needed
   - Share lessons learned

## Integration with External Systems

### Monitoring Tools

- **Jaeger**: Distributed tracing visualization
- **Prometheus**: Metrics collection and storage
- **Grafana**: Dashboard and visualization
- **AlertManager**: Alert routing and management

### Notification Channels

- **Email**: SMTP-based notifications
- **Slack**: Real-time team notifications
- **PagerDuty**: Critical alert escalation
- **Microsoft Teams**: Enterprise notifications

### Backup and Recovery

- **Database Backups**: Automated daily backups
- **File Storage**: Versioned file backups
- **Configuration**: Git-based configuration management
- **State Snapshots**: Application state persistence

## Best Practices

### Alerting

1. **Meaningful Alerts**: Each alert should require action
2. **Clear Severity**: Use appropriate severity levels
3. **Actionable Messages**: Include suggested resolutions
4. **Avoid Alert Fatigue**: Use suppression and aggregation

### Runbooks

1. **Comprehensive Coverage**: Cover all failure scenarios
2. **Clear Steps**: Each step should be unambiguous
3. **Rollback Procedures**: Include rollback for each action
4. **Regular Testing**: Test runbooks regularly

### Performance Monitoring

1. **Relevant Metrics**: Monitor business-critical metrics
2. **SLO Alignment**: Align with business objectives
3. **Trend Analysis**: Monitor trends, not just current values
4. **Capacity Planning**: Use metrics for capacity planning

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   - Check trace span retention
   - Monitor metric collection rate
   - Review alert processing

2. **Missing Traces**
   - Verify OpenTelemetry configuration
   - Check sampling rates
   - Review service connectivity

3. **Alert Fatigue**
   - Review alert thresholds
   - Implement suppression rules
   - Optimize notification channels

4. **Runbook Failures**
   - Check step dependencies
   - Verify system permissions
   - Review timeout configurations

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set debug log level
export LOG_LEVEL=DEBUG

# Enable verbose tracing
export OTEL_DEBUG=true

# Run with increased logging
docker-compose up --build api
```

## Performance Considerations

### Trace Sampling

Configure appropriate sampling rates:

```python
# In tracing service
OTEL_TRACE_SAMPLING_RATE=0.1  # 10% sampling
```

### Metric Retention

Configure appropriate retention periods:

```python
# In metrics service
METRICS_RETENTION_DAYS=90
AGGREGATED_METRICS_RETENTION_DAYS=365
```

### Alert Rate Limiting

Configure alert rate limits:

```python
# In alert service
ALERT_RATE_LIMIT_PER_MINUTE=10
ALERT_RATE_LIMIT_BURST=20
```

## Security Considerations

### Access Control

- Restrict runbook execution to authorized users
- Implement audit logging for all actions
- Use principle of least privilege

### Data Privacy

- Sanitize sensitive data from traces
- Encrypt stored metrics and logs
- Implement data retention policies

### Network Security

- Secure monitoring endpoints
- Use mutual TLS for service communication
- Implement network segmentation

## Future Enhancements

### Planned Features

1. **Machine Learning Anomaly Detection**
   - Advanced pattern recognition
   - Predictive alerting
   - Automated root cause analysis

2. **Enhanced Visualization**
   - Real-time streaming dashboards
   - Interactive trace analysis
   - 3D system topology visualization

3. **Automated Remediation**
   - Self-healing capabilities
   - Intelligent resource scaling
   - Automated configuration updates

4. **Integration Expansion**
   - Additional monitoring tools
   - External incident management systems
   - Compliance reporting

## Contributing

When contributing to the observability system:

1. **Follow Patterns**: Use established tracing and metrics patterns
2. **Document Changes**: Update documentation for new features
3. **Test Thoroughly**: Include observability in test coverage
4. **Performance Impact**: Consider performance implications

## Support

For observability system issues:

1. **Check Documentation**: Review this documentation first
2. **Search Issues**: Check GitHub issues for known problems
3. **Debug Logs**: Enable debug logging and review logs
4. **Contact Team**: Reach out to the observability team

---

*Last updated: January 2024*