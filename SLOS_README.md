# KPIs/SLOs Framework Implementation

This document describes the comprehensive Service Level Objectives (SLOs) and Key Performance Indicators (KPIs) framework implemented for the AP Intake & Validation system.

## Overview

The SLO framework provides enterprise-grade monitoring and alerting capabilities specifically designed for SMB-friendly invoice processing operations. It includes real-time performance tracking, error budget management, and actionable alerting.

## Core SLIs (Service Level Indicators)

### 1. Time-to-Ready Processing
- **Definition**: Time from invoice upload to ready for approval
- **Target**: 95% of invoices processed within 5 minutes
- **Error Budget**: 5%
- **Measurement**: Daily and hourly

### 2. Validation Pass Rate
- **Definition**: Percentage of invoices passing structural and math validation
- **Target**: 90% validation success rate
- **Error Budget**: 10%
- **Measurement**: Daily

### 3. Processing Success Rate
- **Definition**: Overall success rate of invoice processing workflow
- **Target**: 95% successful processing
- **Error Budget**: 5%
- **Measurement**: Hourly

### 4. Extraction Accuracy
- **Definition**: Average confidence score for document extraction
- **Target**: 92% average confidence
- **Error Budget**: 8%
- **Measurement**: Daily

### 5. Approval Latency
- **Definition**: Time from ready for approval to approved
- **Target**: 90% approved within 2 hours
- **Error Budget**: 10%
- **Measurement**: Daily

### 6. Exception Resolution Time
- **Definition**: Average time to resolve processing exceptions
- **Target**: 85% resolved within 4 hours
- **Error Budget**: 15%
- **Measurement**: Daily

### 7. Duplicate Detection Recall
- **Definition**: Accuracy of duplicate invoice detection
- **Target**: 98% recall accuracy
- **Error Budget**: 2%
- **Measurement**: Weekly

## Architecture

### Database Models

The system uses several key database models:

- **SLODefinition**: Defines SLO targets and error budget policies
- **SLIMeasurement**: Stores periodic SLI measurements
- **SLOAlert**: Tracks SLO violations and alerts
- **InvoiceMetric**: Detailed invoice-level metrics
- **SystemMetric**: General system performance metrics

### Services

#### MetricsService (`app/services/metrics_service.py`)
Core service for:
- SLI calculation and measurement
- Error budget tracking
- Alert generation and management
- KPI summary generation

#### PrometheusService (`app/services/prometheus_service.py`)
Handles:
- Prometheus metrics exposition
- System performance monitoring
- Real-time metric collection

### API Endpoints

#### SLO Management
- `GET /api/v1/metrics/slos/dashboard` - SLO dashboard data
- `GET /api/v1/metrics/slos/definitions` - SLO definitions
- `GET /api/v1/metrics/slos/{slo_id}/measurements` - Historical measurements

#### Alerts
- `GET /api/v1/metrics/alerts` - List SLO alerts
- `POST /api/v1/metrics/alerts/{alert_id}/acknowledge` - Acknowledge alerts
- `POST /api/v1/metrics/alerts/{alert_id}/resolve` - Resolve alerts

#### KPIs
- `GET /api/v1/metrics/kpis/summary` - KPI summary
- `GET /api/v1/metrics/metrics/invoice-trends` - Invoice processing trends

#### Management
- `POST /api/v1/metrics/slos/initialize` - Initialize default SLOs
- `POST /api/v1/metrics/measurements/calculate` - Trigger measurements calculation

### Background Tasks

#### Metrics Tasks (`app/workers/metrics_tasks.py`)
Scheduled tasks for:
- **SLI Calculation**: Hourly, daily, and weekly measurements
- **Report Generation**: Daily and weekly performance reports
- **Data Cleanup**: Monthly cleanup of old metrics data
- **SLO Initialization**: Setup default SLO definitions

### Frontend Components

#### SLO Dashboard (`web/components/dashboard/SLODashboard.tsx`)
Interactive dashboard featuring:
- Real-time SLO status overview
- Error budget visualization
- Alert management
- Performance trends
- Historical analysis

#### React Hook (`web/hooks/useSLOMetrics.ts`)
Custom hook for:
- Data fetching and caching
- Real-time updates
- Error handling
- Loading states

## Error Budget Management

### 5% Error Budget Policy
Each SLO includes a configurable error budget (typically 5-15%). When the error budget is consumed:

1. **80% consumed**: Warning alerts sent to stakeholders
2. **95% consumed**: Critical alerts with immediate escalation
3. **100% consumed**: Incident response triggered

### Burn Rate Monitoring
The system tracks burn rate (rate of error budget consumption):
- **Burn rate > 2.0**: High alert - error budget being consumed too quickly
- **Burn rate > 1.5**: Warning alert - elevated consumption rate
- **Burn rate < 1.0**: Normal operation

## Alerting Strategy

### Alert Types
1. **Burn Rate Warning**: Error budget consumption rate is elevated
2. **Error Budget Exhausted**: Error budget fully consumed
3. **Critical Performance**: SLO achievement below 50%
4. **Consecutive Failures**: Multiple consecutive measurement failures

### Notification Channels
- **Email**: Standard alert notifications
- **Slack**: Real-time alerts and updates
- **SMS**: Critical alerts (configurable)

### Escalation Policy
1. **Warning**: Email notification to operations team
2. **Critical**: Email + Slack + on-call notification
3. **Incident**: Full incident response protocol

## Configuration

### SLO Configuration (`monitoring/slo-rules.yml`)
Comprehensive configuration file defining:
- SLO targets and thresholds
- Error budget policies
- Alert rules and escalation
- Notification channels
- Reporting schedules

