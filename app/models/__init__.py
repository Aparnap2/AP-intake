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
from .dlq import (
    DeadLetterQueue,
)
from .reference import Vendor, PurchaseOrder, GoodsReceiptNote
from .ar_invoice import (
    Customer,
    ARInvoice,
    PaymentStatus,
    CollectionPriority,
)
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
from .metrics import (
    SLODefinition,
    SLIMeasurement,
    SLOAlert,
    InvoiceMetric,
    SystemMetric,
    MetricsConfiguration,
)

__all__ = [
    "Invoice",
    "InvoiceExtraction",
    "Validation",
    "Exception",
    "StagedExport",
    "DeadLetterQueue",
    "Vendor",
    "PurchaseOrder",
    "GoodsReceiptNote",
    "Customer",
    "ARInvoice",
    "PaymentStatus",
    "CollectionPriority",
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
    # Metrics and SLO models
    "SLODefinition",
    "SLIMeasurement",
    "SLOAlert",
    "InvoiceMetric",
    "SystemMetric",
    "MetricsConfiguration",
]