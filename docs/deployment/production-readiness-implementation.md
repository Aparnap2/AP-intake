# Production Readiness Implementation Guide
## AP Intake & Validation System

### 🚨 IMMEDIATE SECURITY ACTIONS REQUIRED

#### Phase 1: Critical Security Fixes (Execute Immediately)

**1. Remove Hardcoded QuickBooks Credentials**
```bash
# IMMEDIATE ACTION REQUIRED
# File: app/core/config.py lines 102-103
# These lines must be removed immediately:

# SECURITY CRITICAL: REMOVE THESE LINES
QUICKBOOKS_SANDBOX_CLIENT_ID: Optional[str] = "ABks36hUKi4CnTlqhEKeztfPxZC083pJ4kH7vqPPtTXbNhTwRy"
QUICKBOOKS_SANDBOX_CLIENT_SECRET: Optional[str] = "tNca9AST3GahKyxVWYziia6vyODid81CV3CEQey7"
```

**2. Generate Secure Secret Key**
```bash
# Generate new secure secret key
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"

# Add to .env file
# SECRET_KEY=your-generated-64-character-key-here
```

**3. Update Configuration to Use Enhanced Settings**
```bash
# Backup current config
cp app/core/config.py app/core/config.py.backup

# Update imports in main application files
# Replace: from app.core.config import settings
# With: from app.core.enhanced_config import enhanced_settings as settings
```

### Implementation Steps

#### Step 1: Update Application Dependencies

Add these packages to your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
# Existing dependencies...

# Enhanced reliability and security
tenacity = "^8.2.3"  # Advanced retry logic
prometheus-client = "^0.17.1"  # Metrics collection
redis = {extras = ["asyncio"], version = "^4.6.0"}  # Redis for rate limiting
httpx = "^0.24.1"  # Modern HTTP client
cryptography = "^41.0.4"  # Security utilities
python-jose = {extras = ["cryptography"], version = "^3.3.0"}  # JWT handling
passlib = {extras = ["bcrypt"], version = "^1.7.4"}  # Password hashing
```

Install dependencies:
```bash
uv add tenacity prometheus-client redis[asyncio] httpx cryptography python-jose[cryptography] passlib[bcrypt]
```

#### Step 2: Update Main Application

Create `app/main.py` (or update existing):

```python
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.enhanced_config import enhanced_settings, setup_environment
from app.middleware.security_monitoring import SecurityMonitoringMiddleware
from app.services.external_service_manager import LLMServiceManager
from app.api.api_v1.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    setup_environment()

    # Initialize external service managers
    llm_manager = LLMServiceManager()
    await llm_manager.initialize()

    yield

    # Shutdown
    await llm_manager.cleanup()

# Create FastAPI app
app = FastAPI(
    title=enhanced_settings.project_name,
    description=enhanced_settings.project_description,
    version=enhanced_settings.version,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    SecurityMonitoringMiddleware
)

# CORS middleware
if enhanced_settings.security.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=enhanced_settings.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API routes
app.include_router(api_router, prefix=enhanced_settings.api_v1_str)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": enhanced_settings.environment,
        "version": enhanced_settings.version,
        "timestamp": datetime.utcnow().isoformat()
    }

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    from app.middleware.security_monitoring import metrics_collector
    return Response(
        content=metrics_collector.get_metrics_export(),
        media_type="text/plain"
    )
```

#### Step 3: Update Environment Configuration

1. Copy the production template:
```bash
cp .env.production.template .env.production
```

2. Fill in all required values with actual production secrets
3. Set proper file permissions:
```bash
chmod 600 .env.production
```

#### Step 4: Update Service Implementations

**Update LLM Service** (`app/services/llm_service.py`):

```python
# Replace existing LLM service with enhanced version
from app.services.external_service_manager import LLMServiceManager, with_external_service

class EnhancedLLMService:
    def __init__(self):
        self.manager = LLMServiceManager()

    async def initialize(self):
        await self.manager.initialize()

    @with_external_service("openrouter")
    async def patch_low_confidence_fields(
        self,
        extraction_result: Dict[str, Any],
        confidence_score: float,
        service_manager: LLMServiceManager = None
    ) -> Dict[str, Any]:
        """Enhanced LLM service with reliability patterns."""
        if not service_manager:
            service_manager = self.manager

        # Generate prompt
        prompt = self._generate_patch_prompt(extraction_result)

        # Create messages for chat completion
        messages = [
            {"role": "system", "content": "You are an expert invoice data extraction specialist."},
            {"role": "user", "content": prompt}
        ]

        try:
            # Call LLM with enhanced service manager
            response = await service_manager.chat_completion(
                messages=messages,
                max_tokens=enhanced_settings.openrouter.max_tokens,
                temperature=enhanced_settings.openrouter.temperature
            )

            # Process response
            patched_result = self._apply_patches(extraction_result, response)
            return patched_result

        except Exception as e:
            logger.error(f"Enhanced LLM service failed: {e}")
            return extraction_result  # Return original on failure

    async def cleanup(self):
        await self.manager.cleanup()
```

#### Step 5: Add Monitoring Dashboard

Create `monitoring/docker-compose.yml`:

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  prometheus_data:
  grafana_data:
  redis_data:
```

