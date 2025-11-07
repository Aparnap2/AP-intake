"""
Unit tests for the enhanced local storage service.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import StorageException
from app.services.local_storage_service import LocalStorageService


@pytest.fixture
def local_storage_service():
    """Create a local storage service instance for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Override storage path for testing
        settings.STORAGE_PATH = temp_dir
        settings.STORAGE_COMPRESSION_ENABLED = True
        settings.STORAGE_COMPRESSION_TYPE = "gzip"
        settings.STORAGE_COMPRESSION_THRESHOLD = 100

        yield LocalStorageService()


@pytest.fixture
def sample_file_content():
    """Sample file content for testing."""
    return b"This is a sample file content for testing purposes. " * 10


@pytest.fixture
def small_file_content():
    """Small file content for testing compression threshold."""
    return b"Small content"


class TestLocalStorageService:
    """Test cases for LocalStorageService."""

    def test_init_storage_directories(self, local_storage_service):
        """Test storage directory initialization."""
        storage_path = local_storage_service.storage_path

        # Check that all directories were created
        assert storage_path.exists()
        assert (storage_path / "originals").exists()
        assert (storage_path / "processed").exists()
        assert (storage_path / "compressed").exists()
        assert (storage_path / "temp").exists()
        assert (storage_path / "archive").exists()
        assert (storage_path / "by_date").exists()
        assert (storage_path / "by_vendor").exists()
        assert (storage_path / "by_type").exists()

    def test_generate_organized_file_path(self, local_storage_service):
        """Test file path generation with different organization criteria."""
        file_hash = "a1b2c3d4e5f6789012345678901234567890abcd"
        filename = "test_invoice.pdf"

        # Test default organization
        path = local_storage_service._generate_organized_file_path(file_hash, filename)
        expected_prefix = f"{file_hash[:2]}/{file_hash[2:4]}"
        assert path.startswith(expected_prefix)
        assert path.endswith(f"{file_hash}.pdf")

        # Test organization path
        org_path = "company123/2024"
        path = local_storage_service._generate_organized_file_path(
            file_hash, filename, organization_path=org_path
        )
        assert path.startswith(f"{org_path}/{expected_prefix}")

        # Test vendor-based organization
        vendor_name = "ACME Corp"
        path = local_storage_service._generate_organized_file_path(
            file_hash, filename, vendor_name=vendor_name
        )
        assert path.startswith(f"by_vendor/ACME_Corp/{expected_prefix}")

        # Test date-based organization
        invoice_date = "2024-01-15"
        path = local_storage_service._generate_organized_file_path(
            file_hash, filename, invoice_date=invoice_date
        )
        assert path.startswith(f"by_date/2024/01/{expected_prefix}")

    @pytest.mark.asyncio
    async def test_compress_file_gzip(self, local_storage_service, sample_file_content):
        """Test file compression with gzip."""
        # Set up compression settings
        local_storage_service.compression_enabled = True
        local_storage_service.compression_type = "gzip"
        local_storage_service.compression_threshold = 100

        compressed_content, is_compressed, compression_info = await local_storage_service._compress_file(
            sample_file_content, "application/pdf"
        )

        assert is_compressed
        assert compression_info is not None
        assert compression_info["type"] == "gzip"
        assert compression_info["original_size"] == len(sample_file_content)
        assert compression_info["compressed_size"] == len(compressed_content)
        assert compression_info["ratio"] > 0.1  # Should have at least 10% compression

        # Verify decompression works
        decompressed_content = await local_storage_service._decompress_file(compressed_content, "")
        assert decompressed_content == sample_file_content

    @pytest.mark.asyncio
    async def test_compress_file_below_threshold(self, local_storage_service, small_file_content):
        """Test that files below compression threshold are not compressed."""
        local_storage_service.compression_enabled = True
        local_storage_service.compression_type = "gzip"
        local_storage_service.compression_threshold = 1000  # Higher than small file

        compressed_content, is_compressed, compression_info = await local_storage_service._compress_file(
            small_file_content, "application/pdf"
        )

        assert not is_compressed
        assert compression_info is None
        assert compressed_content == small_file_content

    @pytest.mark.asyncio
    async def test_compress_file_disabled(self, local_storage_service, sample_file_content):
        """Test that compression is disabled when setting is False."""
        local_storage_service.compression_enabled = False

        compressed_content, is_compressed, compression_info = await local_storage_service._compress_file(
            sample_file_content, "application/pdf"
        )

        assert not is_compressed
        assert compression_info is None
        assert compressed_content == sample_file_content

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_store_file_basic(self, mock_session, local_storage_service, sample_file_content):
        """Test basic file storage functionality."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store file
        result = await local_storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user"
        )

        # Verify result structure
        assert result["storage_type"] == "local"
        assert result["filename"] == "test_invoice.pdf"
        assert result["content_type"] == "application/pdf"
        assert result["file_hash"] is not None
        assert result["file_size"] == len(sample_file_content)
        assert result["url"].startswith("file://")
        assert not result["deduplicated"]

        # Verify file was created
        file_path = Path(result["url"].replace("file://", ""))
        assert file_path.exists()

        # Verify content matches
        with open(file_path, "rb") as f:
            stored_content = f.read()
        assert stored_content == sample_file_content

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_store_file_with_compression(self, mock_session, local_storage_service, sample_file_content):
        """Test file storage with compression."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store file
        result = await local_storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user"
        )

        # If compression was successful, check compressed storage
        if result.get("is_compressed"):
            assert "compressed/" in result["file_path"]
            assert result["compression_ratio"] > 0

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_store_file_with_vendor_organization(
        self, mock_session, local_storage_service, sample_file_content
    ):
        """Test file storage with vendor-based organization."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store file with vendor information
        result = await local_storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user",
            vendor_name="ACME Corporation",
            invoice_date="2024-01-15"
        )

        # Check that file is organized by vendor
        assert "by_vendor/ACME_Corporation" in result["file_path"]

        # Check that organizational links were created
        vendor_link_path = local_storage_service.storage_path / "by_vendor" / "ACME_Corporation"
        assert vendor_link_path.exists()

        date_link_path = local_storage_service.storage_path / "by_date" / "2024" / "01"
        assert date_link_path.exists()

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_store_file_deduplication(self, mock_session, local_storage_service, sample_file_content):
        """Test file deduplication functionality."""
        # Mock database operations to simulate existing file
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # First storage - should create new file
        result1 = await local_storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user"
        )
        assert not result1["deduplicated"]

        # Mock existing file in database
        mock_dedup_record = MagicMock()
        mock_dedup_record.stored_path = result1["file_path"]
        mock_dedup_record.is_compressed = False
        mock_dedup_record.original_size = len(sample_file_content)
        mock_dedup_record.compressed_size = len(sample_file_content)

        with patch.object(
            local_storage_service, '_check_deduplication',
            return_value={
                "stored_path": result1["file_path"],
                "is_compressed": False,
                "original_size": len(sample_file_content),
                "compressed_size": len(sample_file_content),
            }
        ):
            # Second storage with same content - should use deduplication
            result2 = await local_storage_service.store_file(
                file_content=sample_file_content,
                filename="test_invoice_copy.pdf",
                content_type="application/pdf",
                user_id="test_user"
            )

            assert result2["deduplicated"]
            assert result2["file_hash"] == result1["file_hash"]
            assert result2["file_path"] == result1["file_path"]

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_get_file_content(self, mock_session, local_storage_service, sample_file_content):
        """Test file content retrieval."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # First store a file
        store_result = await local_storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user"
        )

        # Retrieve file content
        retrieved_content = await local_storage_service.get_file_content(
            file_path=store_result["file_path"],
            user_id="test_user"
        )

        assert retrieved_content == sample_file_content

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, local_storage_service):
        """Test file content retrieval for non-existent file."""
        with pytest.raises(StorageException, match="File not found"):
            await local_storage_service.get_file_content("nonexistent/path/file.pdf")

    @pytest.mark.asyncio
    async def test_file_exists(self, local_storage_service):
        """Test file existence check."""
        # Test non-existent file
        assert not await local_storage_service.file_exists("nonexistent/path/file.pdf")

        # Create a test file
        test_file = local_storage_service.storage_path / "test_file.txt"
        test_file.write_text("test content")

        # Test existing file
        assert await local_storage_service.file_exists("test_file.txt")

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_delete_file_permanent(self, mock_session, local_storage_service, sample_file_content):
        """Test permanent file deletion."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store a file first
        store_result = await local_storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user"
        )

        file_path = Path(store_result["url"].replace("file://", ""))
        assert file_path.exists()

        # Delete the file permanently
        delete_result = await local_storage_service.delete_file(
            file_path=store_result["file_path"],
            user_id="test_user",
            permanent=True
        )

        assert delete_result
        assert not file_path.exists()

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_delete_file_archive(self, mock_session, local_storage_service, sample_file_content):
        """Test file archival."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store a file first
        store_result = await local_storage_service.store_file(
            file_content=sample_file_content,
            filename="test_invoice.pdf",
            content_type="application/pdf",
            user_id="test_user"
        )

        original_path = Path(store_result["url"].replace("file://", ""))
        assert original_path.exists()

        # Archive the file
        delete_result = await local_storage_service.delete_file(
            file_path=store_result["file_path"],
            user_id="test_user",
            permanent=False
        )

        assert delete_result
        assert not original_path.exists()

        # Check that file was moved to archive
        archive_path = local_storage_service.storage_path / "archive" / store_result["file_path"]
        assert archive_path.exists()

    @pytest.mark.asyncio
    @patch('app.services.local_storage_service.AsyncSessionLocal')
    async def test_list_files(self, mock_session, local_storage_service, sample_file_content):
        """Test file listing functionality."""
        # Mock database operations
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Store some test files
        stored_files = []
        for i in range(3):
            result = await local_storage_service.store_file(
                file_content=sample_file_content,
                filename=f"test_invoice_{i}.pdf",
                content_type="application/pdf",
                user_id="test_user"
            )
            stored_files.append(result)

        # List files
        file_list = await local_storage_service.list_files(limit=10, user_id="test_user")

        assert len(file_list) >= 3
        for file_info in file_list:
            assert "path" in file_info
            assert "size" in file_info
            assert "last_modified" in file_info
            assert "url" in file_info
            assert not file_info.get("is_archived", False)

    @pytest.mark.asyncio
    async def test_list_files_with_prefix(self, local_storage_service):
        """Test file listing with prefix filtering."""
        # Create test files in different directories
        (local_storage_service.storage_path / "test_dir").mkdir(exist_ok=True)
        (local_storage_service.storage_path / "other_dir").mkdir(exist_ok=True)

        test_file1 = local_storage_service.storage_path / "test_dir" / "file1.txt"
        test_file2 = local_storage_service.storage_path / "test_dir" / "file2.txt"
        test_file3 = local_storage_service.storage_path / "other_dir" / "file3.txt"

        test_file1.write_text("content1")
        test_file2.write_text("content2")
        test_file3.write_text("content3")

        # List files with prefix
        file_list = await local_storage_service.list_files(prefix="test_dir", user_id=None)

        # Should only include files from test_dir
        paths = [file_info["path"] for file_info in file_list]
        assert any("test_dir/file1.txt" in path for path in paths)
        assert any("test_dir/file2.txt" in path for path in paths)
        assert not any("other_dir/file3.txt" in path for path in paths)

    @pytest.mark.asyncio
    async def test_compress_lz4(self, local_storage_service, sample_file_content):
        """Test LZ4 compression."""
        local_storage_service.compression_type = "lz4"

        compressed_content, is_compressed, compression_info = await local_storage_service._compress_lz4(
            sample_file_content
        )

        assert is_compressed
        assert compression_info["type"] == "lz4"
        assert len(compressed_content) < len(sample_file_content)

        # Test decompression
        decompressed_content = await local_storage_service._decompress_file(compressed_content, "")
        assert decompressed_content == sample_file_content

    @pytest.mark.asyncio
    async def test_create_organizational_links(self, local_storage_service, sample_file_content):
        """Test creation of organizational symbolic links."""
        file_hash = "a1b2c3d4e5f6789012345678901234567890abcd"
        filename = "test.pdf"
        stored_path = "a1/b2/a1b2c3d4e5f6789012345678901234567890abcd.pdf"

        # Create the actual file
        full_path = local_storage_service.storage_path / stored_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(sample_file_content)

        # Test organizational links creation
        await local_storage_service._create_organizational_links(
            file_hash, filename, stored_path, "ACME Corp", "2024-01-15"
        )

        # Check that links were created
        vendor_link = local_storage_service.storage_path / "by_vendor" / "ACME_Corp" / f"{file_hash}.pdf"
        date_link = local_storage_service.storage_path / "by_date" / "2024" / "01" / f"{file_hash}.pdf"

        assert vendor_link.exists()
        assert date_link.exists()

        # Verify links point to correct file
        assert vendor_link.resolve() == full_path.resolve()
        assert date_link.resolve() == full_path.resolve()