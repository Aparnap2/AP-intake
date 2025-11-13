"""
Signed URL service for secure file access with time-limited permissions.
"""

import asyncio
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse, urlunparse

from fastapi import Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.core.config import settings
from app.core.exceptions import SecurityException
from app.models.ingestion import SignedUrl, IngestionJob
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class SignedUrlService:
    """Service for generating and managing secure signed URLs."""

    def __init__(self):
        """Initialize the signed URL service."""
        self.storage_service = StorageService()
        self.secret_key = settings.SECRET_KEY or "default-secret-key"
        self.default_expiry_hours = 24
        self.max_expiry_hours = 168  # 7 days
        self.url_token_length = 32

    async def generate_signed_url(
        self,
        ingestion_job_id: str,
        db: AsyncSession,
        expiry_hours: Optional[int] = None,
        max_access_count: int = 1,
        allowed_ip_addresses: Optional[List[str]] = None,
        allowed_user_agents: Optional[List[str]] = None,
        created_for: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a secure signed URL for file access.

        Args:
            ingestion_job_id: UUID of the ingestion job
            db: Database session
            expiry_hours: Hours until URL expires (default: 24, max: 168)
            max_access_count: Maximum number of times URL can be used
            allowed_ip_addresses: List of allowed IP addresses
            allowed_user_agents: List of allowed user agent patterns
            created_for: User or purpose identifier
            custom_headers: Custom headers to include

        Returns:
            Dictionary with signed URL details
        """
        try:
            # Validate ingestion job
            job = await self._get_ingestion_job(ingestion_job_id, db)
            if not job:
                raise SecurityException(f"Ingestion job {ingestion_job_id} not found")

            # Validate file exists
            if not await self.storage_service.file_exists(job.storage_path):
                raise SecurityException(f"File not found: {job.storage_path}")

            # Validate and normalize expiry time
            expiry_hours = min(max(expiry_hours or self.default_expiry_hours, 1), self.max_expiry_hours)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)

            # Generate secure token
            url_token = await self._generate_secure_token()

            # Build signed URL based on storage backend
            if job.storage_backend == "s3":
                signed_url = await self._generate_s3_signed_url(job, expiry_hours * 3600)
            else:
                signed_url = await self._generate_local_signed_url(job, url_token, expires_at)

            # Create signed URL record
            signed_url_record = SignedUrl(
                ingestion_job_id=job.id,
                url_token=url_token,
                signed_url=signed_url,
                expires_at=expires_at,
                max_access_count=max_access_count,
                allowed_ip_addresses=allowed_ip_addresses,
                is_active=True,
                created_for=created_for,
            )

            db.add(signed_url_record)
            await db.commit()
            await db.refresh(signed_url_record)

            logger.info(f"Generated signed URL for job {ingestion_job_id}, expires {expires_at}")

            return {
                "signed_url_id": str(signed_url_record.id),
                "url": signed_url,
                "token": url_token,
                "expires_at": expires_at.isoformat(),
                "expiry_hours": expiry_hours,
                "max_access_count": max_access_count,
                "allowed_ip_addresses": allowed_ip_addresses,
                "filename": job.original_filename,
                "file_size": job.file_size_bytes,
                "mime_type": job.mime_type,
                "security_features": {
                    "token_length": len(url_token),
                    "url_expires": True,
                    "access_limited": max_access_count > 0,
                    "ip_restricted": len(allowed_ip_addresses or []) > 0,
                },
            }

        except Exception as e:
            logger.error(f"Failed to generate signed URL for job {ingestion_job_id}: {e}")
            raise SecurityException(f"Failed to generate signed URL: {str(e)}")

    async def validate_signed_url_access(
        self,
        url_token: str,
        request: Request,
        db: AsyncSession,
    ) -> Tuple[IngestionJob, SignedUrl]:
        """
        Validate signed URL access request.

        Args:
            url_token: URL token for validation
            request: FastAPI request object
            db: Database session

        Returns:
            Tuple of (ingestion_job, signed_url_record) if valid

        Raises:
            SecurityException: If validation fails
        """
        try:
            # Get signed URL record
            signed_url_record = await self._get_signed_url_record(url_token, db)
            if not signed_url_record:
                raise SecurityException("Invalid or expired signed URL token")

            # Check if URL is active
            if not signed_url_record.is_active:
                raise SecurityException("Signed URL has been revoked")

            # Check expiry
            if datetime.now(timezone.utc) > signed_url_record.expires_at:
                raise SecurityException("Signed URL has expired")

            # Check access count
            if signed_url_record.access_count >= signed_url_record.max_access_count:
                raise SecurityException("Signed URL access limit exceeded")

            # Check IP restrictions
            if signed_url_record.allowed_ip_addresses:
                client_ip = self._get_client_ip(request)
                if client_ip not in signed_url_record.allowed_ip_addresses:
                    logger.warning(f"Access denied for IP {client_ip} (not in allowed list)")
                    raise SecurityException("IP address not authorized")

            # Get ingestion job
            job = await self._get_ingestion_job(str(signed_url_record.ingestion_job_id), db)
            if not job:
                raise SecurityException("Associated ingestion job not found")

            # Update access tracking
            signed_url_record.access_count += 1
            signed_url_record.last_accessed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(f"Validated signed URL access for job {job.id} (access #{signed_url_record.access_count})")
            return job, signed_url_record

        except SecurityException:
            raise
        except Exception as e:
            logger.error(f"Signed URL validation failed: {e}")
            raise SecurityException(f"Access validation failed: {str(e)}")

    async def revoke_signed_url(
        self,
        signed_url_id: str,
        revoked_by: str,
        db: AsyncSession,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Revoke a signed URL.

        Args:
            signed_url_id: UUID of the signed URL record
            revoked_by: User or system revoking the URL
            reason: Reason for revocation
            db: Database session

        Returns:
            True if successfully revoked
        """
        try:
            # Get signed URL record
            result = await db.execute(
                select(SignedUrl).where(SignedUrl.id == signed_url_id)
            )
            signed_url_record = result.scalar_one_or_none()

            if not signed_url_record:
                raise SecurityException(f"Signed URL {signed_url_id} not found")

            # Revoke the URL
            signed_url_record.is_active = False
            signed_url_record.revoked_at = datetime.now(timezone.utc)
            signed_url_record.revoked_by = revoked_by

            await db.commit()

            logger.info(f"Revoked signed URL {signed_url_id} by {revoked_by}")
            if reason:
                logger.info(f"Revocation reason: {reason}")

            return True

        except SecurityException:
            raise
        except Exception as e:
            logger.error(f"Failed to revoke signed URL {signed_url_id}: {e}")
            await db.rollback()
            raise SecurityException(f"Failed to revoke signed URL: {str(e)}")

    async def cleanup_expired_urls(self, db: AsyncSession, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up expired signed URLs.

        Args:
            db: Database session
            dry_run: If True, only report what would be cleaned up

        Returns:
            Dictionary with cleanup statistics
        """
        try:
            # Find expired URLs
            cutoff_time = datetime.now(timezone.utc)
            query = select(SignedUrl).where(SignedUrl.expires_at <= cutoff_time)
            result = await db.execute(query)
            expired_urls = result.scalars().all()

            cleanup_stats = {
                "total_expired": len(expired_urls),
                "already_inactive": 0,
                "to_deactivate": 0,
                "cutoff_time": cutoff_time.isoformat(),
            }

            if not dry_run:
                for url_record in expired_urls:
                    if url_record.is_active:
                        url_record.is_active = False
                        cleanup_stats["to_deactivate"] += 1
                    else:
                        cleanup_stats["already_inactive"] += 1

                await db.commit()
                logger.info(f"Cleaned up {cleanup_stats['to_deactivate']} expired signed URLs")
            else:
                cleanup_stats["to_deactivate"] = len([u for u in expired_urls if u.is_active])
                cleanup_stats["already_inactive"] = len([u for u in expired_urls if not u.is_active])

            return cleanup_stats

        except Exception as e:
            logger.error(f"Failed to cleanup expired URLs: {e}")
            if not dry_run:
                await db.rollback()
            raise SecurityException(f"Cleanup failed: {str(e)}")

    async def get_url_access_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get access statistics for signed URLs within date range."""
        try:
            # Query signed URLs created in date range
            query = select(SignedUrl).where(
                and_(
                    SignedUrl.created_at >= start_date,
                    SignedUrl.created_at <= end_date,
                )
            )
            result = await db.execute(query)
            urls = result.scalars().all()

            # Calculate statistics
            total_urls = len(urls)
            accessed_urls = len([u for u in urls if u.access_count > 0])
            expired_urls = len([u for u in urls if u.expires_at <= datetime.now(timezone.utc)])
            revoked_urls = len([u for u in urls if u.revoked_at is not None])

            total_accesses = sum(u.access_count for u in urls)
            avg_accesses = total_accesses / total_urls if total_urls > 0 else 0

            # Group by creation purpose
            by_purpose = {}
            for url in urls:
                purpose = url.created_for or "unknown"
                if purpose not in by_purpose:
                    by_purpose[purpose] = {"count": 0, "accesses": 0}
                by_purpose[purpose]["count"] += 1
                by_purpose[purpose]["accesses"] += url.access_count

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "total_urls": total_urls,
                "accessed_urls": accessed_urls,
                "expired_urls": expired_urls,
                "revoked_urls": revoked_urls,
                "total_accesses": total_accesses,
                "avg_accesses_per_url": round(avg_accesses, 2),
                "access_rate": round(accessed_urls / total_urls * 100, 2) if total_urls > 0 else 0,
                "by_purpose": by_purpose,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get URL access statistics: {e}")
            raise SecurityException(f"Failed to get statistics: {str(e)}")

    async def _get_ingestion_job(self, job_id: str, db: AsyncSession) -> Optional[IngestionJob]:
        """Get ingestion job by ID."""
        try:
            from sqlalchemy.orm import selectinload
            import uuid

            job_uuid = uuid.UUID(job_id)
            result = await db.execute(
                select(IngestionJob).where(IngestionJob.id == job_uuid)
            )
            return result.scalar_one_or_none()

        except ValueError:
            logger.warning(f"Invalid job ID format: {job_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get ingestion job {job_id}: {e}")
            return None

    async def _get_signed_url_record(self, url_token: str, db: AsyncSession) -> Optional[SignedUrl]:
        """Get signed URL record by token."""
        try:
            result = await db.execute(
                select(SignedUrl).where(
                    and_(
                        SignedUrl.url_token == url_token,
                        SignedUrl.is_active == True,
                    )
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get signed URL record for token {url_token}: {e}")
            return None

    async def _generate_secure_token(self) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(self.url_token_length)

    async def _generate_s3_signed_url(self, job: IngestionJob, expiry_seconds: int) -> str:
        """Generate S3 presigned URL."""
        try:
            return await self.storage_service.generate_presigned_url(
                job.storage_path, expiry_seconds
            )
        except Exception as e:
            logger.error(f"Failed to generate S3 signed URL: {e}")
            raise SecurityException(f"S3 signed URL generation failed: {str(e)}")

    async def _generate_local_signed_url(
        self, job: IngestionJob, url_token: str, expires_at: datetime
    ) -> str:
        """Generate local signed URL with authentication parameters."""
        try:
            base_url = settings.BASE_URL or "http://localhost:8000"

            # Create URL with authentication parameters
            params = {
                "token": url_token,
                "expires": int(expires_at.timestamp()),
                "job_id": str(job.id),
            }

            # Add signature for additional security
            signature = self._generate_url_signature(params)
            params["signature"] = signature

            url_path = f"/api/v1/ingestion/files/{url_token}"
            url_parts = urlparse(base_url)
            query_string = urlencode(params)

            signed_url = urlunparse((
                url_parts.scheme,
                url_parts.netloc,
                url_path,
                "",
                query_string,
                ""
            ))

            return signed_url

        except Exception as e:
            logger.error(f"Failed to generate local signed URL: {e}")
            raise SecurityException(f"Local signed URL generation failed: {str(e)}")

    def _generate_url_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC signature for URL parameters."""
        try:
            # Create a normalized parameter string
            sorted_params = sorted(params.items(), key=lambda x: x[0])
            param_string = "&".join(f"{k}={v}" for k, v in sorted_params)

            # Generate HMAC signature
            signature = hmac.new(
                self.secret_key.encode(),
                param_string.encode(),
                hashlib.sha256
            ).hexdigest()

            return signature

        except Exception as e:
            logger.error(f"Failed to generate URL signature: {e}")
            raise SecurityException(f"Signature generation failed: {str(e)}")

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded IP addresses
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fallback to client host
        return request.client.host if request.client else "unknown"

    async def generate_batch_signed_urls(
        self,
        ingestion_job_ids: List[str],
        db: AsyncSession,
        expiry_hours: Optional[int] = None,
        max_access_count: int = 1,
        created_for: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate signed URLs for multiple ingestion jobs."""
        results = []

        for job_id in ingestion_job_ids:
            try:
                signed_url_info = await self.generate_signed_url(
                    ingestion_job_id=job_id,
                    db=db,
                    expiry_hours=expiry_hours,
                    max_access_count=max_access_count,
                    created_for=created_for,
                )
                results.append({
                    "job_id": job_id,
                    "success": True,
                    "signed_url": signed_url_info,
                })

            except Exception as e:
                logger.error(f"Failed to generate signed URL for job {job_id}: {e}")
                results.append({
                    "job_id": job_id,
                    "success": False,
                    "error": str(e),
                })

        return results

    async def validate_url_signature(self, params: Dict[str, Any], signature: str) -> bool:
        """Validate URL signature to prevent tampering."""
        try:
            expected_signature = self._generate_url_signature(params)
            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(f"Failed to validate URL signature: {e}")
            return False