### Environment Variables
```bash
# Enable metrics collection
METRICS_ENABLED=true

# SLO calculation intervals
SLO_HOURLY_ENABLED=true
SLO_DAILY_ENABLED=true
SLO_WEEKLY_ENABLED=true

# Alert configuration
ALERT_EMAIL_ENABLED=true
ALERT_SLACK_ENABLED=false
ALERT_SMS_ENABLED=false
```

## Integration with Existing Workflow

### Invoice Processing Integration
The metrics collection is integrated into the invoice processing workflow:

1. **Process Completion**: Automatic metric recording for each invoice
2. **Performance Tracking**: Detailed timing and quality metrics
3. **Exception Handling**: Exception impact on SLOs
4. **Success Rate Tracking**: Overall processing effectiveness

### Real-time Monitoring
- Prometheus metrics endpoint at `/health/metrics`
- Real-time dashboard updates
- Automatic performance regression detection

## Usage Examples

### Initialize SLOs
```bash
curl -X POST "http://localhost:8000/api/v1/metrics/slos/initialize" \
  -H "Authorization: Bearer <token>"
```

### Get SLO Dashboard
```bash
curl "http://localhost:8000/api/v1/metrics/slos/dashboard?time_range_days=30" \
  -H "Authorization: Bearer <token>"
```

### Get KPI Summary
```bash
curl "http://localhost:8000/api/v1/metrics/kpis/summary?days=7" \
  -H "Authorization: Bearer <token>"
```

### Acknowledge Alert
```bash
curl -X POST "http://localhost:8000/api/v1/metrics/alerts/{alert_id}/acknowledge" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Acknowledged via API"}'
```

## Prometheus Metrics

### Business Metrics
- `ap_intake_invoices_processed_total`: Total processed invoices
- `ap_intake_processing_duration_seconds`: Processing time distributions
- `ap_intake_extraction_confidence`: Extraction confidence scores
- `ap_intake_validation_results_total`: Validation results
- `ap_intake_exceptions_total`: Processing exceptions

### SLO Metrics
- `ap_intake_slo_achieved_percentage`: SLO achievement rates
- `ap_intake_error_budget_consumed`: Error budget consumption
- `ap_intake_slo_alerts_total`: SLO alert counts

### System Metrics
- `ap_intake_active_workflows`: Active workflow count
- `ap_intake_memory_usage_bytes`: Memory usage by component
- `ap_intake_cpu_usage_percent`: CPU usage by component

## Data Retention

### Metrics Retention
- **Raw invoice metrics**: 30 days
- **SLI measurements**: 90 days
- **SLO alerts**: 1 year
- **Aggregated metrics**: 2 years

### Automatic Cleanup
Monthly background task automatically removes old data based on retention policies.

## Reporting

### Automated Reports
- **Daily**: Performance summary and alert status
- **Weekly**: Trend analysis and recommendations
- **Monthly**: Comprehensive SLO attainment report

### Custom Reports
API endpoints support custom date ranges and filtering for ad-hoc reporting.

## Monitoring and Observability

### Health Checks
- `/health/metrics`: Metrics system health status
- `/health/detailed`: Overall system health including metrics

### Performance Monitoring
- Real-time metrics via Prometheus
- Historical trend analysis
- Performance regression detection

## Best Practices

### SLO Configuration
1. **Start Conservative**: Begin with conservative targets and adjust based on data
2. **Monitor Burn Rate**: Pay attention to error budget consumption patterns
3. **Regular Reviews**: Quarterly SLO target reviews and adjustments
4. **Stakeholder Communication**: Regular sharing of SLO performance

### Alert Management
1. **Avoid Alert Fatigue**: Set appropriate thresholds to minimize noise
2. **Clear Escalation**: Define clear escalation paths for different alert types
3. **Quick Acknowledgment**: Promptly acknowledge and investigate alerts
4. **Documentation**: Maintain clear documentation of alert procedures

### Performance Optimization
1. **Regular Monitoring**: Continuously monitor SLO performance
2. **Trend Analysis**: Use historical data to identify performance trends
3. **Proactive Optimization**: Address performance issues before they impact SLOs
4. **Capacity Planning**: Use metrics data for capacity planning

## Troubleshooting

### Common Issues
1. **Missing Measurements**: Check background task scheduling
2. **Alert Delays**: Verify notification channel configuration
3. **High Error Budget**: Investigate performance regressions
4. **Dashboard Loading Issues**: Check database connectivity and query performance

### Debug Commands
```bash
# Check Celery workers
celery -A app.workers.metrics_tasks inspect active

# Test SLO calculation
python -m app.workers.metrics_tasks calculate_sli_measurements

# Check metrics collection
curl "http://localhost:8000/health/metrics"
```

## Future Enhancements

### Planned Features
1. **ML-based Anomaly Detection**: Automated detection of unusual patterns
2. **Predictive Analytics**: Forecast SLO performance based on trends
3. **Advanced Reporting**: Interactive drill-down reports
4. **Multi-tenant Support**: Organization-specific SLO configurations
5. **Integration with External Monitoring**: Grafana, DataDog integration

### Scalability Improvements
1. **Distributed Metrics Collection**: Horizontal scaling of metrics processing
2. **Time-series Database**: Integration with InfluxDB or TimescaleDB
3. **Real-time Streaming**: Kafka-based real-time metrics processing
4. **Edge Monitoring**: Metrics collection at edge locations

## Support

For questions or issues with the SLO framework:
1. Check this documentation
2. Review the API documentation at `/docs`
3. Monitor system health at `/health/detailed`
4. Contact the platform engineering team

---

This implementation provides a production-ready, SMB-friendly SLO framework that delivers actionable insights while maintaining operational simplicity. The system is designed to scale with the organization and provide the visibility needed for reliable invoice processing operations.