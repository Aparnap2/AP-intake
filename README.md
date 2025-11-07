# AP Intake & Validation Pilot

A comprehensive AP (Accounts Payable) invoice processing system using Docling for intelligent document extraction, validation, and export capabilities.

## 🎯 Purpose

Transform emailed PDF invoices into validated, structured "prepared bills" ready for approval and ERP import without executing payments.

## 🏗️ Architecture

- **FastAPI** - REST API service
- **LangGraph** - State machine for invoice processing workflow
- **Docling** - Core document parsing and extraction
- **PostgreSQL** - Primary data store
- **Redis/RabbitMQ** - Caching and message queuing
- **S3/MinIO** - Document storage
- **Sentry/Langfuse** - Observability and monitoring

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for UI development)

### 1. Environment Setup

```bash
# Copy environment configuration
cp .env.example .env

# Edit .env with your configuration
# Set API keys, database URLs, etc.
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 3. Initialize Database

```bash
# Run database migrations
docker-compose exec api alembic upgrade head

# Seed sample data (optional)
docker-compose exec api python scripts/seed_data.py
```

### 4. Access Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin123)
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Web UI**: http://localhost:3000

## 📁 Project Structure

```
ap_intake/
├── app/                    # FastAPI application
│   ├── api/               # API routes
│   ├── core/              # Core configuration and utilities
│   ├── db/                # Database session management
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic services
│   ├── workers/           # Background tasks
│   └── utils/             # Helper utilities
├── web/                   # React frontend
├── migrations/            # Alembic database migrations
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── docs/                  # Documentation
├── docker-compose.yml     # Development environment
├── Dockerfile            # Application container
└── requirements.txt      # Python dependencies
```

## 🔄 Workflow

1. **Ingestion** - Email or file upload capture
2. **Extraction** - Docling parsing with confidence scoring
3. **Validation** - Business rules and compliance checks
4. **Triage** - Auto-approve vs exception handling
5. **Review** - Human-in-the-loop validation
6. **Export** - CSV/JSON payload generation
7. **Integration** - ERP system import (sandbox mode)

## 🧪 Testing

```bash
# Run unit tests
docker-compose exec api pytest tests/unit/

# Run integration tests
docker-compose exec api pytest tests/integration/

# Run all tests with coverage
docker-compose exec api pytest --cov=app tests/
```

## 📊 Monitoring

- **Sentry** - Error tracking and performance monitoring
- **Langfuse** - LLM usage and cost tracking
- **Prometheus** - Metrics collection
- **Health Checks** - Service availability monitoring

## 🔧 Configuration

Key environment variables:

- `DATABASE_URL` - PostgreSQL connection string
- `RABBITMQ_URL` - Message broker URL
- `STORAGE_TYPE` - Document storage backend (local/s3/r2/supabase)
- `DOCLING_CONFIDENCE_THRESHOLD` - Minimum confidence for auto-approval
- `LLM_MODEL` - Model for low-confidence field patching

## 🚀 Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start database (if not using Docker)
docker-compose up postgres redis rabbitmq minio

# Run Alembic migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload

# Start worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info
```

### Code Quality

```bash
# Format code
black app/ tests/
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

## 📋 API Endpoints

### Core Operations

- `POST /invoices/upload` - Upload invoice files
- `GET /invoices/{id}` - Get invoice details
- `PUT /invoices/{id}/review` - Update invoice after review
- `POST /invoices/{id}/approve` - Approve invoice
- `GET /invoices/{id}/export/csv` - Download CSV export
- `GET /invoices/{id}/export/json` - Download JSON export

### Management

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `GET /status` - System status overview

## 🔐 Security

- JWT-based authentication
- File type validation
- Size limits enforced
- Audit logging enabled
- RBAC for user permissions

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make your changes
4. Add tests
5. Run test suite
6. Submit pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- Create GitHub issues for bugs
- Check documentation in `/docs`
- Review test files for usage examples