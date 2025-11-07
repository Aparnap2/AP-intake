"""
Enhanced local storage service with compression, deduplication, and audit logging.
"""

import asyncio
import gzip
import hashlib
import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import lz4.frame
from fastapi import Request

from app.core.config import settings
from app.core.exceptions import StorageException
from app.db.session import AsyncSessionLocal
from app.models.storage_audit import FileAccessControl, FileDeduplication, StorageAudit

logger = logging.getLogger(__name__)


class LocalStorageService:
    """Enhanced local storage service with compression, deduplication, and audit logging."""

    def __init__(self):
        """Initialize the local storage service."""
        self.storage_path = Path(settings.STORAGE_PATH)
        self.compression_enabled = getattr(settings, 'STORAGE_COMPRESSION_ENABLED', True)
        self.compression_type = getattr(settings, 'STORAGE_COMPRESSION_TYPE', 'gzip')  # gzip, lz4, none
        self.compression_threshold = getattr(settings, 'STORAGE_COMPRESSION_THRESHOLD', 1024)  # bytes

        # Initialize storage directories
        self._init_storage_directories()

    def _init_storage_directories(self):
        """Initialize storage directory structure."""
        try:
            # Create base storage directories
            directories = [
                self.storage_path,
                self.storage_path / "originals",
                self.storage_path / "processed",
                self.storage_path / "compressed",
                self.storage_path / "temp",
                self.storage_path / "archive",
                self.storage_path / "by_date",
                self.storage_path / "by_vendor",
                self.storage_path / "by_type",
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)

            logger.info(f"Initialized local storage at: {self.storage_path}")

        except Exception as e:
            logger.error(f"Failed to initialize local storage directories: {e}")
            raise StorageException(f"Local storage initialization failed: {str(e)}")

    async def store_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request: Optional[Request] = None,
        organization_path: Optional[str] = None,
        vendor_name: Optional[str] = None,
        invoice_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store a file with compression, deduplication, and audit logging."""
        operation_start = time.time()

        try:
            # Generate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()
            file_size = len(file_content)

            # Check for existing file using deduplication
            deduplication_info = await self._check_deduplication(file_hash, filename)

            if deduplication_info:
                # File already exists, update reference count
                await self._update_reference_count(file_hash)

                # Log access
                await self._log_storage_operation(
                    file_path=deduplication_info["stored_path"],
                    file_hash=file_hash,
                    operation="store",
                    operation_status="success",
                    user_id=user_id,
                    session_id=session_id,
                    request=request,
                    file_size=file_size,
                    content_type=content_type,
                    duration_ms=int((time.time() - operation_start) * 1000),
                    metadata=json.dumps({"deduplicated": True, "original_filename": filename})
                )

                return {
                    "storage_type": "local",
                    "file_path": deduplication_info["stored_path"],
                    "file_hash": file_hash,
                    "file_size": file_size,
                    "filename": filename,
                    "content_type": content_type,
                    "url": f"file://{self.storage_path / deduplication_info['stored_path']}",
                    "deduplicated": True,
                    "is_compressed": deduplication_info.get("is_compressed", False),
                    "original_size": deduplication_info.get("original_size", file_size),
                    "compressed_size": deduplication_info.get("compressed_size", file_size),
                }

            # Generate file path with organization
            file_path = self._generate_organized_file_path(
                file_hash, filename, organization_path, vendor_name, invoice_date
            )

            # Compress file if enabled and meets threshold
            compressed_content, is_compressed, compression_info = await self._compress_file(
                file_content, content_type
            )

            # Store the file
            final_content = compressed_content if is_compressed else file_content
            stored_path = file_path if not is_compressed else f"compressed/{file_path}"
            full_path = self.storage_path / stored_path

            # Write file
            await self._write_file_async(full_path, final_content)

            # Store in originals directory as backup
            original_path = self.storage_path / "originals" / file_path
            await self._write_file_async(original_path, file_content)

            # Save deduplication record
            await self._save_deduplication_record(
                file_hash=file_hash,
                original_filename=filename,
                stored_path=stored_path,
                file_size=file_size,
                content_type=content_type,
                is_compressed=is_compressed,
                compression_info=compression_info
            )

            # Set up file access control
            await self._set_file_access_control(
                file_path=stored_path,
                file_hash=file_hash,
                access_level="private",
                created_by=user_id
            )

            # Log successful operation
            await self._log_storage_operation(
                file_path=stored_path,
                file_hash=file_hash,
                operation="store",
                operation_status="success",
                user_id=user_id,
                session_id=session_id,
                request=request,
                file_size=file_size,
                content_type=content_type,
                duration_ms=int((time.time() - operation_start) * 1000),
                metadata=json.dumps({
                    "compression": compression_info,
                    "original_filename": filename,
                    "organization_path": organization_path,
                    "vendor_name": vendor_name,
                    "invoice_date": invoice_date
                })
            )

            # Create additional organizational links
            await self._create_organizational_links(
                file_hash, filename, stored_path, vendor_name, invoice_date
            )

            return {
                "storage_type": "local",
                "file_path": stored_path,
                "file_hash": file_hash,
                "file_size": file_size,
                "filename": filename,
                "content_type": content_type,
                "url": f"file://{full_path}",
                "deduplicated": False,
                "is_compressed": is_compressed,
                "compression_type": compression_info.get("type") if compression_info else None,
                "original_size": compression_info.get("original_size", file_size) if compression_info else file_size,
                "compressed_size": compression_info.get("compressed_size", len(final_content)) if compression_info else file_size,
                "compression_ratio": compression_info.get("ratio", 0) if compression_info else 0,
            }

        except Exception as e:
            # Log failed operation
            await self._log_storage_operation(
                file_path="",
                file_hash="",
                operation="store",
                operation_status="failure",
                user_id=user_id,
                session_id=session_id,
                request=request,
                file_size=len(file_content) if file_content else 0,
                content_type=content_type,
                duration_ms=int((time.time() - operation_start) * 1000),
                error_message=str(e),
                metadata=json.dumps({"original_filename": filename})
            )

            logger.error(f"Failed to store file {filename}: {e}")
            raise StorageException(f"File storage failed: {str(e)}")

    async def get_file_content(
        self,
        file_path: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request: Optional[Request] = None
    ) -> bytes:
        """Retrieve file content with access control and audit logging."""
        operation_start = time.time()

        try:
            # Check access permissions
            if not await self._check_file_access(file_path, user_id):
                raise StorageException(f"Access denied for file: {file_path}")

            full_path = self.storage_path / file_path

            if not full_path.exists():
                raise StorageException(f"File not found: {file_path}")

            # Check if file is compressed
            is_compressed = file_path.startswith("compressed/")
            content = await self._read_file_async(full_path)

            # Decompress if necessary
            if is_compressed:
                content = await self._decompress_file(content, file_path)

            # Update access time in deduplication record
            file_hash = await self._get_file_hash_from_path(file_path)
            if file_hash:
                await self._update_access_time(file_hash)

            # Log successful operation
            await self._log_storage_operation(
                file_path=file_path,
                file_hash=file_hash or "",
                operation="retrieve",
                operation_status="success",
                user_id=user_id,
                session_id=session_id,
                request=request,
                file_size=len(content),
                duration_ms=int((time.time() - operation_start) * 1000)
            )

            return content

        except Exception as e:
            # Log failed operation
            await self._log_storage_operation(
                file_path=file_path,
                file_hash="",
                operation="retrieve",
                operation_status="failure",
                user_id=user_id,
                session_id=session_id,
                request=request,
                error_message=str(e),
                duration_ms=int((time.time() - operation_start) * 1000)
            )

            logger.error(f"Failed to retrieve file {file_path}: {e}")
            raise StorageException(f"File retrieval failed: {str(e)}")

    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        full_path = self.storage_path / file_path
        return full_path.exists()

    async def delete_file(
        self,
        file_path: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request: Optional[Request] = None,
        permanent: bool = False
    ) -> bool:
        """Delete a file with audit logging."""
        operation_start = time.time()

        try:
            # Check access permissions
            if not await self._check_file_access(file_path, user_id, require_delete=True):
                raise StorageException(f"Access denied for file deletion: {file_path}")

            full_path = self.storage_path / file_path

            if not full_path.exists():
                return False

            # Get file hash for audit
            file_hash = await self._get_file_hash_from_path(file_path)

            if permanent:
                # Permanent deletion
                full_path.unlink()

                # Update deduplication record
                if file_hash:
                    await self._decrement_reference_count(file_hash)

                # Delete access control record
                await self._delete_access_control(file_path)

                # Log permanent deletion
                await self._log_storage_operation(
                    file_path=file_path,
                    file_hash=file_hash or "",
                    operation="delete",
                    operation_status="success",
                    user_id=user_id,
                    session_id=session_id,
                    request=request,
                    duration_ms=int((time.time() - operation_start) * 1000),
                    metadata=json.dumps({"permanent": True})
                )

            else:
                # Move to archive
                archive_path = self.storage_path / "archive" / file_path
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(full_path), str(archive_path))

                # Log archival
                await self._log_storage_operation(
                    file_path=file_path,
                    file_hash=file_hash or "",
                    operation="archive",
                    operation_status="success",
                    user_id=user_id,
                    session_id=session_id,
                    request=request,
                    duration_ms=int((time.time() - operation_start) * 1000),
                    metadata=json.dumps({"permanent": False})
                )

            return True

        except Exception as e:
            # Log failed operation
            await self._log_storage_operation(
                file_path=file_path,
                file_hash="",
                operation="delete" if permanent else "archive",
                operation_status="failure",
                user_id=user_id,
                session_id=session_id,
                request=request,
                error_message=str(e),
                duration_ms=int((time.time() - operation_start) * 1000)
            )

            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        user_id: Optional[str] = None,
        include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        """List files with access control filtering."""
        try:
            files = []
            search_path = self.storage_path

            if prefix:
                search_path = self.storage_path / prefix

            # Define directories to search
            search_dirs = [search_path]
            if include_archived:
                search_dirs.append(self.storage_path / "archive")

            for search_dir in search_dirs:
                for file_path in search_dir.rglob("*"):
                    if file_path.is_file():
                        # Check access permissions
                        relative_path = file_path.relative_to(self.storage_path)
                        if not await self._check_file_access(str(relative_path), user_id):
                            continue

                        stat = file_path.stat()
                        files.append({
                            "path": str(relative_path),
                            "size": stat.st_size,
                            "last_modified": stat.st_mtime,
                            "url": f"file://{file_path}",
                            "is_archived": "archive" in str(relative_path),
                        })

                        if len(files) >= limit:
                            break

                if len(files) >= limit:
                    break

            return files

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def _generate_organized_file_path(
        self,
        file_hash: str,
        filename: str,
        organization_path: Optional[str] = None,
        vendor_name: Optional[str] = None,
        invoice_date: Optional[str] = None
    ) -> str:
        """Generate organized file path based on various criteria."""
        # Use hash-based directory structure for deduplication
        prefix1 = file_hash[:2]
        prefix2 = file_hash[2:4]

        # Get file extension
        extension = Path(filename).suffix.lower()
        if not extension:
            extension = ".bin"  # Default extension

        base_path = f"{prefix1}/{prefix2}/{file_hash}{extension}"

        # If organization path is provided, use it
        if organization_path:
            return f"{organization_path}/{base_path}"

        # Otherwise, use date-based organization
        if invoice_date:
            try:
                # Parse date and create year/month structure
                date_obj = datetime.strptime(invoice_date, "%Y-%m-%d")
                return f"by_date/{date_obj.year}/{date_obj.month:02d}/{base_path}"
            except ValueError:
                pass  # Fall back to default structure

        # Use vendor-based organization if available
        if vendor_name:
            clean_vendor = "".join(c for c in vendor_name if c.isalnum() or c in (' ', '-', '_')).strip()
            clean_vendor = clean_vendor.replace(' ', '_')
            return f"by_vendor/{clean_vendor}/{base_path}"

        # Default organization by file type
        file_type_dir = "by_type"
        if extension == ".pdf":
            file_type_dir = "pdfs"
        elif extension in [".jpg", ".jpeg", ".png"]:
            file_type_dir = "images"
        elif extension in [".doc", ".docx"]:
            file_type_dir = "documents"

        return f"{file_type_dir}/{base_path}"

    async def _compress_file(
        self, file_content: bytes, content_type: Optional[str] = None
    ) -> Tuple[bytes, bool, Optional[Dict[str, Any]]]:
        """Compress file content if enabled and beneficial."""
        if not self.compression_enabled or len(file_content) < self.compression_threshold:
            return file_content, False, None

        # Don't compress already compressed files
        if content_type:
            skip_types = [
                "application/zip", "application/gzip", "application/x-gzip",
                "application/x-lz4", "application/x-7z-compressed",
                "application/x-rar-compressed", "image/jpeg", "image/png"
            ]
            if any(skip_type in content_type.lower() for skip_type in skip_types):
                return file_content, False, None

        try:
            if self.compression_type == "gzip":
                compressed_content = await self._compress_gzip(file_content)
            elif self.compression_type == "lz4":
                compressed_content = await self._compress_lz4(file_content)
            else:
                return file_content, False, None

            compression_ratio = (len(file_content) - len(compressed_content)) / len(file_content)

            # Only use compression if it's beneficial (at least 10% reduction)
            if compression_ratio > 0.1:
                return compressed_content, True, {
                    "type": self.compression_type,
                    "original_size": len(file_content),
                    "compressed_size": len(compressed_content),
                    "ratio": compression_ratio
                }

            return file_content, False, None

        except Exception as e:
            logger.warning(f"Compression failed: {e}")
            return file_content, False, None

    async def _compress_gzip(self, content: bytes) -> bytes:
        """Compress content using gzip."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: gzip.compress(content))

    async def _compress_lz4(self, content: bytes) -> bytes:
        """Compress content using LZ4."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: lz4.frame.compress(content))

    async def _decompress_file(self, content: bytes, file_path: str) -> bytes:
        """Decompress file content based on compression type."""
        try:
            if self.compression_type == "gzip":
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: gzip.decompress(content))
            elif self.compression_type == "lz4":
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: lz4.frame.decompress(content))
            else:
                return content
        except Exception as e:
            logger.error(f"Decompression failed for {file_path}: {e}")
            raise StorageException(f"Decompression failed: {str(e)}")

    async def _write_file_async(self, file_path: Path, content: bytes):
        """Write file content asynchronously."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

    async def _read_file_async(self, file_path: Path) -> bytes:
        """Read file content asynchronously."""
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def _create_organizational_links(
        self,
        file_hash: str,
        filename: str,
        stored_path: str,
        vendor_name: Optional[str],
        invoice_date: Optional[str]
    ):
        """Create symbolic links or references for alternative organization."""
        try:
            # Create date-based link if invoice date is available
            if invoice_date:
                try:
                    date_obj = datetime.strptime(invoice_date, "%Y-%m-%d")
                    date_link_path = self.storage_path / "by_date" / str(date_obj.year) / f"{date_obj.month:02d}" / f"{file_hash}{Path(filename).suffix}"
                    original_path = self.storage_path / stored_path

                    # Create parent directory
                    date_link_path.parent.mkdir(parents=True, exist_ok=True)

                    # Create symbolic link if it doesn't exist
                    if not date_link_path.exists():
                        date_link_path.symlink_to(original_path.resolve())

                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to create date link for {file_hash}: {e}")

            # Create vendor-based link if vendor name is available
            if vendor_name:
                try:
                    clean_vendor = "".join(c for c in vendor_name if c.isalnum() or c in (' ', '-', '_')).strip()
                    clean_vendor = clean_vendor.replace(' ', '_')
                    vendor_link_path = self.storage_path / "by_vendor" / clean_vendor / f"{file_hash}{Path(filename).suffix}"
                    original_path = self.storage_path / stored_path

                    # Create parent directory
                    vendor_link_path.parent.mkdir(parents=True, exist_ok=True)

                    # Create symbolic link if it doesn't exist
                    if not vendor_link_path.exists():
                        vendor_link_path.symlink_to(original_path.resolve())

                except OSError as e:
                    logger.warning(f"Failed to create vendor link for {file_hash}: {e}")

        except Exception as e:
            logger.warning(f"Failed to create organizational links for {file_hash}: {e}")

    async def _check_deduplication(self, file_hash: str, filename: str) -> Optional[Dict[str, Any]]:
        """Check if file already exists using deduplication."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(FileDeduplication).where(FileDeduplication.file_hash == file_hash)
                )
                dedup_record = result.scalar_one_or_none()

                if dedup_record:
                    return {
                        "stored_path": dedup_record.stored_path,
                        "is_compressed": dedup_record.is_compressed,
                        "original_size": dedup_record.original_size,
                        "compressed_size": dedup_record.compressed_size,
                    }

                return None

        except Exception as e:
            logger.error(f"Failed to check deduplication for {file_hash}: {e}")
            return None

    async def _save_deduplication_record(
        self,
        file_hash: str,
        original_filename: str,
        stored_path: str,
        file_size: int,
        content_type: Optional[str],
        is_compressed: bool,
        compression_info: Optional[Dict[str, Any]]
    ):
        """Save deduplication record to database."""
        try:
            async with AsyncSessionLocal() as session:
                dedup_record = FileDeduplication(
                    file_hash=file_hash,
                    original_filename=original_filename,
                    stored_path=stored_path,
                    file_size=file_size,
                    content_type=content_type,
                    reference_count=1,
                    is_compressed=is_compressed,
                    compression_type=self.compression_type if is_compressed else None,
                    original_size=compression_info.get("original_size") if compression_info else file_size,
                    compressed_size=compression_info.get("compressed_size") if compression_info else file_size,
                )

                session.add(dedup_record)
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to save deduplication record for {file_hash}: {e}")

    async def _update_reference_count(self, file_hash: str, increment: bool = True):
        """Update reference count for deduplicated file."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select, update

                result = await session.execute(
                    select(FileDeduplication).where(FileDeduplication.file_hash == file_hash)
                )
                dedup_record = result.scalar_one_or_none()

                if dedup_record:
                    if increment:
                        dedup_record.reference_count += 1
                    else:
                        dedup_record.reference_count = max(0, dedup_record.reference_count - 1)

                    dedup_record.last_accessed = datetime.utcnow()
                    await session.commit()

        except Exception as e:
            logger.error(f"Failed to update reference count for {file_hash}: {e}")

    async def _decrement_reference_count(self, file_hash: str):
        """Decrement reference count and potentially delete deduplication record."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(FileDeduplication).where(FileDeduplication.file_hash == file_hash)
                )
                dedup_record = result.scalar_one_or_none()

                if dedup_record:
                    dedup_record.reference_count = max(0, dedup_record.reference_count - 1)

                    # Delete record if no more references
                    if dedup_record.reference_count <= 0:
                        await session.delete(dedup_record)

                    await session.commit()

        except Exception as e:
            logger.error(f"Failed to decrement reference count for {file_hash}: {e}")

    async def _update_access_time(self, file_hash: str):
        """Update last accessed time for deduplication record."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select, update

                result = await session.execute(
                    select(FileDeduplication).where(FileDeduplication.file_hash == file_hash)
                )
                dedup_record = result.scalar_one_or_none()

                if dedup_record:
                    dedup_record.last_accessed = datetime.utcnow()
                    await session.commit()

        except Exception as e:
            logger.error(f"Failed to update access time for {file_hash}: {e}")

    async def _get_file_hash_from_path(self, file_path: str) -> Optional[str]:
        """Get file hash from deduplication record using file path."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(FileDeduplication).where(FileDeduplication.stored_path == file_path)
                )
                dedup_record = result.scalar_one_or_none()

                return dedup_record.file_hash if dedup_record else None

        except Exception as e:
            logger.error(f"Failed to get file hash from path {file_path}: {e}")
            return None

    async def _set_file_access_control(
        self,
        file_path: str,
        file_hash: str,
        access_level: str = "private",
        created_by: Optional[str] = None
    ):
        """Set access control for a file."""
        try:
            async with AsyncSessionLocal() as session:
                access_control = FileAccessControl(
                    file_path=file_path,
                    file_hash=file_hash,
                    access_level=access_level,
                    created_by=created_by
                )

                session.add(access_control)
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to set access control for {file_path}: {e}")

    async def _check_file_access(
        self,
        file_path: str,
        user_id: Optional[str] = None,
        require_delete: bool = False
    ) -> bool:
        """Check if user has access to file."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(FileAccessControl).where(FileAccessControl.file_path == file_path)
                )
                access_control = result.scalar_one_or_none()

                if not access_control:
                    # Default access if no control record exists
                    return True

                # Check if access has expired
                if access_control.expires_at and access_control.expires_at < datetime.utcnow():
                    return False

                # Check access level
                if access_control.access_level == "public":
                    return True

                if access_control.access_level == "private":
                    # Only creator can access
                    return access_control.created_by == user_id

                if access_control.access_level == "restricted":
                    # Check if user is in allowed users/roles
                    if user_id and access_control.allowed_users:
                        allowed_users = json.loads(access_control.allowed_users)
                        if user_id in allowed_users:
                            return True

                    # Add role-based checking here if needed

                return require_delete and access_control.created_by == user_id

        except Exception as e:
            logger.error(f"Failed to check file access for {file_path}: {e}")
            return False  # Deny access on error

    async def _delete_access_control(self, file_path: str):
        """Delete access control record for a file."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import delete

                await session.execute(
                    delete(FileAccessControl).where(FileAccessControl.file_path == file_path)
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to delete access control for {file_path}: {e}")

    async def _log_storage_operation(
        self,
        file_path: str,
        file_hash: str,
        operation: str,
        operation_status: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request: Optional[Request] = None,
        file_size: Optional[int] = None,
        content_type: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[str] = None,
        duration_ms: Optional[int] = None
    ):
        """Log storage operation for audit trail."""
        try:
            async with AsyncSessionLocal() as session:
                audit_log = StorageAudit(
                    file_path=file_path,
                    file_hash=file_hash,
                    operation=operation,
                    operation_status=operation_status,
                    user_id=user_id,
                    session_id=session_id,
                    ip_address=request.client.host if request else None,
                    user_agent=request.headers.get("user-agent") if request else None,
                    file_size=file_size,
                    content_type=content_type,
                    error_message=error_message,
                    metadata=metadata,
                    duration_ms=duration_ms
                )

                session.add(audit_log)
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to log storage operation: {e}")