"""
Unit tests for StorageService file handling and storage operations.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage_service import StorageService
from app.services.local_storage_service import LocalStorageService
from app.core.exceptions import StorageException


class TestStorageService:
    """Test suite for StorageService."""

    @pytest.fixture
    def storage_service(self) -> StorageService:
        """Create StorageService instance for testing."""
        return StorageService()

    @pytest.fixture
    def temp_file(self) -> Path:
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"test file content")
            temp_path = Path(temp.name)
        yield temp_path
        temp_path.unlink(missing_ok=True)

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_store_file_success(self, storage_service: StorageService, temp_file: Path):
        """Test successful file storage."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.store_file.return_value = "/stored/path/file.pdf"

            result = await storage_service.store_file(
                file_path=str(temp_file),
                filename="test_invoice.pdf",
                content_type="application/pdf"
            )

            assert result == "/stored/path/file.pdf"
            mock_backend.store_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_file_not_found(self, storage_service: StorageService):
        """Test file storage with non-existent file."""
        with pytest.raises(StorageException, match="File not found"):
            await storage_service.store_file(
                file_path="/nonexistent/file.pdf",
                filename="test.pdf"
            )

    @pytest.mark.asyncio
    async def test_store_file_with_content(self, storage_service: StorageService):
        """Test file storage with content bytes."""
        test_content = b"test file content"

        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.store_file_from_content.return_value = "/stored/path/file.pdf"

            result = await storage_service.store_file_from_content(
                content=test_content,
                filename="test_invoice.pdf",
                content_type="application/pdf"
            )

            assert result == "/stored/path/file.pdf"
            mock_backend.store_file_from_content.assert_called_once_with(
                test_content, "test_invoice.pdf", "application/pdf"
            )

    @pytest.mark.asyncio
    async def test_get_file_content_success(self, storage_service: StorageService, temp_file: Path):
        """Test successful file content retrieval."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            expected_content = temp_file.read_bytes()
            mock_backend.get_file_content.return_value = expected_content

            result = await storage_service.get_file_content(str(temp_file))

            assert result == expected_content
            mock_backend.get_file_content.assert_called_once_with(str(temp_file))

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, storage_service: StorageService):
        """Test file content retrieval with non-existent file."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.get_file_content.side_effect = FileNotFoundError("File not found")

            with pytest.raises(StorageException, match="File not found"):
                await storage_service.get_file_content("/nonexistent/file.pdf")

    @pytest.mark.asyncio
    async def test_file_exists_true(self, storage_service: StorageService):
        """Test file existence check - file exists."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.file_exists.return_value = True

            result = await storage_service.file_exists("/existing/file.pdf")

            assert result is True
            mock_backend.file_exists.assert_called_once_with("/existing/file.pdf")

    @pytest.mark.asyncio
    async def test_file_exists_false(self, storage_service: StorageService):
        """Test file existence check - file doesn't exist."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.file_exists.return_value = False

            result = await storage_service.file_exists("/nonexistent/file.pdf")

            assert result is False
            mock_backend.file_exists.assert_called_once_with("/nonexistent/file.pdf")

    @pytest.mark.asyncio
    async def test_delete_file_success(self, storage_service: StorageService):
        """Test successful file deletion."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.delete_file.return_value = True

            result = await storage_service.delete_file("/path/to/file.pdf")

            assert result is True
            mock_backend.delete_file.assert_called_once_with("/path/to/file.pdf")

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, storage_service: StorageService):
        """Test file deletion with non-existent file."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.delete_file.return_value = False

            result = await storage_service.delete_file("/nonexistent/file.pdf")

            assert result is False
            mock_backend.delete_file.assert_called_once_with("/nonexistent/file.pdf")

    @pytest.mark.asyncio
    async def test_list_files_success(self, storage_service: StorageService):
        """Test successful file listing."""
        expected_files = [
            {"name": "file1.pdf", "path": "/storage/file1.pdf", "size": 1024, "modified": "2024-01-15"},
            {"name": "file2.pdf", "path": "/storage/file2.pdf", "size": 2048, "modified": "2024-01-16"},
        ]

        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.list_files.return_value = expected_files

            result = await storage_service.list_files(prefix="invoices/")

            assert result == expected_files
            mock_backend.list_files.assert_called_once_with(prefix="invoices/")

    @pytest.mark.asyncio
    async def test_get_file_metadata_success(self, storage_service: StorageService):
        """Test successful file metadata retrieval."""
        expected_metadata = {
            "name": "test.pdf",
            "size": 1024,
            "content_type": "application/pdf",
            "created_at": "2024-01-15T10:00:00Z",
            "modified_at": "2024-01-15T10:30:00Z",
        }

        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.get_file_metadata.return_value = expected_metadata

            result = await storage_service.get_file_metadata("/path/to/test.pdf")

            assert result == expected_metadata
            mock_backend.get_file_metadata.assert_called_once_with("/path/to/test.pdf")

    @pytest.mark.asyncio
    async def test_copy_file_success(self, storage_service: StorageService):
        """Test successful file copy."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.copy_file.return_value = "/destination/copied_file.pdf"

            result = await storage_service.copy_file(
                source_path="/source/file.pdf",
                destination_path="/destination/copied_file.pdf"
            )

            assert result == "/destination/copied_file.pdf"
            mock_backend.copy_file.assert_called_once_with(
                "/source/file.pdf", "/destination/copied_file.pdf"
            )

    @pytest.mark.asyncio
    async def test_move_file_success(self, storage_service: StorageService):
        """Test successful file move."""
        with patch.object(storage_service, '_get_storage_backend') as mock_backend:
            mock_backend.move_file.return_value = "/new/location/moved_file.pdf"

            result = await storage_service.move_file(
                source_path="/source/file.pdf",
                destination_path="/new/location/moved_file.pdf"
            )

            assert result == "/new/location/moved_file.pdf"
            mock_backend.move_file.assert_called_once_with(
                "/source/file.pdf", "/new/location/moved_file.pdf"
            )

    def test_get_storage_backend_local(self, storage_service: StorageService):
        """Test getting local storage backend."""
        with patch.dict('app.core.config.settings.__dict__', {'STORAGE_TYPE': 'local'}):
            backend = storage_service._get_storage_backend()
            assert isinstance(backend, LocalStorageService)

    def test_get_storage_backend_s3(self, storage_service: StorageService):
        """Test getting S3 storage backend."""
        with patch.dict('app.core.config.settings.__dict__', {'STORAGE_TYPE': 's3'}):
            with patch('app.services.storage_service.S3StorageService') as mock_s3:
                mock_instance = MagicMock()
                mock_s3.return_value = mock_instance

                backend = storage_service._get_storage_backend()
                assert backend == mock_instance
                mock_s3.assert_called_once()

    def test_get_storage_backend_unsupported(self, storage_service: StorageService):
        """Test getting unsupported storage backend."""
        with patch.dict('app.core.config.settings.__dict__', {'STORAGE_TYPE': 'unsupported'}):
            with pytest.raises(StorageException, match="Unsupported storage type"):
                storage_service._get_storage_backend()


class TestLocalStorageService:
    """Test suite for LocalStorageService."""

    @pytest.fixture
    def local_storage_service(self, temp_dir: Path) -> LocalStorageService:
        """Create LocalStorageService instance for testing."""
        return LocalStorageService(base_path=str(temp_dir))

    @pytest.fixture
    def sample_file_content(self) -> bytes:
        """Sample file content for testing."""
        return b"Sample PDF content for testing storage operations"

    @pytest.mark.asyncio
    async def test_store_file_success(
        self, local_storage_service: LocalStorageService, temp_file: Path, sample_file_content: bytes
    ):
        """Test successful local file storage."""
        result = await local_storage_service.store_file(
            file_path=str(temp_file),
            filename="test_invoice.pdf",
            content_type="application/pdf"
        )

        expected_path = Path(local_storage_service.base_path) / "test_invoice.pdf"
        assert result == str(expected_path)
        assert expected_path.exists()
        assert expected_path.read_bytes() == sample_file_content

    @pytest.mark.asyncio
    async def test_store_file_from_content(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test storing file from content bytes."""
        result = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="content_test.pdf",
            content_type="application/pdf"
        )

        expected_path = Path(local_storage_service.base_path) / "content_test.pdf"
        assert result == str(expected_path)
        assert expected_path.exists()
        assert expected_path.read_bytes() == sample_file_content

    @pytest.mark.asyncio
    async def test_get_file_content(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test retrieving local file content."""
        # First store a file
        stored_path = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="retrieve_test.pdf",
            content_type="application/pdf"
        )

        # Then retrieve its content
        result = await local_storage_service.get_file_content(stored_path)

        assert result == sample_file_content

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, local_storage_service: LocalStorageService):
        """Test retrieving content of non-existent file."""
        non_existent_path = Path(local_storage_service.base_path) / "non_existent.pdf"

        with pytest.raises(StorageException, match="File not found"):
            await local_storage_service.get_file_content(str(non_existent_path))

    @pytest.mark.asyncio
    async def test_file_exists(self, local_storage_service: LocalStorageService, sample_file_content: bytes):
        """Test file existence check."""
        # Test non-existent file
        non_existent_path = Path(local_storage_service.base_path) / "non_existent.pdf"
        assert await local_storage_service.file_exists(str(non_existent_path)) is False

        # Store a file and test existence
        stored_path = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="existence_test.pdf",
            content_type="application/pdf"
        )
        assert await local_storage_service.file_exists(stored_path) is True

    @pytest.mark.asyncio
    async def test_delete_file(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test file deletion."""
        # Store a file
        stored_path = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="delete_test.pdf",
            content_type="application/pdf"
        )

        # Verify it exists
        assert Path(stored_path).exists()

        # Delete it
        result = await local_storage_service.delete_file(stored_path)

        assert result is True
        assert not Path(stored_path).exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, local_storage_service: LocalStorageService):
        """Test deleting non-existent file."""
        non_existent_path = Path(local_storage_service.base_path) / "non_existent.pdf"

        result = await local_storage_service.delete_file(str(non_existent_path))

        assert result is False

    @pytest.mark.asyncio
    async def test_list_files(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test file listing."""
        # Store multiple files
        await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="invoice1.pdf",
            content_type="application/pdf"
        )
        await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="invoice2.pdf",
            content_type="application/pdf"
        )
        await local_storage_service.store_file_from_content(
            content=b"different content",
            filename="report.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        # List all files
        all_files = await local_storage_service.list_files()
        assert len(all_files) == 3

        # List files with prefix
        pdf_files = await local_storage_service.list_files(prefix="invoice")
        assert len(pdf_files) == 2
        assert all(file["name"].startswith("invoice") for file in pdf_files)

        # Check file structure
        file_info = pdf_files[0]
        assert "name" in file_info
        assert "path" in file_info
        assert "size" in file_info
        assert "modified" in file_info

    @pytest.mark.asyncio
    async def test_get_file_metadata(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test file metadata retrieval."""
        # Store a file
        stored_path = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="metadata_test.pdf",
            content_type="application/pdf"
        )

        # Get metadata
        metadata = await local_storage_service.get_file_metadata(stored_path)

        assert metadata["name"] == "metadata_test.pdf"
        assert metadata["size"] == len(sample_file_content)
        assert metadata["content_type"] == "application/pdf"
        assert "created_at" in metadata
        assert "modified_at" in metadata

    @pytest.mark.asyncio
    async def test_copy_file(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test file copying."""
        # Store a source file
        source_path = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="source.pdf",
            content_type="application/pdf"
        )

        # Copy it
        destination_path = str(Path(local_storage_service.base_path) / "copied.pdf")
        result = await local_storage_service.copy_file(source_path, destination_path)

        assert result == destination_path
        assert Path(source_path).exists()
        assert Path(destination_path).exists()
        assert Path(destination_path).read_bytes() == sample_file_content

    @pytest.mark.asyncio
    async def test_copy_file_source_not_found(self, local_storage_service: LocalStorageService):
        """Test copying non-existent source file."""
        source_path = Path(local_storage_service.base_path) / "non_existent.pdf"
        destination_path = Path(local_storage_service.base_path) / "copy.pdf"

        with pytest.raises(StorageException, match="Source file not found"):
            await local_storage_service.copy_file(str(source_path), str(destination_path))

    @pytest.mark.asyncio
    async def test_move_file(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test file moving."""
        # Store a source file
        source_path = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename="move_source.pdf",
            content_type="application/pdf"
        )

        # Move it
        destination_path = str(Path(local_storage_service.base_path) / "moved.pdf")
        result = await local_storage_service.move_file(source_path, destination_path)

        assert result == destination_path
        assert not Path(source_path).exists()
        assert Path(destination_path).exists()
        assert Path(destination_path).read_bytes() == sample_file_content

    @pytest.mark.asyncio
    async def test_move_file_source_not_found(self, local_storage_service: LocalStorageService):
        """Test moving non-existent source file."""
        source_path = Path(local_storage_service.base_path) / "non_existent.pdf"
        destination_path = Path(local_storage_service.base_path) / "moved.pdf"

        with pytest.raises(StorageException, match="Source file not found"):
            await local_storage_service.move_file(str(source_path), str(destination_path))

    @pytest.mark.asyncio
    async def test_create_directory(self, local_storage_service: LocalStorageService):
        """Test directory creation."""
        new_dir_path = Path(local_storage_service.base_path) / "new_directory"

        assert not new_dir_path.exists()

        await local_storage_service.create_directory(str(new_dir_path))

        assert new_dir_path.exists()
        assert new_dir_path.is_dir()

    @pytest.mark.asyncio
    async def test_create_nested_directory(self, local_storage_service: LocalStorageService):
        """Test nested directory creation."""
        nested_dir_path = Path(local_storage_service.base_path) / "level1" / "level2" / "level3"

        assert not nested_dir_path.exists()

        await local_storage_service.create_directory(str(nested_dir_path))

        assert nested_dir_path.exists()
        assert nested_dir_path.is_dir()

    @pytest.mark.asyncio
    async def test_store_file_in_subdirectory(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test storing file in subdirectory."""
        # Create subdirectory first
        sub_dir = Path(local_storage_service.base_path) / "invoices" / "2024"
        await local_storage_service.create_directory(str(sub_dir))

        # Store file in subdirectory
        filename = "invoices/2024/test_invoice.pdf"
        result = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename=filename,
            content_type="application/pdf"
        )

        expected_path = Path(local_storage_service.base_path) / filename
        assert result == str(expected_path)
        assert expected_path.exists()
        assert expected_path.read_bytes() == sample_file_content

    def test_generate_unique_filename(self, local_storage_service: LocalStorageService):
        """Test unique filename generation."""
        base_name = "test_invoice.pdf"

        # Test first call
        unique1 = local_storage_service._generate_unique_filename(base_name)
        assert unique1 == base_name

        # Test when file exists
        existing_file = Path(local_storage_service.base_path) / base_name
        existing_file.touch()

        unique2 = local_storage_service._generate_unique_filename(base_name)
        assert unique2 != base_name
        assert unique2.startswith("test_invoice")
        assert unique2.endswith(".pdf")

        # Clean up
        existing_file.unlink()

    @pytest.mark.asyncio
    async def test_store_with_duplicate_filename(
        self, local_storage_service: LocalStorageService, sample_file_content: bytes
    ):
        """Test storing file with duplicate filename."""
        filename = "duplicate_test.pdf"

        # Store first file
        result1 = await local_storage_service.store_file_from_content(
            content=sample_file_content,
            filename=filename,
            content_type="application/pdf"
        )

        # Store second file with same name
        result2 = await local_storage_service.store_file_from_content(
            content=b"different content",
            filename=filename,
            content_type="application/pdf"
        )

        assert result1 != result2
        assert Path(result1).exists()
        assert Path(result2).exists()
        assert Path(result1).read_bytes() != Path(result2).read_bytes()

    @pytest.mark.asyncio
    async def test_storage_service_error_handling(self, local_storage_service: LocalStorageService):
        """Test error handling in storage operations."""
        # Test with invalid base path (read-only directory)
        readonly_dir = "/root/nonexistent"  # Likely doesn't exist or isn't writable
        readonly_service = LocalStorageService(base_path=readonly_dir)

        with pytest.raises(StorageException):
            await readonly_service.store_file_from_content(
                content=b"test content",
                filename="test.pdf"
            )

    @pytest.mark.asyncio
    async def test_file_size_validation(self, local_storage_service: LocalStorageService):
        """Test file size validation."""
        # Create large content (assuming there might be a size limit)
        large_content = b"x" * (100 * 1024 * 1024)  # 100MB

        # This should work for local storage (no size limit by default)
        result = await local_storage_service.store_file_from_content(
            content=large_content,
            filename="large_file.pdf",
            content_type="application/pdf"
        )

        assert result is not None
        assert Path(result).exists()
        assert Path(result).stat().st_size == len(large_content)

    @pytest.mark.asyncio
    async def test_file_type_validation(self, local_storage_service: LocalStorageService):
        """Test file type validation."""
        content = b"test content"

        # Test valid content type
        result = await local_storage_service.store_file_from_content(
            content=content,
            filename="test.pdf",
            content_type="application/pdf"
        )
        assert result is not None

        # Test with no content type (should still work)
        result = await local_storage_service.store_file_from_content(
            content=content,
            filename="test.txt"
        )
        assert result is not None