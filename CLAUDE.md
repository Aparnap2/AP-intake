# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AP Intake & Validation is a comprehensive invoice processing system that transforms PDF invoices into structured, validated data ready for ERP import. The system uses Docling for intelligent document extraction, LangGraph for workflow orchestration, and includes a React frontend with FastAPI backend.

## Architecture

- **FastAPI** - REST API service with async support
- **LangGraph** - State machine for invoice processing workflow (app/workflows/invoice_processor.py)
- **Docling** - Core document parsing and extraction service
- **PostgreSQL** - Primary data store with SQLAlchemy ORM
- **Redis/RabbitMQ** - Caching and message queuing for background tasks
- **Celery** - Background task processing (app/workers/)
- **S3/MinIO** - Document storage with configurable backends
- **React** - Frontend UI (web/ directory)

## Common Development Commands

### Docker Development (Recommended)

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View API logs
docker-compose logs -f api

# View worker logs
docker-compose logs -f worker

# Stop services
docker-compose down
```

### Database Operations

```bash
# Run database migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Seed sample data
docker-compose exec api python scripts/seed_data.py

# Access PostgreSQL directly
docker-compose exec postgres psql -U postgres -d ap_intake
```

### Testing

```bash
# Run all tests
docker-compose exec api pytest

# Run unit tests only
docker-compose exec api pytest tests/unit/

# Run integration tests
docker-compose exec api pytest tests/integration/

# Run with coverage report
docker-compose exec api pytest --cov=app tests/

# Run specific test file
docker-compose exec api pytest tests/test_invoice_processor.py -v
```

### Code Quality

```bash
# Format code
docker-compose exec api black app/ tests/
docker-compose exec api isort app/ tests/

# Lint code
docker-compose exec api flake8 app/ tests/

# Type checking
docker-compose exec api mypy app/
```

### Frontend Development

```bash
# Start React development server
cd web/
npm install
npm start

# Build for production
npm run build

# Run tests
npm test
```

## Core Workflow Architecture

The invoice processing workflow is implemented as a LangGraph state machine in `app/workflows/invoice_processor.py`:

1. **receive** - File ingestion and validation
2. **parse** - Docling document extraction with confidence scoring
3. **patch** - LLM-based patching for low-confidence fields
4. **validate** - Business rules validation
5. **triage** - Auto-approval vs human review determination
6. **stage_export** - Prepare structured export payload

### Key Configuration
- `DOCLING_CONFIDENCE_THRESHOLD` - Minimum confidence for auto-approval (default: 0.8)
- `STORAGE_TYPE` - Document storage backend (local/s3/r2/supabase)
- `LLM_MODEL` - Model used for low-confidence field patching

## Service URLs

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Metrics**: http://localhost:8000/metrics
- **React UI**: http://localhost:3000
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin123)
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)

## Key Services

### Invoice Processing Service
- Location: `app/services/docling_service.py`
- Handles document parsing with Docling
- Returns structured data with confidence scores

### Validation Service
- Location: `app/services/validation_service.py`
- Applies business rules to extracted data
- Determines if human review is needed

### Storage Service
- Location: `app/services/storage_service.py`
- Configurable backend (local/S3/MinIO/R2/Supabase)
- Handles file upload/retrieval operations

### LLM Service
- Location: `app/services/llm_service.py`
- Patches low-confidence extraction results
- Configurable model selection

### Export Service
- Location: `app/services/export_service.py`
- Generates CSV/JSON export payloads
- Handles format standardization

## Background Tasks

Celery workers handle async invoice processing:
- Worker: `app/workers/invoice_tasks.py`
- Configuration: `app/workers/celery_app.py`

Monitor workers: http://localhost:15672 (RabbitMQ management)

## Database Models

Core models in `app/models/`:
- `invoice.py` - Invoice records and processing status
- `reference.py` - Reference data for validation

## Testing Strategy

- Unit tests: `tests/unit/` - Individual service testing
- Integration tests: `tests/integration/` - End-to-end workflow testing
- Test fixtures: `tests/fixtures/` - Sample documents and data

## Configuration Files

- `pyproject.toml` - Python packaging and tool configuration
- `alembic.ini` - Database migration configuration
- `docker-compose.yml` - Development environment setup
- `.env.example` - Environment variable template

## Observability

- **Sentry** - Error tracking (configure SENTRY_DSN)
- **Langfuse** - LLM usage tracking (configure LANGFUSE keys)
- **Prometheus** - Metrics collection at /metrics endpoint
- Structured logging with request tracing

## Environment Setup

Copy `.env.example` to `.env` and configure:
- Database connection strings
- Storage backend credentials
- LLM API keys
- Monitoring service credentials