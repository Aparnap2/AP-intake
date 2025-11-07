# Celery Background Workers Setup

This document describes the Celery background worker configuration for the AP Intake system.

## Architecture Overview

The AP Intake system uses Celery with Redis as both the message broker and result backend for background task processing. This setup provides:

- **Asynchronous invoice processing** - File uploads and email processing happen in the background
- **Email monitoring** - Gmail inbox monitoring runs on scheduled intervals
- **Maintenance tasks** - Automated cleanup and health checks
- **Queue-based processing** - Different queues for different types of tasks
- **Monitoring and logging** - Comprehensive task monitoring and error handling

## Configuration

### Message Broker & Backend

- **Broker**: Redis (redis://redis:6379/0)
- **Result Backend**: Redis (redis://redis:6379/0)
- **Transport**: Redis broker with connection pooling

### Queues

The system uses multiple queues for different types of tasks:

| Queue Name | Purpose | Tasks |
|------------|---------|-------|
| `invoice_processing` | Main invoice workflow execution | `process_invoice_task` |
| `validation` | Invoice data validation | `validate_invoice_task` |
| `export` | Export formatted data | `export_invoice_task` |
| `email_processing` | Email and attachment processing | `process_email_task`, `monitor_gmail_inbox` |
| `celery` | Default/maintenance tasks | Health checks, cleanup tasks |

### Worker Configuration

- **Concurrency**: 4 processes per worker (configurable)
- **Prefetch Multiplier**: 1 task per worker
- **Soft Time Limit**: 5 minutes per task
- **Hard Time Limit**: 10 minutes per task
- **Retry Logic**: Exponential backoff with maximum retries

## Services

### 1. Celery Worker Service

**Location**: `app/workers/invoice_tasks.py`, `app/workers/email_tasks.py`

**Main Tasks**:
- `process_invoice_task` - Complete invoice workflow execution
- `validate_invoice_task` - Business rules validation
- `export_invoice_task` - Format and export processed data
- `monitor_gmail_inbox` - Gmail monitoring and attachment processing
- `process_email_attachment` - Individual email attachment processing

**Features**:
- Database session management with automatic cleanup
- Error handling with retry logic
- Status tracking and updates
- Integration with LangGraph workflow

### 2. Celery Beat Scheduler

**Location**: `app/workers/maintenance_tasks.py`

**Scheduled Tasks**:
- `cleanup_old_exports` - Hourly cleanup of old export files (7 days retention)
- `health_check` - System health check every 5 minutes
- `cleanup_failed_tasks` - Daily cleanup of failed task records
- `backup_system_state` - Weekly system state backup
- `monitor_worker_performance` - Performance metrics collection

### 3. Maintenance Tasks

**Features**:
- Automated cleanup of temporary files and old data
- System health monitoring (database, Redis, storage, disk space)
- Performance metrics collection
- Backup and recovery operations

## Docker Setup

### Services in docker-compose.yml

```yaml
# Redis for both broker and backend
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]

# Celery Worker
worker:
  command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
  environment:
    - REDIS_URL=redis://redis:6379/0

# Celery Beat Scheduler
scheduler:
  command: celery -A app.workers.celery_app beat --loglevel=info
  environment:
    - REDIS_URL=redis://redis:6379/0
```

## Starting the Services

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View worker logs
docker-compose logs -f worker

# View scheduler logs
docker-compose logs -f scheduler
```

### Manual Development Setup

```bash
# Start Redis (if not running)
redis-server

# Start Celery worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=4

# Start Celery Beat scheduler (in separate terminal)
celery -A app.workers.celery_app beat --loglevel=info
```

## Monitoring and Management

### API Endpoints

The system provides comprehensive monitoring endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/celery/status` | Worker status and statistics |
| `GET /api/v1/celery/tasks` | Task information and status |
| `GET /api/v1/celery/queues` | Queue information |
| `GET /api/v1/celery/workers` | Detailed worker information |
| `GET /api/v1/celery/metrics` | Performance metrics |
| `POST /api/v1/celery/maintenance/cleanup` | Trigger maintenance tasks |
| `POST /api/v1/celery/maintenance/health-check` | Trigger health check |
| `GET /api/v1/celery/beat/schedule` | View Beat schedule |

### Command Line Monitoring

```bash
# Check active workers
celery -A app.workers.celery_app inspect active

# Check worker statistics
celery -A app.workers.celery_app inspect stats

# Monitor tasks in real-time
celery -A app.workers.celery_app events

# Check queue lengths
celery -A app.workers.celery_app inspect reserved
```

### Flower Monitoring (Optional)

For enhanced monitoring, you can add Flower:

```bash
# Install flower
pip install flower

# Start flower
celery -A app.workers.celery_app flower

# Access flower UI at http://localhost:5555
```

## Testing

### Run Test Suite

```bash
# Run Celery-specific tests
pytest tests/test_celery_setup.py -v

# Run all tests
pytest tests/ -v
```

### Manual Testing

```bash
# Run the comprehensive test script
python scripts/test_celery_setup.py

# Test individual components
python -c "from app.workers.maintenance_tasks import health_check; print(health_check.delay().get())"
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker and backend URL |
| `WORKER_CONCURRENCY` | `4` | Number of worker processes |
| `WORKER_PREFETCH_MULTIPLIER` | `1` | Tasks to prefetch per worker |
| `WORKER_TASK_SOFT_TIME_LIMIT` | `300` | Soft time limit in seconds |
| `WORKER_TASK_TIME_LIMIT` | `600` | Hard time limit in seconds |

### Celery Configuration

Key configuration options in `app/workers/celery_app.py`:

```python
# Task routing
task_routes = {
    "app.workers.invoice_tasks.*": {"queue": "invoice_processing"},
    "app.workers.email_tasks.*": {"queue": "email_processing"},
    "app.workers.maintenance_tasks.*": {"queue": "celery"},
}

# Error handling
task_reject_on_worker_lost = True
task_acks_late = True

# Monitoring
worker_send_task_events = True
task_send_sent_event = True
```

## Task Development

### Creating New Tasks

1. **Create task function**:

```python
from app.workers.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def my_task(self, arg1, arg2):
    try:
        # Your task logic here
        return {"status": "success", "result": ...}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        raise
```

2. **Add to Celery app includes** (if new module):

```python
# In app/workers/celery_app.py
celery_app = Celery(
    "ap_intake",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.invoice_tasks",
        "app.workers.email_tasks",
        "app.workers.maintenance_tasks",
        "app.workers.my_new_tasks",  # Add new module here
    ]
)
```

3. **Add task routing** (optional):

```python
task_routes = {
    "app.workers.my_new_tasks.my_task": {"queue": "my_queue"},
}
```

### Database Tasks

Use the `DatabaseTask` base class for tasks that need database access:

```python
from app.workers.invoice_tasks import DatabaseTask

@celery_app.task(bind=True, base=DatabaseTask, max_retries=3)
def my_db_task(self, invoice_id):
    db = self.get_db()
    try:
        # Use database session
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        # ... your logic here
        db.commit()
    finally:
        # Cleanup is handled automatically by DatabaseTask
        pass
```

## Troubleshooting

### Common Issues

1. **Workers not starting**:
   - Check Redis connection: `redis-cli ping`
   - Verify REDIS_URL environment variable
   - Check logs: `docker-compose logs worker`

2. **Tasks not executing**:
   - Verify workers are running: `celery inspect active`
   - Check queue configuration
   - Monitor task events: `celery events`

3. **High memory usage**:
   - Reduce worker concurrency
   - Check for task memory leaks
   - Monitor with `docker stats`

4. **Connection errors**:
   - Verify Redis is accessible from workers
   - Check network configuration in Docker
   - Verify firewall settings

### Debug Mode

Enable debug logging:

```bash
# Start worker with debug logging
celery -A app.workers.celery_app worker --loglevel=debug

# Enable SQL logging
export SQL_ECHO=true
```

### Health Checks

The system includes comprehensive health checks:

```bash
# Check system health
curl http://localhost:8000/api/v1/celery/maintenance/health-check

# Check worker status
curl http://localhost:8000/api/v1/celery/status
```

## Performance Optimization

### Worker Tuning

1. **Concurrency**: Set to number of CPU cores
2. **Prefetch**: Keep low for I/O bound tasks
3. **Memory**: Monitor worker memory usage
4. **Time limits**: Adjust based on task complexity

### Redis Optimization

1. **Persistence**: Configure appropriate persistence policy
2. **Memory**: Set max memory limits
3. **Networking**: Use connection pooling
4. **Monitoring**: Monitor Redis memory usage

### Queue Management

1. **Priority**: Use separate queues for different priority levels
2. **Monitoring**: Monitor queue lengths regularly
3. **Scaling**: Add workers for high-priority queues
4. **Routing**: Route tasks to appropriate queues

## Security Considerations

1. **Redis Security**: Use Redis password in production
2. **Network Security**: Limit Redis network exposure
3. **Task Security**: Validate task inputs
4. **Access Control**: Restrict API endpoint access

## Backup and Recovery

1. **Redis Backup**: Regular Redis RDB snapshots
2. **Task Recovery**: Monitor failed tasks
3. **Data Recovery**: Backup database and storage
4. **Monitoring**: Alert on task failures

This Celery setup provides a robust foundation for background task processing in the AP Intake system, with comprehensive monitoring, error handling, and maintenance capabilities.