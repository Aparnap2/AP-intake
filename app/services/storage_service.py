"""
Enhanced storage service for document storage and retrieval with local backend support.
"""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import aiofiles
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import Request

from app.core.config import settings
from app.core.exceptions import StorageException
from app.services.local_storage_service import LocalStorageService

logger = logging.getLogger(__name__)


class StorageService:
    """Enhanced service for document storage and retrieval."""

    def __init__(self):
        """Initialize the storage service."""
        self.storage_type = settings.STORAGE_TYPE.lower()
        self.storage_path = settings.STORAGE_PATH

        # Initialize storage backend
        if self.storage_type == "s3":
            self._init_s3_client()
        elif self.storage_type == "local":
            self._init_local_storage()
        else:
            raise StorageException(f"Unsupported storage type: {self.storage_type}")

    def _init_s3_client(self):
        """Initialize S3 client."""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
                endpoint_url=settings.S3_ENDPOINT_URL,
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            logger.info(f"Initialized S3 storage with bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise StorageException(f"S3 initialization failed: {str(e)}")

    def _init_local_storage(self):
        """Initialize enhanced local file storage."""
        try:
            self.local_storage_service = LocalStorageService()
            logger.info(f"Initialized enhanced local storage at: {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to initialize local storage: {e}")
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
        """Store a file and return storage information with enhanced features."""
        logger.info(f"Storing file: {filename}")

        try:
            # Store file based on storage type
            if self.storage_type == "s3":
                # Generate file hash and unique path for S3
                file_hash = hashlib.sha256(file_content).hexdigest()
                file_path = self._generate_file_path(file_hash, filename)
                storage_info = await self._store_s3(file_content, file_path, content_type)

                # Return storage information for S3
                return {
                    "storage_type": self.storage_type,
                    "file_path": file_path,
                    "file_hash": file_hash,
                    "file_size": len(file_content),
                    "filename": filename,
                    "content_type": content_type,
                    "url": storage_info.get("url"),
                    "storage_metadata": storage_info,
                    "deduplicated": False,
                    "is_compressed": False,
                }

            else:  # local - use enhanced local storage service
                return await self.local_storage_service.store_file(
                    file_content=file_content,
                    filename=filename,
                    content_type=content_type,
                    user_id=user_id,
                    session_id=session_id,
                    request=request,
                    organization_path=organization_path,
                    vendor_name=vendor_name,
                    invoice_date=invoice_date
                )

        except Exception as e:
            logger.error(f"Failed to store file {filename}: {e}")
            raise StorageException(f"File storage failed: {str(e)}")

    async def get_file_content(
        self,
        file_path: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request: Optional[Request] = None
    ) -> bytes:
        """Retrieve file content with access control."""
        logger.debug(f"Retrieving file: {file_path}")

        try:
            if self.storage_type == "s3":
                return await self._get_s3_content(file_path)
            else:  # local - use enhanced local storage service
                return await self.local_storage_service.get_file_content(
                    file_path=file_path,
                    user_id=user_id,
                    session_id=session_id,
                    request=request
                )

        except Exception as e:
            logger.error(f"Failed to retrieve file {file_path}: {e}")
            raise StorageException(f"File retrieval failed: {str(e)}")

    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        logger.debug(f"Checking if file exists: {file_path}")

        try:
            if self.storage_type == "s3":
                return await self._s3_file_exists(file_path)
            else:  # local - use enhanced local storage service
                return await self.local_storage_service.file_exists(file_path)

        except Exception as e:
            logger.error(f"Failed to check file existence {file_path}: {e}")
            return False

    async def delete_file(
        self,
        file_path: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request: Optional[Request] = None,
        permanent: bool = False
    ) -> bool:
        """Delete a file with access control."""
        logger.info(f"Deleting file: {file_path}")

        try:
            if self.storage_type == "s3":
                return await self._delete_s3_file(file_path)
            else:  # local - use enhanced local storage service
                return await self.local_storage_service.delete_file(
                    file_path=file_path,
                    user_id=user_id,
                    session_id=session_id,
                    request=request,
                    permanent=permanent
                )

        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        user_id: Optional[str] = None,
        include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        """List files in storage with access control."""
        logger.debug(f"Listing files with prefix: {prefix}")

        try:
            if self.storage_type == "s3":
                return await self._list_s3_files(prefix, limit)
            else:  # local - use enhanced local storage service
                return await self.local_storage_service.list_files(
                    prefix=prefix,
                    limit=limit,
                    user_id=user_id,
                    include_archived=include_archived
                )

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def _generate_file_path(self, file_hash: str, filename: str) -> str:
        """Generate unique file path."""
        # Use hash-based directory structure
        prefix1 = file_hash[:2]
        prefix2 = file_hash[2:4]

        # Get file extension
        extension = Path(filename).suffix.lower()
        if not extension:
            extension = ".bin"  # Default extension

        return f"{prefix1}/{prefix2}/{file_hash}{extension}"

    async def _store_s3(
        self, file_content: bytes, file_path: str, content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store file in S3."""
        try:
            # Prepare S3 upload parameters
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            # Upload to S3
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=file_path,
                    Body=file_content,
                    **extra_args
                )
            )

            # Generate URL
            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{file_path}"
            if settings.S3_ENDPOINT_URL:
                # For custom S3 endpoints (like MinIO)
                url = f"{settings.S3_ENDPOINT_URL}/{self.bucket_name}/{file_path}"

            return {
                "url": url,
                "bucket": self.bucket_name,
                "key": file_path,
            }

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise StorageException(f"S3 upload failed: {str(e)}")

    async def _store_local(
        self, file_content: bytes, file_path: str, content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store file locally."""
        try:
            full_path = self.storage_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(file_content)

            return {
                "url": f"file://{full_path}",
                "path": str(full_path),
            }

        except Exception as e:
            logger.error(f"Local file storage failed: {e}")
            raise StorageException(f"Local file storage failed: {str(e)}")

    async def _get_s3_content(self, file_path: str) -> bytes:
        """Get file content from S3."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise StorageException(f"File not found in S3: {file_path}")
            raise StorageException(f"S3 retrieval failed: {str(e)}")

    async def _get_local_content(self, file_path: str) -> bytes:
        """Get file content from local storage."""
        try:
            full_path = self.storage_path / file_path
            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        except FileNotFoundError:
            raise StorageException(f"File not found locally: {file_path}")
        except Exception as e:
            raise StorageException(f"Local file retrieval failed: {str(e)}")

    async def _s3_file_exists(self, file_path: str) -> bool:
        """Check if file exists in S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
            )
            return True
        except ClientError:
            return False

    async def _local_file_exists(self, file_path: str) -> bool:
        """Check if file exists locally."""
        full_path = self.storage_path / file_path
        return full_path.exists()

    async def _delete_s3_file(self, file_path: str) -> bool:
        """Delete file from S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            )
            return True
        except ClientError as e:
            logger.error(f"S3 deletion failed: {e}")
            return False

    async def _delete_local_file(self, file_path: str) -> bool:
        """Delete file locally."""
        try:
            full_path = self.storage_path / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Local file deletion failed: {e}")
            return False

    async def _list_s3_files(self, prefix: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List files in S3."""
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            loop = asyncio.get_event_loop()

            pages = []
            if prefix:
                pages = await loop.run_in_executor(
                    None,
                    lambda: list(paginator.paginate(Bucket=self.bucket_name, Prefix=prefix))
                )
            else:
                pages = await loop.run_in_executor(
                    None,
                    lambda: list(paginator.paginate(Bucket=self.bucket_name))
                )

            files = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        files.append({
                            "path": obj["Key"],
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"].isoformat(),
                            "url": f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{obj['Key']}",
                        })
                        if len(files) >= limit:
                            return files

            return files

        except ClientError as e:
            logger.error(f"S3 list failed: {e}")
            return []

    async def _list_local_files(self, prefix: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List files locally."""
        try:
            files = []
            search_path = self.storage_path

            if prefix:
                search_path = self.storage_path / prefix

            for file_path in search_path.rglob("*"):
                if file_path.is_file():
                    stat = file_path.stat()
                    relative_path = file_path.relative_to(self.storage_path)
                    files.append({
                        "path": str(relative_path),
                        "size": stat.st_size,
                        "last_modified": stat.st_mtime,
                        "url": f"file://{file_path}",
                    })
                    if len(files) >= limit:
                        break

            return files

        except Exception as e:
            logger.error(f"Local file list failed: {e}")
            return []

    async def generate_presigned_url(self, file_path: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for file access (S3 only)."""
        if self.storage_type != "s3":
            return None

        try:
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None,
                lambda: self.s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": file_path},
                    ExpiresIn=expiration,
                )
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None