"""
Database models for the AP Intake & Validation system.
"""

from .invoice import (
    Invoice,
    InvoiceExtraction,
    Validation,
    Exception,
    StagedExport,
)
from .reference import Vendor, PurchaseOrder, GoodsReceiptNote
from .storage_audit import StorageAudit, FileDeduplication, FileAccessControl
# Temporarily commented out email models to fix SQLAlchemy relationship error
# from .email import (
#     Email,
#     EmailAttachment,
#     EmailProcessingLog,
#     EmailCredentials,
#     EmailMonitoringConfig,
#     EmailSecurityRule,
#     EmailProvider,
#     EmailStatus,
#     EmailSecurityFlag,
# )
from .user import (
    User,
    UserSession,
    ApiKey,
    UserRole,
    UserStatus,
)

__all__ = [
    "Invoice",
    "InvoiceExtraction",
    "Validation",
    "Exception",
    "StagedExport",
    "Vendor",
    "PurchaseOrder",
    "GoodsReceiptNote",
    "StorageAudit",
    "FileDeduplication",
    "FileAccessControl",
    # Email models temporarily commented out
    # "Email",
    # "EmailAttachment",
    # "EmailProcessingLog",
    # "EmailCredentials",
    # "EmailMonitoringConfig",
    # "EmailSecurityRule",
    # "EmailProvider",
    # "EmailStatus",
    # "EmailSecurityFlag",
    # User models
    "User",
    "UserSession",
    "ApiKey",
    "UserRole",
    "UserStatus",
]