"""
ERP adapter service for integrating with various ERP systems.
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import aiohttp
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ERPException, ValidationException

logger = logging.getLogger(__name__)


class ERPSystemType(str, Enum):
    """Supported ERP system types."""
    QUICKBOOKS = "quickbooks"
    SAP = "sap"
    NETSUITE = "netsuite"
    XERO = "xero"
    SAGE = "sage"
    ORACLE = "oracle"
    GENERIC = "generic"


class ERPEnvironment(str, Enum):
    """ERP environment types."""
    SANDBOX = "sandbox"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class ERPAction(str, Enum):
    """ERP actions for invoice processing."""
    CREATE_VENDOR_BILL = "create_vendor_bill"
    CREATE_INVOICE = "create_invoice"
    UPDATE_VENDOR = "update_vendor"
    CREATE_PAYMENT = "create_payment"
    SYNC_CHART_OF_ACCOUNTS = "sync_chart_of_accounts"
    TEST_CONNECTION = "test_connection"


@dataclass
class ERPConnection:
    """ERP connection configuration."""
    system_type: ERPSystemType
    environment: ERPEnvironment
    connection_config: Dict[str, Any]
    credentials: Dict[str, Any]
    is_active: bool = True
    last_tested: Optional[datetime] = None


@dataclass
class ERPTransaction:
    """ERP transaction data."""
    transaction_id: str
    transaction_type: str
    status: str
    data: Dict[str, Any]
    external_id: Optional[str] = None
    created_at: datetime = datetime.now(timezone.utc)
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class ERPResponse:
    """Response from ERP system."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    external_id: Optional[str] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    warning_messages: Optional[List[str]] = None


