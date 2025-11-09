"""
n8n webhook endpoints for handling workflow callbacks and events.
This module provides FastAPI endpoints for receiving n8n webhook events,
validating signatures, and processing workflow responses.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.schemas.n8n_schemas import N8nWebhookEvent, N8nApiResponse
from app.services.n8n_service import N8nService, N8nWorkflowException

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_n8n_service() -> N8nService:
    """Dependency to get n8n service instance."""
    return N8nService()


@router.post("/webhook/n8n/{webhook_path}")
async def handle_n8n_webhook(
    webhook_path: str,
    request: Request,
    n8n_service: N8nService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Handle incoming webhook events from n8n workflows.

    Args:
        webhook_path: Webhook path for routing
        request: FastAPI request object
        n8n_service: n8n service instance

    Returns:
        Webhook processing response
    """
    try:
        # Get request body
        body = await request.body()

        # Parse JSON data
        try:
            webhook_data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON data")

        # Get signature from headers
        signature = request.headers.get("X-n8n-signature") or request.headers.get("X-Hook-Signature")

        # Create webhook event
        webhook_event = N8nWebhookEvent(
            workflow_id=webhook_data.get("workflowId", "unknown"),
            execution_id=webhook_data.get("executionId", "unknown"),
            status=webhook_data.get("status", "unknown"),
            timestamp=datetime.utcnow(),
            data=webhook_data,
            signature=signature
        )

        # Process webhook event
        result = await n8n_service.process_webhook_event(webhook_event)

        # Log successful processing
        logger.info(f"Processed n8n webhook event {webhook_event.execution_id}")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Webhook processed successfully",
                "execution_id": webhook_event.execution_id,
                "processed_at": result["processed_at"]
            }
        )

    except N8nWorkflowException as e:
        logger.error(f"n8n workflow error in webhook processing: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Workflow processing failed",
                "error": str(e)
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error in n8n webhook processing: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Internal server error",
                "error": "An unexpected error occurred"
            }
        )


@router.post("/webhook/n8n/ap-invoice")
async def handle_ap_invoice_webhook(
    request: Request,
    n8n_service: N8nService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Handle AP invoice processing webhook events.

    Args:
        request: FastAPI request object
        n8n_service: n8n service instance

    Returns:
        Webhook processing response
    """
    try:
        webhook_data = await request.json()
        signature = request.headers.get("X-n8n-signature")

        # Create specialized webhook event for AP invoice processing
        webhook_event = N8nWebhookEvent(
            workflow_id=webhook_data.get("workflowId", "ap_invoice_processing"),
            execution_id=webhook_data.get("executionId"),
            status=webhook_data.get("status"),
            timestamp=datetime.utcnow(),
            data=webhook_data,
            signature=signature
        )

        result = await n8n_service.process_webhook_event(webhook_event)

        # Handle AP invoice specific logic
        if webhook_event.status == "success":
            # Update invoice status, send notifications, etc.
            invoice_id = webhook_data.get("data", {}).get("invoice_id")
            if invoice_id:
                logger.info(f"AP invoice {invoice_id} workflow completed successfully")
                # Here you would update the invoice status in your database

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "AP invoice webhook processed",
                "invoice_id": webhook_data.get("data", {}).get("invoice_id"),
                "execution_status": webhook_event.status
            }
        )

    except Exception as e:
        logger.error(f"Error processing AP invoice webhook: {e}")
        raise HTTPException(status_code=500, detail="AP invoice webhook processing failed")


@router.post("/webhook/n8n/ar-invoice")
async def handle_ar_invoice_webhook(
    request: Request,
    n8n_service: N8nService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Handle AR invoice processing webhook events.

    Args:
        request: FastAPI request object
        n8n_service: n8n service instance

    Returns:
        Webhook processing response
    """
    try:
        webhook_data = await request.json()
        signature = request.headers.get("X-n8n-signature")

        webhook_event = N8nWebhookEvent(
            workflow_id=webhook_data.get("workflowId", "ar_invoice_processing"),
            execution_id=webhook_data.get("executionId"),
            status=webhook_data.get("status"),
            timestamp=datetime.utcnow(),
            data=webhook_data,
            signature=signature
        )

        result = await n8n_service.process_webhook_event(webhook_event)

        # Handle AR invoice specific logic
        if webhook_event.status == "success":
            invoice_id = webhook_data.get("data", {}).get("invoice_id")
            customer_id = webhook_data.get("data", {}).get("customer_id")
            if invoice_id and customer_id:
                logger.info(f"AR invoice {invoice_id} for customer {customer_id} workflow completed")
                # Update customer account, send invoice, etc.

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "AR invoice webhook processed",
                "invoice_id": webhook_data.get("data", {}).get("invoice_id"),
                "customer_id": webhook_data.get("data", {}).get("customer_id"),
                "execution_status": webhook_event.status
            }
        )

    except Exception as e:
        logger.error(f"Error processing AR invoice webhook: {e}")
        raise HTTPException(status_code=500, detail="AR invoice webhook processing failed")


