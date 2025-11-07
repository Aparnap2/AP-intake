"""
Integration tests for the enhanced storage service.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.storage_service import StorageService


@pytest.fixture
def storage_service():
    """Create a storage service instance for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Override storage path for testing
        settings.STORAGE_PATH = temp_dir
        settings.STORAGE_TYPE = "local"
        settings.STORAGE_COMPRESSION_ENABLED = True
        settings.STORAGE_COMPRESSION_TYPE = "gzip"
        settings.STORAGE_COMPRESSION_THRESHOLD = 100

        yield StorageService()


@pytest.fixture
def sample_file_content():
    """Sample file content for testing."""
    return b"This is a sample invoice PDF content for testing purposes. " * 20


class TestStorageServiceIntegration:
    """Integration tests for the enhanced storage service."""

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_store_file_integration(self, mock_session, storage_service, sample_file_content):
        """Test complete file storage integration."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Test file storage with all enhanced features
        result = await storage_service.store_file(
            file_content=sample_file_content,
            filename="invoice_12345.pdf",
            content_type="application/pdf",
            user_id="user123",
            session_id="session456",
            organization_path="company_ABC/2024",
            vendor_name="Global Supplies Inc.",
            invoice_date="2024-01-15"
        )

        # Verify enhanced storage service response
        assert result["storage_type"] == "local"
        assert result["filename"] == "invoice_12345.pdf"
        assert result["content_type"] == "application/pdf"
        assert result["file_hash"] is not None
        assert result["file_size"] == len(sample_file_content)
        assert result["url"].startswith("file://")
        assert "by_vendor/Global_Supplies_Inc" in result["file_path"]
        assert not result["deduplicated"]

        # Check if file was actually created
        file_path = Path(result["url"].replace("file://", ""))
        assert file_path.exists()

        # Verify file content
        with open(file_path, "rb") as f:
            stored_content = f.read()
        assert stored_content == sample_file_content

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_get_file_content_integration(self, mock_session, storage_service, sample_file_content):
        """Test complete file retrieval integration."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store a file first
        store_result = await storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user"
        )

        # Retrieve the file
        retrieved_content = await storage_service.get_file_content(
            file_path=store_result["file_path"],
            user_id="test_user",
            session_id="test_session"
        )

        assert retrieved_content == sample_file_content

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_file_operations_workflow(self, mock_session, storage_service, sample_file_content):
        """Test complete file operations workflow."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # 1. Store a file
        store_result = await storage_service.store_file(
            file_content=sample_file_content,
            filename="workflow_test.pdf",
            content_type="application/pdf",
            user_id="workflow_user",
            vendor_name="Test Vendor",
            invoice_date="2024-02-01"
        )

        # 2. Check if file exists
        exists = await storage_service.file_exists(store_result["file_path"])
        assert exists

        # 3. List files
        file_list = await storage_service.list_files(limit=10, user_id="workflow_user")
        assert len(file_list) >= 1

        # 4. Retrieve file content
        content = await storage_service.get_file_content(
            file_path=store_result["file_path"],
            user_id="workflow_user"
        )
        assert content == sample_file_content

        # 5. Archive file (soft delete)
        archived = await storage_service.delete_file(
            file_path=store_result["file_path"],
            user_id="workflow_user",
            permanent=False
        )
        assert archived

        # 6. Check file exists in archive
        archived_files = await storage_service.list_files(
            include_archived=True, user_id="workflow_user"
        )
        archived_paths = [f["path"] for f in archived_files if f.get("is_archived")]
        assert len(archived_paths) >= 1

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_compression_integration(self, mock_session, storage_service):
        """Test compression integration in storage service."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Create large content that should be compressed
        large_content = b"Large invoice content that should be compressed. " * 100

        # Store large file
        result = await storage_service.store_file(
            file_content=large_content,
            filename="large_invoice.pdf",
            content_type="application/pdf",
            user_id="compression_test"
        )

        # Check if compression was applied
        if result.get("is_compressed"):
            assert result["compression_ratio"] > 0.1
            assert result["compressed_size"] < result["original_size"]
            assert "compressed/" in result["file_path"]

        # Retrieve and verify content matches
        retrieved_content = await storage_service.get_file_content(
            file_path=result["file_path"],
            user_id="compression_test"
        )
        assert retrieved_content == large_content

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_vendor_organization_integration(self, mock_session, storage_service, sample_file_content):
        """Test vendor-based file organization."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        vendors = [
            "ABC Corporation",
            "XYZ Industries Ltd.",
            "Global Supplies Inc."
        ]

        stored_files = []
        for vendor in vendors:
            result = await storage_service.store_file(
                file_content=sample_file_content,
                filename=f"invoice_from_{vendor.lower().replace(' ', '_')}.pdf",
                content_type="application/pdf",
                user_id="org_test",
                vendor_name=vendor,
                invoice_date="2024-01-15"
            )
            stored_files.append(result)

        # Verify files are organized by vendor
        for i, result in enumerate(stored_files):
            assert f"by_vendor/{vendors[i].replace(' ', '_')}" in result["file_path"]

        # List files by vendor prefix
        abc_files = await storage_service.list_files(
            prefix="by_vendor/ABC_Corporation", user_id="org_test"
        )
        assert len(abc_files) >= 1

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_date_organization_integration(self, mock_session, storage_service, sample_file_content):
        """Test date-based file organization."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        dates = ["2024-01-15", "2024-02-20", "2024-03-10"]

        stored_files = []
        for date in dates:
            result = await storage_service.store_file(
                file_content=sample_file_content,
                filename=f"invoice_{date.replace('-', '')}.pdf",
                content_type="application/pdf",
                user_id="date_test",
                invoice_date=date
            )
            stored_files.append(result)

        # Verify files are organized by date
        for i, result in enumerate(stored_files):
            year, month = dates[i].split("-")[:2]
            assert f"by_date/{year}/{month}" in result["file_path"]

        # List files by date prefix
        jan_files = await storage_service.list_files(
            prefix="by_date/2024/01", user_id="date_test"
        )
        assert len(jan_files) >= 1

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_deduplication_integration(self, mock_session, storage_service, sample_file_content):
        """Test file deduplication integration."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store first file
        result1 = await storage_service.store_file(
            file_content=sample_file_content,
            filename="original_invoice.pdf",
            content_type="application/pdf",
            user_id="dedup_test"
        )
        assert not result1["deduplicated"]

        # Mock existing file for deduplication test
        with patch.object(
            storage_service.local_storage_service, '_check_deduplication',
            return_value={
                "stored_path": result1["file_path"],
                "is_compressed": False,
                "original_size": len(sample_file_content),
                "compressed_size": len(sample_file_content),
            }
        ):
            # Store duplicate content with different name
            result2 = await storage_service.store_file(
                file_content=sample_file_content,
                filename="duplicate_invoice.pdf",
                content_type="application/pdf",
                user_id="dedup_test"
            )

            assert result2["deduplicated"]
            assert result2["file_hash"] == result1["file_hash"]
            assert result2["file_path"] == result1["file_path"]

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_access_control_integration(self, mock_session, storage_service, sample_file_content):
        """Test file access control integration."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store file as user1
        result = await storage_service.store_file(
            file_content=sample_file_content,
            filename="access_control_test.pdf",
            content_type="application/pdf",
            user_id="user1"
        )

        # Mock access control to allow only user1
        with patch.object(
            storage_service.local_storage_service, '_check_file_access',
            side_effect=lambda path, user_id, require_delete=False: user_id == "user1"
        ):
            # Successful retrieval by owner
            content = await storage_service.get_file_content(
                file_path=result["file_path"],
                user_id="user1"
            )
            assert content == sample_file_content

            # Failed retrieval by unauthorized user
            with pytest.raises(Exception):  # Should raise access denied exception
                await storage_service.get_file_content(
                    file_path=result["file_path"],
                    user_id="user2"
                )

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_file_type_organization(self, mock_session, storage_service):
        """Test file type-based organization."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        file_types = [
            ("invoice.pdf", "application/pdf", "pdfs"),
            ("receipt.jpg", "image/jpeg", "images"),
            ("contract.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "documents"),
            ("data.bin", "application/octet-stream", "by_type")
        ]

        for filename, content_type, expected_dir in file_types:
            content = f"Content for {filename}".encode()

            result = await storage_service.store_file(
                file_content=content,
                filename=filename,
                content_type=content_type,
                user_id="type_test"
            )

            # Verify file organization
            if expected_dir != "by_type":  # Special case for unknown types
                assert expected_dir in result["file_path"]

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_error_handling_integration(self, mock_session, storage_service):
        """Test error handling in storage operations."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Test retrieval of non-existent file
        with pytest.raises(Exception):
            await storage_service.get_file_content("nonexistent/file.pdf")

        # Test deletion of non-existent file
        result = await storage_service.delete_file("nonexistent/file.pdf", permanent=True)
        assert not result

        # Test existence check for non-existent file
        exists = await storage_service.file_exists("nonexistent/file.pdf")
        assert not exists

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_large_file_handling(self, mock_session, storage_service):
        """Test handling of large files."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Create a large file content (simulating a large invoice PDF)
        large_content = b"Large invoice content. " * 10000  # ~300KB

        # Store large file
        result = await storage_service.store_file(
            file_content=large_content,
            filename="large_invoice.pdf",
            content_type="application/pdf",
            user_id="large_file_test"
        )

        # Verify storage
        assert result["file_size"] == len(large_content)
        assert result["file_hash"] is not None

        # Retrieve and verify
        retrieved = await storage_service.get_file_content(
            file_path=result["file_path"],
            user_id="large_file_test"
        )
        assert retrieved == large_content

        # Check if compression was beneficial for large file
        if result.get("is_compressed"):
            compression_ratio = result.get("compression_ratio", 0)
            assert compression_ratio > 0.1  # Should have meaningful compression