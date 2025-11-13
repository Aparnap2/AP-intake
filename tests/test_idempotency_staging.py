"""
Comprehensive tests for idempotency and staging infrastructure.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.idempotency_service import IdempotencyService, IdempotencyOperationType, IdempotencyStatus
from app.services.staging_service import StagingService, StagingStatus, ExportFormat
from app.models.idempotency import IdempotencyRecord, IdempotencyConflict
from app.models.staging import StagedExport, StagingAuditTrail
from app.core.exceptions import ConflictException, ValidationException


class TestIdempotencyService:
    """Test suite for IdempotencyService."""

    @pytest.fixture
    def idempotency_service(self):
        """Create idempotency service instance."""
        return IdempotencyService()

    @pytest.fixture
    def sample_operation_data(self):
        """Sample operation data for testing."""
        return {
            "filename": "test_invoice.pdf",
            "vendor_id": str(uuid.uuid4()),
            "source_type": "upload",
            "file_hash": "abc123def456",
        }

    @pytest.mark.asyncio
    async def test_generate_idempotency_key(self, idempotency_service):
        """Test idempotency key generation."""
        # Test with invoice upload operation
        key1 = idempotency_service.generate_idempotency_key(
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            vendor_id="vendor_123",
            file_hash="hash_123",
            user_id="user_123"
        )

        # Generate same key again with same parameters
        key2 = idempotency_service.generate_idempotency_key(
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            vendor_id="vendor_123",
            file_hash="hash_123",
            user_id="user_123"
        )

        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex length

        # Test different parameters generate different keys
        key3 = idempotency_service.generate_idempotency_key(
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            vendor_id="vendor_456",  # Different vendor
            file_hash="hash_123",
            user_id="user_123"
        )

        assert key1 != key3

    @pytest.mark.asyncio
    async def test_check_and_create_new_record(self, idempotency_service, sample_operation_data, db_session):
        """Test creating new idempotency record."""
        idempotency_key = "test_key_123"

        record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            operation_data=sample_operation_data,
            user_id="test_user",
        )

        assert is_new is True
        assert record.idempotency_key == idempotency_key
        assert record.operation_type == IdempotencyOperationType.INVOICE_UPLOAD
        assert record.operation_status == IdempotencyStatus.PENDING
        assert record.operation_data == sample_operation_data
        assert record.user_id == "test_user"
        assert record.execution_count == 0

    @pytest.mark.asyncio
    async def test_existing_completed_record(self, idempotency_service, sample_operation_data, db_session):
        """Test handling existing completed record."""
        idempotency_key = "test_key_456"

        # Create initial record
        record1, is_new1 = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            operation_data=sample_operation_data,
            user_id="test_user",
        )

        # Mark as completed
        await idempotency_service.mark_operation_completed(
            db=db_session,
            idempotency_key=idempotency_key,
            result_data={"status": "completed", "invoice_id": str(uuid.uuid4())}
        )

        # Try to create record with same key
        record2, is_new2 = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            operation_data=sample_operation_data,
            user_id="test_user",
        )

        assert is_new2 is False
        assert record2.id == record1.id
        assert record2.operation_status == IdempotencyStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_concurrent_operation_conflict(self, idempotency_service, sample_operation_data, db_session):
        """Test handling concurrent operation conflicts."""
        idempotency_key = "test_key_789"

        # Create initial record
        record1, is_new1 = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            operation_data=sample_operation_data,
            user_id="test_user",
        )

        # Mark as in progress
        await idempotency_service.mark_operation_started(db=db_session, idempotency_key=idempotency_key)

        # Try to create record with same key while in progress
        with pytest.raises(ConflictException) as exc_info:
            await idempotency_service.check_and_create_idempotency_record(
                db=db_session,
                idempotency_key=idempotency_key,
                operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
                operation_data=sample_operation_data,
                user_id="test_user",
            )

        assert "already in progress" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_operation_lifecycle(self, idempotency_service, sample_operation_data, db_session):
        """Test complete operation lifecycle."""
        idempotency_key = "test_key_lifecycle"

        # Create record
        record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_PROCESS,
            operation_data=sample_operation_data,
            user_id="test_user",
        )

        assert record.operation_status == IdempotencyStatus.PENDING

        # Start operation
        success = await idempotency_service.mark_operation_started(db=db_session, idempotency_key=idempotency_key)
        assert success is True

        # Check status
        await db_session.refresh(record)
        assert record.operation_status == IdempotencyStatus.IN_PROGRESS
        assert record.execution_count == 1

        # Complete operation
        result_data = {"invoice_id": str(uuid.uuid4()), "status": "processed"}
        success = await idempotency_service.mark_operation_completed(
            db=db_session,
            idempotency_key=idempotency_key,
            result_data=result_data
        )
        assert success is True

        # Check final status
        await db_session.refresh(record)
        assert record.operation_status == IdempotencyStatus.COMPLETED
        assert record.result_data == result_data
        assert record.completed_at is not None

    @pytest.mark.asyncio
    async def test_failed_operation_retry(self, idempotency_service, sample_operation_data, db_session):
        """Test failed operation retry logic."""
        idempotency_key = "test_key_retry"

        # Create record
        record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_PROCESS,
            operation_data=sample_operation_data,
            user_id="test_user",
            max_executions=3,
        )

        # Start and fail operation
        await idempotency_service.mark_operation_started(db=db_session, idempotency_key=idempotency_key)
        error_data = {"error": "Processing failed", "code": "PROCESSING_ERROR"}
        await idempotency_service.mark_operation_failed(
            db=db_session,
            idempotency_key=idempotency_key,
            error_data=error_data
        )

        # Check failed status
        await db_session.refresh(record)
        assert record.operation_status == IdempotencyStatus.FAILED
        assert record.error_data == error_data
        assert record.execution_count == 1

        # Retry operation
        record2, is_new2 = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_PROCESS,
            operation_data=sample_operation_data,
            user_id="test_user",
        )

        assert is_new2 is False  # Same record
        assert record2.execution_count == 1  # Not yet incremented

    @pytest.mark.asyncio
    async def test_cleanup_expired_records(self, idempotency_service, db_session):
        """Test cleanup of expired records."""
        # Create expired record
        expired_record = IdempotencyRecord(
            idempotency_key="expired_key",
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            operation_status=IdempotencyStatus.COMPLETED,
            operation_data={"test": "data"},
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        )
        db_session.add(expired_record)
        await db_session.commit()

        # Create active record
        active_record = IdempotencyRecord(
            idempotency_key="active_key",
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            operation_status=IdempotencyStatus.IN_PROGRESS,
            operation_data={"test": "data"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),  # Not expired
        )
        db_session.add(active_record)
        await db_session.commit()

        # Run cleanup
        cleanup_stats = await idempotency_service.cleanup_expired_records(db=db_session)

        assert cleanup_stats["expired_records_found"] == 1
        assert cleanup_stats["records_deleted"] == 1

        # Verify expired record is deleted
        stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == "expired_key")
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

        # Verify active record still exists
        stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == "active_key")
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is not None


class TestStagingService:
    """Test suite for StagingService."""

    @pytest.fixture
    def staging_service(self):
        """Create staging service instance."""
        return StagingService()

    @pytest.fixture
    def sample_export_data(self):
        """Sample export data for testing."""
        return {
            "vendor_name": "Test Vendor",
            "invoice_number": "INV-001",
            "invoice_date": "2025-01-10",
            "total_amount": 1000.00,
            "currency": "USD",
            "line_items": [
                {
                    "description": "Test Item",
                    "quantity": 1,
                    "unit_price": 1000.00,
                    "total": 1000.00
                }
            ]
        }

    @pytest.fixture
    def sample_invoice(self, db_session):
        """Create sample invoice for testing."""
        from app.models.invoice import Invoice

        invoice = Invoice(
            file_url="test_url",
            file_hash="test_hash",
            file_name="test.pdf",
            file_size="1MB",
            status="validated"
        )
        db_session.add(invoice)
        await db_session.commit()
        await db_session.refresh(invoice)
        return invoice

    @pytest.mark.asyncio
    async def test_stage_export(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test staging an export."""
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.CSV,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
            business_unit="accounting",
            cost_center="general",
        )

        assert staged_export.invoice_id == sample_invoice.id
        assert staged_export.export_format == ExportFormat.CSV
        assert staged_export.destination_system == "test_erp"
        assert staged_export.staging_status == StagingStatus.PREPARED
        assert staged_export.prepared_data == sample_export_data
        assert staged_export.business_unit == "accounting"
        assert staged_export.cost_center == "general"
        assert staged_export.quality_score is not None
        assert staged_export.prepared_at is not None

    @pytest.mark.asyncio
    async def test_approve_staged_export(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test approving a staged export."""
        # First stage an export
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.JSON,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
        )

        # Modify export data slightly
        modified_data = sample_export_data.copy()
        modified_data["total_amount"] = 1100.00

        # Approve with modifications
        approved_by = str(uuid.uuid4())
        approved_export = await staging_service.approve_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            approved_by=approved_by,
            approved_data=modified_data,
            change_reason="Corrected total amount",
            approval_comments="Looks good otherwise",
        )

        assert approved_export.staging_status == StagingStatus.APPROVED
        assert approved_export.approved_by == uuid.UUID(approved_by)
        assert approved_export.approved_at is not None
        assert approved_export.approved_data == modified_data
        assert approved_export.change_reason == "Corrected total amount"
        assert approved_export.reviewer_comments == "Looks good otherwise"
        assert approved_export.field_changes is not None

    @pytest.mark.asyncio
    async def test_post_staged_export(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test posting a staged export."""
        # Stage and approve an export
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.XML,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
        )

        await staging_service.approve_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            approved_by=str(uuid.uuid4()),
        )

        # Post the export
        posted_by = str(uuid.uuid4())
        external_ref = "EXT-12345"
        posted_export = await staging_service.post_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            posted_by=posted_by,
            external_reference=external_ref,
            export_filename="export_123.xml",
            export_file_size=2048,
        )

        assert posted_export.staging_status == StagingStatus.POSTED
        assert posted_export.posted_by == uuid.UUID(posted_by)
        assert posted_export.posted_at is not None
        assert posted_export.external_reference == external_ref
        assert posted_export.export_filename == "export_123.xml"
        assert posted_export.export_file_size == 2048
        assert posted_export.export_job_id is not None

    @pytest.mark.asyncio
    async def test_reject_staged_export(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test rejecting a staged export."""
        # Stage an export
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.CSV,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
        )

        # Reject the export
        rejected_by = str(uuid.uuid4())
        rejection_reason = "Missing required fields"
        rejected_export = await staging_service.reject_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            rejected_by=rejected_by,
            rejection_reason=rejection_reason,
        )

        assert rejected_export.staging_status == StagingStatus.REJECTED
        assert rejected_export.rejected_by == uuid.UUID(rejected_by)
        assert rejected_export.rejected_at is not None
        assert rejection_reason in rejected_export.audit_notes

    @pytest.mark.asyncio
    async def test_get_staged_export_diff(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test getting diff for staged export."""
        # Stage an export
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.JSON,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
        )

        # Get diff
        diff_data = await staging_service.get_staged_export_diff(
            db=db_session,
            staged_export_id=str(staged_export.id)
        )

        assert diff_data["staged_export_id"] == str(staged_export.id)
        assert diff_data["invoice_id"] == str(sample_invoice.id)
        assert diff_data["destination_system"] == "test_erp"
        assert diff_data["export_format"] == "json"
        assert "original_to_prepared" in diff_data
        assert "summary" in diff_data["original_to_prepared"]
        assert diff_data["prepared_to_approved"] is None  # Not approved yet

    @pytest.mark.asyncio
    async def test_rollback_staged_export(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test rolling back a posted export."""
        # Stage, approve, and post an export
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.CSV,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
        )

        await staging_service.approve_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            approved_by=str(uuid.uuid4()),
        )

        await staging_service.post_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            posted_by=str(uuid.uuid4()),
            external_reference="EXT-12345",
        )

        # Roll back the export
        rolled_back_by = str(uuid.uuid4())
        rollback_reason = "Customer requested cancellation"
        rolled_back_export = await staging_service.rollback_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            rolled_back_by=rolled_back_by,
            rollback_reason=rollback_reason,
        )

        assert rolled_back_export.staging_status == StagingStatus.ROLLED_BACK
        assert rollback_reason in rolled_back_export.audit_notes
        assert rolled_back_export.external_reference is None  # Cleared on rollback

    @pytest.mark.asyncio
    async def test_list_staged_exports(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test listing staged exports with filters."""
        # Create multiple staged exports
        exports = []
        for i in range(5):
            export = await staging_service.stage_export(
                db=db_session,
                invoice_id=str(sample_invoice.id),
                export_data=sample_export_data,
                export_format=ExportFormat.CSV,
                destination_system=f"test_erp_{i}",
                prepared_by=str(uuid.uuid4()),
                business_unit="accounting" if i % 2 == 0 else "finance",
            )
            exports.append(export)

        # Approve some exports
        for i in range(2):
            await staging_service.approve_staged_export(
                db=db_session,
                staged_export_id=str(exports[i].id),
                approved_by=str(uuid.uuid4()),
            )

        # Test listing all exports
        all_exports, total = await staging_service.list_staged_exports(db=db_session)
        assert total >= 5
        assert len(all_exports) >= 5

        # Test filtering by business unit
        accounting_exports, accounting_total = await staging_service.list_staged_exports(
            db=db_session,
            business_unit="accounting"
        )
        assert accounting_total >= 3  # 3 accounting exports

        # Test filtering by status
        prepared_exports, prepared_total = await staging_service.list_staged_exports(
            db=db_session,
            status=StagingStatus.PREPARED
        )
        assert prepared_total >= 3  # 3 still prepared

    @pytest.mark.asyncio
    async def test_duplicate_staging_prevention(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test prevention of duplicate staging for same invoice/destination."""
        # Stage first export
        export1 = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.CSV,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
        )

        # Try to stage another export for same invoice/destination
        with pytest.raises(ConflictException) as exc_info:
            await staging_service.stage_export(
                db=db_session,
                invoice_id=str(sample_invoice.id),
                export_data=sample_export_data,
                export_format=ExportFormat.JSON,  # Different format
                destination_system="test_erp",  # Same destination
                prepared_by=str(uuid.uuid4()),
            )

        assert "already staged" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_audit_trail_creation(self, staging_service, sample_export_data, sample_invoice, db_session):
        """Test that audit trail entries are created for all operations."""
        # Stage export
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(sample_invoice.id),
            export_data=sample_export_data,
            export_format=ExportFormat.CSV,
            destination_system="test_erp",
            prepared_by=str(uuid.uuid4()),
        )

        # Check audit trail for staging
        stmt = select(StagingAuditTrail).where(
            StagingAuditTrail.staged_export_id == staged_export.id
        )
        result = await db_session.execute(stmt)
        audit_entries = result.scalars().all()

        assert len(audit_entries) == 1
        assert audit_entries[0].action == "created"
        assert audit_entries[0].business_event == "export_staged"

        # Approve export
        await staging_service.approve_staged_export(
            db=db_session,
            staged_export_id=str(staged_export.id),
            approved_by=str(uuid.uuid4()),
            change_reason="Test approval",
        )

        # Check audit trail for approval
        result = await db_session.execute(stmt)
        audit_entries = result.scalars().all()

        assert len(audit_entries) == 2
        approval_entry = next(e for e in audit_entries if e.action == "approved")
        assert approval_entry.business_event == "export_approved"
        assert approval_entry.action_reason == "Test approval"


class TestIdempotencyStagingIntegration:
    """Integration tests for idempotency and staging working together."""

    @pytest.mark.asyncio
    async def test_staging_with_idempotency(self, db_session):
        """Test that staging operations properly use idempotency."""
        idempotency_service = IdempotencyService()
        staging_service = StagingService()

        # Create sample data
        from app.models.invoice import Invoice
        invoice = Invoice(
            file_url="test_url",
            file_hash="test_hash",
            file_name="test.pdf",
            file_size="1MB",
            status="validated"
        )
        db_session.add(invoice)
        await db_session.commit()

        export_data = {"vendor_name": "Test", "total": 1000}
        prepared_by = str(uuid.uuid4())

        # Generate idempotency key for staging
        idempotency_key = idempotency_service.generate_idempotency_key(
            operation_type=IdempotencyOperationType.EXPORT_STAGE,
            invoice_id=str(invoice.id),
            destination_system="test_erp",
            user_id=prepared_by,
        )

        # Stage export with idempotency
        record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.EXPORT_STAGE,
            operation_data={"invoice_id": str(invoice.id), "destination": "test_erp"},
            invoice_id=str(invoice.id),
            user_id=prepared_by,
        )

        assert is_new is True

        # Mark operation as started
        await idempotency_service.mark_operation_started(db=db_session, idempotency_key)

        # Perform staging
        staged_export = await staging_service.stage_export(
            db=db_session,
            invoice_id=str(invoice.id),
            export_data=export_data,
            export_format=ExportFormat.CSV,
            destination_system="test_erp",
            prepared_by=prepared_by,
        )

        # Mark operation as completed
        await idempotency_service.mark_operation_completed(
            db=db_session,
            idempotency_key=idempotency_key,
            result_data={"staged_export_id": str(staged_export.id)}
        )

        # Try to stage again with same idempotency key
        record2, is_new2 = await idempotency_service.check_and_create_idempotency_record(
            db=db_session,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.EXPORT_STAGE,
            operation_data={"invoice_id": str(invoice.id), "destination": "test_erp"},
            invoice_id=str(invoice.id),
            user_id=prepared_by,
        )

        assert is_new2 is False
        assert record2.result_data["staged_export_id"] == str(staged_export.id)