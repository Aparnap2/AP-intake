# AP Intake & Validation Pilot

A comprehensive AP (Accounts Payable) invoice processing system using Docling for intelligent document extraction, validation, and export capabilities.

## 🎯 Purpose

Transform emailed PDF invoices into validated, structured "prepared bills" ready for approval and ERP import without executing payments.

## 📋 Quick Links

- **📚 Documentation**: [Comprehensive docs](./docs/) - Architecture, integration, deployment, and development guides
- **🚀 Getting Started**: Quick setup instructions below
- **🧪 Testing**: Comprehensive test suite with unit, integration, and e2e tests
- **🔧 Configuration**: Environment setup and configuration details
- **📊 API Docs**: Interactive API documentation at `/docs` endpoint

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
├── app/                           # FastAPI application
│   ├── api/                      # API routes
│   ├── core/                     # Core configuration and utilities
│   ├── db/                       # Database session management
│   ├── models/                   # SQLAlchemy models
│   ├── services/                 # Business logic services
│   ├── workflows/                # LangGraph workflow definitions
│   ├── workers/                  # Background tasks (Celery)
│   └── utils/                    # Helper utilities
├── web/                          # React frontend
│   ├── app/                      # Next.js app router pages
│   ├── components/               # React components
│   ├── tests/                    # Frontend tests (Playwright)
│   └── test-results/             # Test results and reports
├── docs/                         # Comprehensive documentation
│   ├── architecture/             # System architecture and design
│   ├── integration/              # External service integration
│   ├── deployment/               # Production deployment guides
│   ├── development/              # Development setup and guides
│   ├── reports/                  # Analysis reports and assessments
│   └── README.md                 # Documentation index
├── tests/                        # Backend test suite
│   ├── unit/                     # Unit tests for individual services
│   ├── integration/              # Integration tests for workflows
│   ├── e2e/                      # End-to-end tests
│   ├── api/                      # API endpoint tests
│   ├── services/                 # Service layer tests
│   ├── models/                   # Model tests
│   ├── workflows/                # Workflow tests
│   ├── fixtures/                 # Test data and fixtures
│   └── reports/                  # Test reports
├── test_reports/                 # Test execution reports
├── migrations/                   # Alembic database migrations
├── scripts/                      # Utility scripts
├── docker-compose.yml            # Development environment
├── Dockerfile                   # Application container
├── pyproject.toml               # Python dependencies and tooling
├── CLAUDE.md                    # Development instructions for Claude
└── README.md                    # This file
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

The project has a comprehensive test suite organized by type:

### Backend Testing

```bash
# Run unit tests for individual services
docker-compose exec api pytest tests/unit/ -v

# Run integration tests for workflows and services
docker-compose exec api pytest tests/integration/ -v

# Run end-to-end tests
docker-compose exec api pytest tests/e2e/ -v

# Run API endpoint tests
docker-compose exec api pytest tests/api/ -v

# Run all tests with coverage report
docker-compose exec api pytest --cov=app --cov-report=html tests/

# Run tests with specific markers
docker-compose exec api pytest -m "unit" -v
docker-compose exec api pytest -m "integration" -v
docker-compose exec api pytest -m "e2e" -v

# Run performance tests
docker-compose exec api pytest tests/performance/ -v
```

### Frontend Testing

```bash
# Navigate to frontend directory
cd web/

# Run Playwright tests
npm test

# Run tests with UI
npm run test:ui

# Run tests in debug mode
npm run test:debug

# Generate test report
npm run test:report
```

### Test Organization

- **Unit Tests** (`tests/unit/`) - Individual service and component testing
- **Integration Tests** (`tests/integration/`) - Workflow and service integration testing
- **E2E Tests** (`tests/e2e/`) - Full end-to-end scenario testing
- **API Tests** (`tests/api/`) - REST API endpoint testing
- **Performance Tests** (`tests/performance/`) - Load and performance testing

For detailed testing guidelines, see [Testing Guide](./docs/development/testing-guide.md).

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
# Install dependencies (using uv)
uv sync

# Or with pip
pip install -r requirements.txt

# Start database (if not using Docker)
docker-compose up postgres redis rabbitmq minio

# Run Alembic migrations
docker-compose exec api alembic upgrade head

# Start API server
uvicorn app.main:app --reload

# Start worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info
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

### Development Documentation

For comprehensive development guides, see:
- [Development Setup](./docs/development/)
- [Database Setup](./docs/development/database-setup.md)
- [Testing Strategy](./docs/development/testing-strategy.md)
- [Architecture Documentation](./docs/architecture/)

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

## 🆘 Support & Resources

### Documentation
- **📚 Main Documentation**: [docs/](./docs/) - Comprehensive guides and references
- **🏗️ Architecture**: System design and workflow documentation
- **🔌 Integration**: External service integration guides
- **🚀 Deployment**: Production deployment and operational guides
- **🛠️ Development**: Development setup and guidelines

### Getting Help
- Create GitHub issues for bugs and feature requests
- Review test files for usage examples
- Check the [development guides](./docs/development/) for setup assistance
- Refer to [CLAUDE.md](./CLAUDE.md) for AI assistant development instructions

### Key Resources
- **API Documentation**: Available at `/docs` endpoint when running
- **Testing Information**: [Testing Guide](./docs/development/testing-guide.md)
- **Database Setup**: [Database Setup Guide](./docs/development/database-setup.md)
- **Production Deployment**: [Deployment Guide](./docs/deployment/deployment-guide.md)