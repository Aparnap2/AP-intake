"""
Storage audit models for file access logging and audit trails.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, and_
from sqlalchemy.orm import relationship

from app.db.session import Base


class StorageAudit(Base):
    """Storage audit log for tracking file operations."""

    __tablename__ = "storage_audit"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(500), nullable=False, index=True)
    file_hash = Column(String(64), nullable=False, index=True)
    operation = Column(String(50), nullable=False)  # store, retrieve, delete, list, compress, decompress
    operation_status = Column(String(20), nullable=False)  # success, failure
    user_id = Column(String(100), nullable=True)  # System user or API user
    session_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    file_size = Column(Integer, nullable=True)
    content_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    audit_metadata = Column(Text, nullable=True)  # JSON metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_ms = Column(Integer, nullable=True)  # Operation duration in milliseconds

    # Indexes for common queries
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )


class FileDeduplication(Base):
    """File deduplication tracking."""

    __tablename__ = "file_deduplication"

    id = Column(Integer, primary_key=True, index=True)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False, unique=True)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=True)
    reference_count = Column(Integer, default=1, nullable=False)  # Number of files referencing this hash
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_accessed = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_compressed = Column(Boolean, default=False, nullable=False)
    compression_type = Column(String(20), nullable=True)  # gzip, lz4, etc.
    original_size = Column(Integer, nullable=True)  # Size before compression
    compressed_size = Column(Integer, nullable=True)  # Size after compression

    # Note: Logical relationship to StorageAudit via file_hash can be queried directly
    # since there's no foreign key constraint between these tables


class FileAccessControl(Base):
    """File access control and permissions."""

    __tablename__ = "file_access_control"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(500), nullable=False, index=True)
    file_hash = Column(String(64), nullable=False, index=True)
    access_level = Column(String(20), nullable=False, default="private")  # public, private, restricted
    allowed_users = Column(Text, nullable=True)  # JSON array of user IDs
    allowed_roles = Column(Text, nullable=True)  # JSON array of role names
    access_rules = Column(Text, nullable=True)  # JSON access rules
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)