@router.post("/webhook/n8n/working-capital")
async def handle_working_capital_webhook(
    request: Request,
    n8n_service: N8nService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Handle working capital analysis webhook events.

    Args:
        request: FastAPI request object
        n8n_service: n8n service instance

    Returns:
        Webhook processing response
    """
    try:
        webhook_data = await request.json()
        signature = request.headers.get("X-n8n-signature")

        webhook_event = N8nWebhookEvent(
            workflow_id=webhook_data.get("workflowId", "working_capital_analysis"),
            execution_id=webhook_data.get("executionId"),
            status=webhook_data.get("status"),
            timestamp=datetime.utcnow(),
            data=webhook_data,
            signature=signature
        )

        result = await n8n_service.process_webhook_event(webhook_event)

        # Handle working capital analysis specific logic
        if webhook_event.status == "success":
            analysis_results = webhook_data.get("data", {}).get("analysis_results")
            if analysis_results:
                logger.info("Working capital analysis completed successfully")
                # Store analysis results, send reports, etc.

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Working capital analysis webhook processed",
                "analysis_date": webhook_data.get("data", {}).get("analysis_date"),
                "execution_status": webhook_event.status
            }
        )

    except Exception as e:
        logger.error(f"Error processing working capital webhook: {e}")
        raise HTTPException(status_code=500, detail="Working capital webhook processing failed")


@router.post("/webhook/n8n/exception-handling")
async def handle_exception_handling_webhook(
    request: Request,
    n8n_service: N8nService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Handle exception handling webhook events.

    Args:
        request: FastAPI request object
        n8n_service: n8n service instance

    Returns:
        Webhook processing response
    """
    try:
        webhook_data = await request.json()
        signature = request.headers.get("X-n8n-signature")

        webhook_event = N8nWebhookEvent(
            workflow_id=webhook_data.get("workflowId", "exception_handling"),
            execution_id=webhook_data.get("executionId"),
            status=webhook_data.get("status"),
            timestamp=datetime.utcnow(),
            data=webhook_data,
            signature=signature
        )

        result = await n8n_service.process_webhook_event(webhook_event)

        # Handle exception handling specific logic
        exception_id = webhook_data.get("data", {}).get("exception_id")
        resolution_result = webhook_data.get("data", {}).get("resolution_result")

        if webhook_event.status == "success" and resolution_result:
            logger.info(f"Exception {exception_id} handled successfully")
            # Update exception status, notify users, etc.

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Exception handling webhook processed",
                "exception_id": exception_id,
                "resolution_status": resolution_result.get("status") if resolution_result else None,
                "execution_status": webhook_event.status
            }
        )

    except Exception as e:
        logger.error(f"Error processing exception handling webhook: {e}")
        raise HTTPException(status_code=500, detail="Exception handling webhook processing failed")


@router.post("/webhook/n8n/weekly-report")
async def handle_weekly_report_webhook(
    request: Request,
    n8n_service: N8nService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Handle weekly report generation webhook events.

    Args:
        request: FastAPI request object
        n8n_service: n8n service instance

    Returns:
        Webhook processing response
    """
    try:
        webhook_data = await request.json()
        signature = request.headers.get("X-n8n-signature")

        webhook_event = N8nWebhookEvent(
            workflow_id=webhook_data.get("workflowId", "weekly_report_generation"),
            execution_id=webhook_data.get("executionId"),
            status=webhook_data.get("status"),
            timestamp=datetime.utcnow(),
            data=webhook_data,
            signature=signature
        )

        result = await n8n_service.process_webhook_event(webhook_event)

        # Handle weekly report specific logic
        if webhook_event.status == "success":
            report_info = webhook_data.get("data", {}).get("report_info")
            if report_info:
                logger.info(f"Weekly report generated: {report_info.get('report_id')}")
                # Store report, send notifications, etc.

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Weekly report webhook processed",
                "report_id": webhook_data.get("data", {}).get("report_info", {}).get("report_id"),
                "report_format": webhook_data.get("data", {}).get("report_info", {}).get("format"),
                "execution_status": webhook_event.status
            }
        )

    except Exception as e:
        logger.error(f"Error processing weekly report webhook: {e}")
        raise HTTPException(status_code=500, detail="Weekly report webhook processing failed")


@router.get("/webhook/n8n/status")
async def get_webhook_status() -> Dict[str, Any]:
    """
    Get webhook endpoint status.

    Returns:
        Webhook endpoint status information
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "active",
            "message": "n8n webhook endpoints are active",
            "timestamp": datetime.utcnow().isoformat(),
            "endpoints": [
                "/webhook/n8n/{webhook_path}",
                "/webhook/n8n/ap-invoice",
                "/webhook/n8n/ar-invoice",
                "/webhook/n8n/working-capital",
                "/webhook/n8n/exception-handling",
                "/webhook/n8n/weekly-report"
            ]
        }
    )


@router.post("/webhook/n8n/test")
async def test_webhook(
    request: Request,
    n8n_service: N8nService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Test webhook endpoint functionality.

    Args:
        request: FastAPI request object
        n8n_service: n8n service instance

    Returns:
        Test results
    """
    try:
        webhook_data = await request.json()

        # Create test webhook event
        test_event = N8nWebhookEvent(
            workflow_id=webhook_data.get("workflowId", "test_workflow"),
            execution_id=f"test_{datetime.utcnow().timestamp()}",
            status="success",
            timestamp=datetime.utcnow(),
            data=webhook_data,
            signature=request.headers.get("X-n8n-signature")
        )

        result = await n8n_service.process_webhook_event(test_event)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Webhook test completed successfully",
                "test_execution_id": test_event.execution_id,
                "processed_at": result["processed_at"],
                "test_data": webhook_data
            }
        )

    except Exception as e:
        logger.error(f"Error in webhook test: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Webhook test failed",
                "error": str(e)
            }
        )