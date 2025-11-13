# N8N Integration Guide for AP Intake System

## Overview

Your AP Intake system has comprehensive n8n integration for workflow automation. The system includes:

1. **N8nService** - Service class for n8n API integration
2. **Schema Definitions** - Pydantic models for data validation
3. **Workflow Templates** - Ready-to-use JSON workflows

## Understanding N8N JSON Structure

From n8n documentation, workflows consist of:

```json
{
  "nodes": [
    {
      "id": "unique_node_id",
      "type": "node_type",
      "name": "Human Readable Name",
      "position": [x, y],
      "parameters": {
        // Node-specific configuration
      }
    }
  ],
  "connections": {
    "source_node": {
      "main": [
        [
          {
            "node": "target_node",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

## Data Flow Structure

n8n passes data between nodes as **array of objects**:
```javascript
return [{
  json: {
    // Your data here
    field1: "value1",
    field2: "value2"
  }
}];
```

## Your Current Workflows

### 1. Weekly Digest Workflow (`weekly-digest.json`)
- **Purpose**: Automated Monday 9am CFO reports
- **Trigger**: Cron schedule (`0 9 * * 1`)
- **Features**:
  - Date calculation for weekly periods
  - Financial metrics fetching
  - PDF/Excel report generation
  - Email distribution
  - Dashboard updates

### 2. Exception Handling Workflow (`exception-handling.json`)
- **Purpose**: Intelligent exception processing
- **Trigger**: Webhook (`/exception-handling`)
- **Features**:
  - Exception parsing and validation
  - Auto-resolution attempts
  - Human escalation logic
  - Notification routing
  - Activity logging

### 3. AP Intake Workflow (`ap-intake.json`)
- **Purpose**: AP invoice processing
- **Trigger**: Webhook (`/ap-invoice`)
- **Features**:
  - Invoice validation
  - Duplicate detection
  - Approval routing (auto vs manual)
  - ERP export preparation
  - Notifications

## How to Upload Workflows to N8N

### Method 1: Import from JSON
1. Open n8n web interface
2. Click **"Import from File"** in the main menu
3. Select the JSON file
4. Review and confirm import

### Method 2: Copy-Paste
1. Open n8n workflow editor
2. Click the three dots menu → **"Import"**
3. Select **"Copy from JSON"**
4. Paste the JSON content
5. Click **"Import"**

### Method 3: API Upload
```bash
curl -X POST http://your-n8n-instance:5678/rest/workflows \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflow.json
```

## Configuration Requirements

### Environment Variables
```bash
# N8N Connection
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_n8n_api_key
N8N_USERNAME=your_username
N8N_PASSWORD=your_password

# Security
N8N_WEBHOOK_SECRET=your_webhook_secret
N8N_ENCRYPTION_KEY=your_encryption_key

# Workflow IDs
N8N_AP_WORKFLOW_ID=ap_invoice_processing
N8N_AR_WORKFLOW_ID=ar_invoice_processing
N8N_EXCEPTION_HANDLING_WORKFLOW_ID=exception_handling
N8N_WEEKLY_REPORT_WORKFLOW_ID=weekly_report_generation
N8N_CFO_DIGEST_WORKFLOW_ID=cfo_monday_digest
```

## API Integration Points

Your system exposes these endpoints for n8n integration:

### Invoice Processing
```
POST /api/v1/analytics/weekly-summary
GET /api/v1/analytics/financial-summary
```

### Exception Handling
```
POST /api/v1/exceptions/{exception_id}/status
POST /api/v1/observability/log
```

### Reports
```
POST /api/v1/reports/generate-pdf
POST /api/v1/reports/generate-excel
POST /api/v1/storage/save
POST /api/v1/dashboard/weekly-update
```

### Approvals
```
POST /api/v1/approvals/request
```

## Best Practices

### 1. Error Handling
- Always include try-catch blocks in function nodes
- Provide meaningful error messages
- Use appropriate HTTP status codes

### 2. Data Validation
- Validate required fields before processing
- Check data types and formats
- Handle edge cases gracefully

### 3. Security
- Use webhook signature validation
- Encrypt sensitive data
- Implement rate limiting
- Never hardcode credentials

### 4. Performance
- Use parallel processing where possible
- Implement retry logic with exponential backoff
- Monitor execution times
- Optimize database queries

### 5. Monitoring
- Log all important events
- Track execution metrics
- Set up alerts for failures
- Monitor resource usage

## Customization Guidelines

### Adding New Nodes
1. Define unique `id` and `name`
2. Set appropriate `type`
3. Configure `position` for visual layout
4. Add `parameters` as needed
5. Update `connections` for data flow

### Modifying Existing Workflows
1. Backup original JSON
2. Test changes in development
3. Update documentation
4. Monitor production performance

### Testing Workflows
1. Use n8n's "Execute Workflow" feature
2. Test with realistic data
3. Verify error handling
4. Check performance metrics

## Troubleshooting

### Common Issues
1. **Import Failures**: Check JSON syntax and structure
2. **Connection Errors**: Verify API endpoints and authentication
3. **Data Flow Issues**: Review connections between nodes
4. **Performance Problems**: Monitor execution times

### Debugging Steps
1. Check n8n execution logs
2. Review node outputs
3. Verify API responses
4. Test individual components

## Enhanced Features Available

Your N8nService supports advanced features:

- **Circuit Breakers**: Prevent cascade failures
- **Retry Logic**: Automatic retry with exponential backoff
- **Encryption**: Secure sensitive data handling
- **Metrics**: Comprehensive performance tracking
- **Webhook Validation**: Security signature checking
- **Template Management**: Dynamic workflow updates

## Next Steps

1. **Upload Workflows**: Import the JSON files into your n8n instance
2. **Configure Environment**: Set up required environment variables
3. **Test Integration**: Verify webhook endpoints and API connectivity
4. **Monitor Performance**: Set up alerts and dashboards
5. **Customize**: Adapt workflows to your specific business needs

## Support

For issues with n8n integration:
1. Check n8n documentation: https://docs.n8n.io/
2. Review system logs
3. Monitor API endpoints
4. Test workflows in development environment