class BaseERPAdapter(ABC):
    """Base class for ERP adapters."""

    def __init__(self, connection: ERPConnection):
        """Initialize the ERP adapter."""
        self.connection = connection
        self.system_type = connection.system_type
        self.environment = connection.environment

    @abstractmethod
    async def test_connection(self) -> ERPResponse:
        """Test connection to ERP system."""
        pass

    @abstractmethod
    async def create_vendor_bill(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create a vendor bill in the ERP system."""
        pass

    @abstractmethod
    async def create_invoice(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create an invoice in the ERP system."""
        pass

    @abstractmethod
    async def update_vendor(self, vendor_data: Dict[str, Any]) -> ERPResponse:
        """Update vendor information in the ERP system."""
        pass

    @abstractmethod
    async def sync_chart_of_accounts(self) -> ERPResponse:
        """Sync chart of accounts from ERP system."""
        pass

    @abstractmethod
    async def get_transaction_status(self, transaction_id: str) -> ERPResponse:
        """Get status of a transaction in the ERP system."""
        pass

    async def transform_invoice_data(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform invoice data to ERP-specific format."""
        return invoice_data  # Default implementation

    async def validate_invoice_data(self, invoice_data: Dict[str, Any]) -> List[str]:
        """Validate invoice data for ERP requirements."""
        return []  # Default implementation

    def log_transaction(self, transaction: ERPTransaction) -> None:
        """Log ERP transaction."""
        logger.info(f"ERP Transaction: {transaction.transaction_type} - {transaction.transaction_id}")


class QuickBooksAdapter(BaseERPAdapter):
    """QuickBooks Online adapter."""

    def __init__(self, connection: ERPConnection):
        """Initialize QuickBooks adapter."""
        super().__init__(connection)
        self.base_url = "https://sandbox-quickbooks.api.intuit.com" if connection.environment == ERPEnvironment.SANDBOX else "https://quickbooks.api.intuit.com"
        self.realm_id = connection.credentials.get("realm_id")
        self.access_token = connection.credentials.get("access_token")

    async def test_connection(self) -> ERPResponse:
        """Test QuickBooks connection."""
        try:
            url = f"{self.base_url}/v3/company/{self.realm_id}/companyinfo/{self.realm_id}"
            headers = {"Authorization": f"Bearer {self.access_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ERPResponse(
                            success=True,
                            data=data,
                            message="QuickBooks connection successful"
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message=f"QuickBooks connection failed: {response.reason}"
                        )

        except Exception as e:
            logger.error(f"QuickBooks connection test failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Connection test failed: {str(e)}"
            )

    async def create_vendor_bill(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create a vendor bill in QuickBooks."""
        try:
            # Transform to QuickBooks format
            qb_data = await self.transform_invoice_data(invoice_data)

            url = f"{self.base_url}/v3/company/{self.realm_id}/bill?minorversion=65"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=qb_data) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        bill_id = response_data.get("Bill", {}).get("Id")
                        return ERPResponse(
                            success=True,
                            external_id=bill_id,
                            data=response_data,
                            message=f"Vendor bill created successfully: {bill_id}"
                        )
                    else:
                        error_message = response_data.get("Fault", {}).get("Error", [{}])[0].get("Message", "Unknown error")
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message=f"Failed to create vendor bill: {error_message}",
                            data=response_data
                        )

        except Exception as e:
            logger.error(f"QuickBooks vendor bill creation failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Vendor bill creation failed: {str(e)}"
            )

    async def create_invoice(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create an invoice in QuickBooks."""
        try:
            # Transform to QuickBooks invoice format
            qb_data = await self._transform_to_invoice(invoice_data)

            url = f"{self.base_url}/v3/company/{self.realm_id}/invoice?minorversion=65"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=qb_data) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        invoice_id = response_data.get("Invoice", {}).get("Id")
                        return ERPResponse(
                            success=True,
                            external_id=invoice_id,
                            data=response_data,
                            message=f"Invoice created successfully: {invoice_id}"
                        )
                    else:
                        error_message = response_data.get("Fault", {}).get("Error", [{}])[0].get("Message", "Unknown error")
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message=f"Failed to create invoice: {error_message}",
                            data=response_data
                        )

        except Exception as e:
            logger.error(f"QuickBooks invoice creation failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Invoice creation failed: {str(e)}"
            )

    async def update_vendor(self, vendor_data: Dict[str, Any]) -> ERPResponse:
        """Update vendor in QuickBooks."""
        try:
            # Implementation for updating vendor
            return ERPResponse(
                success=True,
                message="Vendor update not implemented in sandbox mode"
            )

        except Exception as e:
            logger.error(f"QuickBooks vendor update failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Vendor update failed: {str(e)}"
            )

    async def sync_chart_of_accounts(self) -> ERPResponse:
        """Sync chart of accounts from QuickBooks."""
        try:
            url = f"{self.base_url}/v3/company/{self.realm_id}/query?minorversion=65"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/text"
            }

            query = "SELECT * FROM Account WHERE AccountType IN ('Expense', 'Cost of Goods Sold', 'Other Expense') MAXRESULTS 1000"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=query) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        accounts = response_data.get("QueryResponse", {}).get("Account", [])
                        return ERPResponse(
                            success=True,
                            data={"accounts": accounts},
                            message=f"Synced {len(accounts)} accounts from QuickBooks"
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message="Failed to sync chart of accounts"
                        )

        except Exception as e:
            logger.error(f"QuickBooks chart of accounts sync failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Chart of accounts sync failed: {str(e)}"
            )

    async def get_transaction_status(self, transaction_id: str) -> ERPResponse:
        """Get transaction status from QuickBooks."""
        try:
            url = f"{self.base_url}/v3/company/{self.realm_id}/bill/{transaction_id}?minorversion=65"
            headers = {"Authorization": f"Bearer {self.access_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bill_data = data.get("Bill", {})
                        status = "Paid" if bill_data.get("Balance") == 0 else "Unpaid"

                        return ERPResponse(
                            success=True,
                            data={
                                "status": status,
                                "balance": bill_data.get("Balance"),
                                "due_date": bill_data.get("DueDate")
                            }
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message="Failed to get transaction status"
                        )

        except Exception as e:
            logger.error(f"QuickBooks transaction status check failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Transaction status check failed: {str(e)}"
            )

    async def transform_invoice_data(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform invoice data to QuickBooks vendor bill format."""
        header = invoice_data.get("header", {})
        lines = invoice_data.get("lines", [])

        # Map to QuickBooks Bill format
        qb_bill = {
            "PrivateNote": f"Imported from AP Intake System - PO: {header.get('po_no', 'N/A')}",
            "Line": []
        }

        # Add vendor reference (would need vendor lookup in real implementation)
        if header.get("vendor_name"):
            qb_bill["VendorRef"] = {"value": "1"}  # Placeholder vendor ID

        # Add line items
        for line in lines:
            qb_line = {
                "Amount": float(line.get("amount", 0)),
                "Description": line.get("description", ""),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": "1"},  # Default expense account
                    "BillableStatus": "NotBillable",
                    "Qty": float(line.get("quantity", 1)),
                    "UnitPrice": float(line.get("unit_price", 0))
                }
            }
            qb_bill["Line"].append(qb_line)

        return qb_bill

    async def _transform_to_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform invoice data to QuickBooks invoice format."""
        header = invoice_data.get("header", {})
        lines = invoice_data.get("lines", [])

        qb_invoice = {
            "PrivateNote": f"Imported from AP Intake System",
            "Line": []
        }

        # Add customer reference
        if header.get("vendor_name"):
            qb_invoice["CustomerRef"] = {"value": "1"}  # Placeholder customer ID

        # Add line items
        for line in lines:
            qb_line = {
                "Amount": float(line.get("amount", 0)),
                "Description": line.get("description", ""),
                "DetailType": "SalesItemLineDetail",
                "SalesItemLineDetail": {
                    "ItemRef": {"value": "1"},  # Default item
                    "Qty": float(line.get("quantity", 1)),
                    "UnitPrice": float(line.get("unit_price", 0))
                }
            }
            qb_invoice["Line"].append(qb_line)

        return qb_invoice


class SAPAdapter(BaseERPAdapter):
    """SAP S/4HANA adapter."""

    def __init__(self, connection: ERPConnection):
        """Initialize SAP adapter."""
        super().__init__(connection)
        self.base_url = connection.connection_config.get("base_url")
        self.username = connection.credentials.get("username")
        self.password = connection.credentials.get("password")

    async def test_connection(self) -> ERPResponse:
        """Test SAP connection."""
        try:
            url = f"{self.base_url}/sap/opu/odata/sap/API_SERVICE_DOCUMENT"
            auth = aiohttp.BasicAuth(self.username, self.password)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth) as response:
                    if response.status == 200:
                        return ERPResponse(
                            success=True,
                            message="SAP connection successful"
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message=f"SAP connection failed: {response.reason}"
                        )

        except Exception as e:
            logger.error(f"SAP connection test failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Connection test failed: {str(e)}"
            )

    async def create_vendor_bill(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create a vendor bill in SAP."""
        try:
            # Transform to SAP format
            sap_data = await self.transform_invoice_data(invoice_data)

            url = f"{self.base_url}/sap/opu/odata/sap/API_VENDOR_INVOICE_SRV/A_VendorInvoice"
            auth = aiohttp.BasicAuth(self.username, self.password)
            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, auth=auth, headers=headers, json=sap_data) as response:
                    if response.status == 201:
                        data = await response.json()
                        invoice_id = data.get("d", {}).get("InvoiceDocument")
                        return ERPResponse(
                            success=True,
                            external_id=invoice_id,
                            data=data,
                            message=f"SAP vendor invoice created: {invoice_id}"
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message="Failed to create SAP vendor invoice"
                        )

        except Exception as e:
            logger.error(f"SAP vendor bill creation failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Vendor bill creation failed: {str(e)}"
            )

    async def create_invoice(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create an invoice in SAP."""
        return ERPResponse(
            success=True,
            message="SAP invoice creation not implemented in sandbox mode"
        )

    async def update_vendor(self, vendor_data: Dict[str, Any]) -> ERPResponse:
        """Update vendor in SAP."""
        return ERPResponse(
            success=True,
            message="SAP vendor update not implemented in sandbox mode"
        )

    async def sync_chart_of_accounts(self) -> ERPResponse:
        """Sync chart of accounts from SAP."""
        try:
            url = f"{self.base_url}/sap/opu/odata/sap/API_GL_ACCOUNT_SRV/A_GLAccount"
            auth = aiohttp.BasicAuth(self.username, self.password)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth) as response:
                    if response.status == 200:
                        data = await response.json()
                        accounts = data.get("d", {}).get("results", [])
                        return ERPResponse(
                            success=True,
                            data={"accounts": accounts},
                            message=f"Synced {len(accounts)} accounts from SAP"
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            message="Failed to sync SAP chart of accounts"
                        )

        except Exception as e:
            logger.error(f"SAP chart of accounts sync failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Chart of accounts sync failed: {str(e)}"
            )

    async def get_transaction_status(self, transaction_id: str) -> ERPResponse:
        """Get transaction status from SAP."""
        return ERPResponse(
            success=True,
            data={"status": "Posted"},
            message="SAP transaction status check not implemented in sandbox mode"
        )

    async def transform_invoice_data(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform invoice data to SAP vendor invoice format."""
        header = invoice_data.get("header", {})
        lines = invoice_data.get("lines", [])

        # Map to SAP vendor invoice format
        sap_invoice = {
            "DocumentDate": header.get("invoice_date", datetime.now().strftime("%Y-%m-%d")),
            "PostingDate": datetime.now().strftime("%Y-%m-%d"),
            "CompanyCode": "1000",  # Default company code
            "DocumentCurrency": header.get("currency", "USD"),
            "Vendor": "1001",  # Placeholder vendor code
            "InvoiceGrossAmount": float(header.get("total", 0)),
            "to_Item": []
        }

        # Add line items
        for i, line in enumerate(lines):
            sap_line = {
                "DocumentItemText": line.get("description", ""),
                "Quantity": float(line.get("quantity", 1)),
                "PurchaseOrderQuantityUnit": "EA",
                "NetAmount": float(line.get("amount", 0)),
                "TaxCode": "V0",  # Default tax code
                "CostCenter": "1000",  # Default cost center
                "GLAccount": "0000400000"  # Default GL account
            }
            sap_invoice["to_Item"].append(sap_line)

        return sap_invoice


class GenericERPAdapter(BaseERPAdapter):
    """Generic ERP adapter for webhook-based or custom integrations."""

    def __init__(self, connection: ERPConnection):
        """Initialize generic ERP adapter."""
        super().__init__(connection)
        self.webhook_url = connection.connection_config.get("webhook_url")
        self.api_key = connection.credentials.get("api_key")

    async def test_connection(self) -> ERPResponse:
        """Test generic ERP connection."""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key
            }

            test_data = {
                "action": "test_connection",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, headers=headers, json=test_data) as response:
                    if response.status == 200:
                        return ERPResponse(
                            success=True,
                            message="Generic ERP connection successful"
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message="Generic ERP connection test failed"
                        )

        except Exception as e:
            logger.error(f"Generic ERP connection test failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Connection test failed: {str(e)}"
            )

    async def create_vendor_bill(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create a vendor bill in generic ERP."""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key
            }

            payload = {
                "action": "create_vendor_bill",
                "data": invoice_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ERPResponse(
                            success=True,
                            external_id=data.get("external_id"),
                            data=data,
                            message=data.get("message", "Vendor bill created successfully")
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message="Failed to create vendor bill in generic ERP"
                        )

        except Exception as e:
            logger.error(f"Generic ERP vendor bill creation failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Vendor bill creation failed: {str(e)}"
            )

    async def create_invoice(self, invoice_data: Dict[str, Any]) -> ERPResponse:
        """Create an invoice in generic ERP."""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key
            }

            payload = {
                "action": "create_invoice",
                "data": invoice_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ERPResponse(
                            success=True,
                            external_id=data.get("external_id"),
                            data=data,
                            message=data.get("message", "Invoice created successfully")
                        )
                    else:
                        return ERPResponse(
                            success=False,
                            error_code=str(response.status),
                            message="Failed to create invoice in generic ERP"
                        )

        except Exception as e:
            logger.error(f"Generic ERP invoice creation failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Invoice creation failed: {str(e)}"
            )

    async def update_vendor(self, vendor_data: Dict[str, Any]) -> ERPResponse:
        """Update vendor in generic ERP."""
        return ERPResponse(
            success=True,
            message="Generic ERP vendor update not implemented"
        )

    async def sync_chart_of_accounts(self) -> ERPResponse:
        """Sync chart of accounts from generic ERP."""
        return ERPResponse(
            success=True,
            data={"accounts": []},
            message="Generic ERP chart of accounts sync not implemented"
        )

    async def get_transaction_status(self, transaction_id: str) -> ERPResponse:
        """Get transaction status from generic ERP."""
        return ERPResponse(
            success=True,
            data={"status": "Unknown"},
            message="Generic ERP transaction status check not implemented"
        )


class ERPAdapterService:
    """Service for managing ERP adapters and integrations."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize the ERP adapter service."""
        self.db = db
        self.adapters = {}
        self._initialize_default_adapters()

    def _initialize_default_adapters(self) -> None:
        """Initialize default ERP adapters."""
        # QuickBooks sandbox configuration
        if settings.QUICKBOOKS_SANDBOX_ENABLED:
            qb_connection = ERPConnection(
                system_type=ERPSystemType.QUICKBOOKS,
                environment=ERPEnvironment.SANDBOX,
                connection_config={},
                credentials={
                    "realm_id": settings.QUICKBOOKS_SANDBOX_REALM_ID,
                    "access_token": settings.QUICKBOOKS_SANDBOX_ACCESS_TOKEN
                }
            )
            self.adapters["quickbooks_sandbox"] = QuickBooksAdapter(qb_connection)

        # SAP sandbox configuration
        if settings.SAP_SANDBOX_ENABLED:
            sap_connection = ERPConnection(
                system_type=ERPSystemType.SAP,
                environment=ERPEnvironment.SANDBOX,
                connection_config={
                    "base_url": settings.SAP_SANDBOX_URL
                },
                credentials={
                    "username": settings.SAP_SANDBOX_USERNAME,
                    "password": settings.SAP_SANDBOX_PASSWORD
                }
            )
            self.adapters["sap_sandbox"] = SAPAdapter(sap_connection)

        # Generic ERP configuration
        if settings.GENERIC_ERP_WEBHOOK_URL:
            generic_connection = ERPConnection(
                system_type=ERPSystemType.GENERIC,
                environment=ERPEnvironment.SANDBOX,
                connection_config={
                    "webhook_url": settings.GENERIC_ERP_WEBHOOK_URL
                },
                credentials={
                    "api_key": settings.GENERIC_ERP_API_KEY
                }
            )
            self.adapters["generic"] = GenericERPAdapter(generic_connection)

    def get_adapter(self, system_type: ERPSystemType, environment: ERPEnvironment = ERPEnvironment.SANDBOX) -> BaseERPAdapter:
        """Get ERP adapter for specified system and environment."""
        adapter_key = f"{system_type.value}_{environment.value}"
        adapter = self.adapters.get(adapter_key)

        if not adapter:
            raise ERPException(f"ERP adapter not found for {system_type.value} in {environment.value}")

        return adapter

    async def test_erp_connection(self, system_type: ERPSystemType, environment: ERPEnvironment = ERPEnvironment.SANDBOX) -> ERPResponse:
        """Test connection to ERP system."""
        try:
            adapter = self.get_adapter(system_type, environment)
            return await adapter.test_connection()

        except Exception as e:
            logger.error(f"ERP connection test failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Connection test failed: {str(e)}"
            )

    async def export_invoice_to_erp(
        self,
        invoice_data: Dict[str, Any],
        system_type: ERPSystemType,
        environment: ERPEnvironment = ERPEnvironment.SANDBOX,
        action: ERPAction = ERPAction.CREATE_VENDOR_BILL
    ) -> ERPResponse:
        """Export invoice to ERP system."""
        try:
            adapter = self.get_adapter(system_type, environment)

            # Validate invoice data
            validation_errors = await adapter.validate_invoice_data(invoice_data)
            if validation_errors:
                return ERPResponse(
                    success=False,
                    message=f"Validation errors: {'; '.join(validation_errors)}"
                )

            # Execute action based on type
            if action == ERPAction.CREATE_VENDOR_BILL:
                return await adapter.create_vendor_bill(invoice_data)
            elif action == ERPAction.CREATE_INVOICE:
                return await adapter.create_invoice(invoice_data)
            else:
                return ERPResponse(
                    success=False,
                    message=f"Unsupported action: {action.value}"
                )

        except Exception as e:
            logger.error(f"ERP export failed: {e}")
            return ERPResponse(
                success=False,
                message=f"ERP export failed: {str(e)}"
            )

    async def sync_chart_of_accounts(self, system_type: ERPSystemType, environment: ERPEnvironment = ERPEnvironment.SANDBOX) -> ERPResponse:
        """Sync chart of accounts from ERP system."""
        try:
            adapter = self.get_adapter(system_type, environment)
            return await adapter.sync_chart_of_accounts()

        except Exception as e:
            logger.error(f"Chart of accounts sync failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Chart of accounts sync failed: {str(e)}"
            )

    async def get_erp_transaction_status(
        self,
        transaction_id: str,
        system_type: ERPSystemType,
        environment: ERPEnvironment = ERPEnvironment.SANDBOX
    ) -> ERPResponse:
        """Get transaction status from ERP system."""
        try:
            adapter = self.get_adapter(system_type, environment)
            return await adapter.get_transaction_status(transaction_id)

        except Exception as e:
            logger.error(f"Transaction status check failed: {e}")
            return ERPResponse(
                success=False,
                message=f"Transaction status check failed: {str(e)}"
            )

    def get_available_erps(self) -> List[Dict[str, Any]]:
        """Get list of available ERP systems."""
        available_erps = []

        for key, adapter in self.adapters.items():
            system_type, environment = key.rsplit("_", 1)
            available_erps.append({
                "system_type": system_type,
                "environment": environment,
                "adapter_class": adapter.__class__.__name__
            })

        return available_erps

    async def create_custom_adapter(
        self,
        system_type: ERPSystemType,
        connection_config: Dict[str, Any],
        credentials: Dict[str, Any],
        environment: ERPEnvironment = ERPEnvironment.SANDBOX
    ) -> str:
        """Create a custom ERP adapter."""
        try:
            connection = ERPConnection(
                system_type=system_type,
                environment=environment,
                connection_config=connection_config,
                credentials=credentials
            )

            # Create appropriate adapter based on system type
            if system_type == ERPSystemType.QUICKBOOKS:
                adapter = QuickBooksAdapter(connection)
            elif system_type == ERPSystemType.SAP:
                adapter = SAPAdapter(connection)
            elif system_type == ERPSystemType.GENERIC:
                adapter = GenericERPAdapter(connection)
            else:
                raise ERPException(f"Unsupported ERP system type: {system_type}")

            # Test connection
            test_result = await adapter.test_connection()
            if not test_result.success:
                raise ERPException(f"Connection test failed: {test_result.message}")

            # Store adapter
            adapter_key = f"{system_type.value}_{environment.value}_custom"
            self.adapters[adapter_key] = adapter

            logger.info(f"Custom ERP adapter created: {adapter_key}")
            return adapter_key

        except Exception as e:
            logger.error(f"Failed to create custom ERP adapter: {e}")
            raise ERPException(f"Failed to create custom ERP adapter: {str(e)}")

    def remove_adapter(self, adapter_key: str) -> bool:
        """Remove an ERP adapter."""
        if adapter_key in self.adapters:
            del self.adapters[adapter_key]
            logger.info(f"ERP adapter removed: {adapter_key}")
            return True
        return False