#### Step 6: Update Docker Configuration

Update `docker-compose.yml` to include enhanced features:

```yaml
version: '3.8'

services:
  api:
    build: .
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.production
    depends_on:
      - postgres
      - redis
      - rabbitmq
    volumes:
      - ./storage:/app/storage
      - ./exports:/app/exports
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=ap_intake_prod
      - POSTGRES_USER=${DATABASE_USER}
      - POSTGRES_PASSWORD=${DATABASE_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  rabbitmq:
    image: rabbitmq:3-management
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
```

### Testing and Validation

#### Step 7: Security Testing

```bash
# Test API key authentication
curl -H "X-API-Key: your-api-key" https://your-domain.com/api/v1/invoices

# Test rate limiting
for i in {1..25}; do
    curl -H "X-API-Key: your-api-key" https://your-domain.com/api/v1/invoices
done

# Test webhook signature validation
python -c "
from app.middleware.security_monitoring import WebhookSignatureValidator
payload = b'test payload'
secret = 'test_secret'
signature = WebhookSignatureValidator.generate_signature(payload, secret)
print('Generated signature:', signature)
"
```

#### Step 8: Performance Testing

```bash
# Install load testing tool
pip install locust

# Create load test script
cat > load_test.py << 'EOF'
from locust import HttpUser, task, between

class APIntakeUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Setup authentication
        response = self.client.post("/api/v1/auth/login", json={
            "username": "test_user",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}

    @task
    def upload_invoice(self):
        """Test invoice upload endpoint."""
        files = {"file": ("test.pdf", open("test.pdf", "rb"), "application/pdf")}
        self.client.post(
            "/api/v1/invoices/upload",
            files=files,
            headers=self.headers
        )

    @task
    def get_invoices(self):
        """Test invoice listing endpoint."""
        self.client.get("/api/v1/invoices", headers=self.headers)
EOF

# Run load test
locust -f load_test.py --host=https://your-domain.com
```

### Monitoring and Alerting Setup

#### Step 9: Configure Monitoring

1. **Prometheus Configuration** (`monitoring/prometheus.yml`):

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ap-intake-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
```

2. **Grafana Dashboards**:
   - Import dashboard for API metrics
   - Set up alerts for error rates > 5%
   - Monitor response times
   - Track external service costs

#### Step 10: Set Up Alerts

Create alerting rules (`monitoring/alerts.yml`):

```yaml
groups:
  - name: ap_intake_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }} seconds"

      - alert: ExternalServiceCostHigh
        expr: external_service_cost_dollars{period="daily"} > 100
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Daily external service costs high"
          description: "Daily cost is ${{ $value }}"
```

### Deployment Checklist

#### Pre-deployment Checklist:

- [ ] **SECURITY**: Remove hardcoded QuickBooks credentials
- [ ] **SECURITY**: Generate and set secure secret key
- [ ] **SECURITY**: Configure proper environment variables
- [ ] **SECURITY**: Set up SSL/TLS certificates
- [ ] **CONFIG**: Update all configuration to use enhanced settings
- [ ] **DEPENDENCIES**: Install all required packages
- [ ] **MONITORING**: Set up Prometheus and Grafana
- [ ] **ALERTING**: Configure alerting rules
- [ ] **BACKUP**: Set up database and file backups
- [ ] **TESTING**: Run security and performance tests

#### Post-deployment Verification:

1. **Health Checks**:
```bash
curl -f https://your-domain.com/health
curl -f https://your-domain.com/metrics
```

2. **Security Validation**:
```bash
# Test HTTPS enforcement
curl -I http://your-domain.com  # Should redirect to HTTPS

# Test security headers
curl -I https://your-domain.com | grep -E "(X-Frame-Options|X-Content-Type|Strict-Transport)"
```

3. **Performance Validation**:
```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s https://your-domain.com/health
```

### Ongoing Maintenance

#### Daily:
- Monitor error rates and response times
- Check external service costs
- Review security logs

#### Weekly:
- Rotate API keys if needed
- Update SSL certificates
- Review and update alerting thresholds

#### Monthly:
- Review and update dependencies
- Audit security configurations
- Performance optimization review
- Cost optimization review

### Emergency Procedures

#### Service Outage Response:
1. Check application health endpoint
2. Review monitoring dashboards
3. Check external service status
4. Review recent deployments
5. Execute rollback if needed

#### Security Incident Response:
1. Identify affected systems
2. Review audit logs
3. Rotate compromised credentials
4. Update security configurations
5. Notify stakeholders

### Contact Information

- **Security Team**: security@your-domain.com
- **Operations Team**: ops@your-domain.com
- **Development Team**: dev@your-domain.com

### Documentation Links

- [API Documentation](https://your-domain.com/docs)
- [Monitoring Dashboard](https://monitoring.your-domain.com)
- [Alerting Configuration](https://alerting.your-domain.com)
- [Runbook](https://runbook.your-domain.com)

---

**🚨 CRITICAL REMINDER**: Execute Phase 1 security fixes immediately before proceeding with any other steps. The hardcoded QuickBooks credentials pose an immediate security risk.