# TODO: Fix SQLAlchemy Relationship and Test E2E Workflow

## 1. SQLAlchemy Relationship Fix (URGENT)
- [ ] Fix FileDeduplication.audit_logs relationship in storage_audit.py
- [ ] Test database models import correctly
- [ ] Run alembic migration to update schema if needed

## 2. API Endpoint Testing
- [ ] Test invoice listing endpoint
- [ ] Test invoice upload endpoint
- [ ] Test all CRUD operations
- [ ] Verify API documentation is accessible

## 3. E2E Workflow Testing
- [ ] Invoice upload and processing
- [ ] Document extraction with Docling
- [ ] LLM patching for low-confidence fields
- [ ] Validation and business rules
- [ ] Triage (auto-approval vs human review)
- [ ] Export functionality

## 4. Frontend-Backend Integration
- [ ] Test React frontend connectivity
- [ ] Verify file upload through UI
- [ ] Check invoice listing in UI
- [ ] Test processing status display

## 5. Comprehensive Testing
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Run E2E tests
- [ ] Performance testing
- [ ] Error handling validation

## Current Status
- ✅ Neon PostgreSQL database connected
- ✅ Configuration loaded
- ❌ SQLAlchemy relationship error blocking API
- ❌ E2E workflow untested