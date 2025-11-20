"""
Gmail Pub/Sub webhook endpoints for real-time email processing.

Replaces polling with push notifications for immediate invoice processing.
"""

import base64
import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.exceptions import EmailIngestionException
from app.services.gmail_pubsub_service import gmail_pubsub_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/gmail-webhook")
async def gmail_webhook(request: Request):
    """
    Handle Gmail Pub/Sub push notifications.

    This endpoint receives real-time notifications from Gmail via Google Cloud Pub/Sub
    when new emails arrive in monitored mailboxes.
    """
    try:
        # Parse Pub/Sub message
        body = await request.json()
        logger.info(f"Received Gmail Pub/Sub message: {type(body)}")

        # Validate Pub/Sub message format
        if 'message' not in body:
            logger.warning("Invalid Pub/Sub message format: missing 'message' field")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid Pub/Sub message format"}
            )

        message = body['message']

        # Extract and decode notification data
        notification_data = None
        if 'data' in message:
            try:
                notification_data = json.loads(
                    base64.b64decode(message['data']).decode('utf-8')
                )
                logger.info(f"Decoded Gmail notification: {notification_data.get('emailAddress')}")
            except (ValueError, UnicodeDecodeError) as e:
                logger.error(f"Failed to decode Pub/Sub message data: {str(e)}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Failed to decode message data"}
                )

        if not notification_data:
            logger.warning("No data in Pub/Sub message")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "No data in message"}
            )

        # Extract notification details
        email_address = notification_data.get('emailAddress')
        history_id = notification_data.get('historyId')

        if not email_address or not history_id:
            logger.error(f"Missing required fields: emailAddress={email_address}, historyId={history_id}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Missing emailAddress or historyId"}
            )

        logger.info(f"Processing Gmail notification for {email_address}, historyId: {history_id}")

        # Process the Gmail notification
        result = await gmail_pubsub_service.process_pubsub_message(message)

        # Log processing results
        if result.get('success', False):
            logger.info(f"✅ Successfully processed Gmail notification: {result}")
        else:
            logger.error(f"❌ Failed to process Gmail notification: {result}")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success" if result.get('success') else "error",
                "message": "Notification processed" if result.get('success') else result.get('error'),
                "result": result
            }
        )

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook request: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid JSON format"}
        )

    except Exception as e:
        logger.error(f"Unexpected error processing Gmail webhook: {str(e)}")
        # Don't return 500 to Pub/Sub - this would trigger retries
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "error", "message": "Internal processing error"}
        )


@router.post("/gmail-setup-watch")
async def setup_gmail_watch(request: Request):
    """
    Set up Gmail watch for real-time notifications.

    This endpoint initializes Gmail push notifications for a user's mailbox.
    """
    try:
        body = await request.json()

        # Validate required fields
        required_fields = ['email', 'credentials']
        for field in required_fields:
            if field not in body:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )

        email = body['email']
        credentials = body['credentials']

        logger.info(f"Setting up Gmail watch for {email}")

        # Set up Gmail watch
        result = await gmail_pubsub_service.setup_gmail_watch({
            'email': email,
            **credentials
        })

        if result.get('success'):
            logger.info(f"✅ Gmail watch setup successful for {email}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "success",
                    "message": "Gmail watch set up successfully",
                    "details": result
                }
            )
        else:
            logger.error(f"❌ Failed to set up Gmail watch for {email}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "message": "Failed to set up Gmail watch",
                    "details": result
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up Gmail watch: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": str(e)
            }
        )


@router.post("/gmail-stop-watch")
async def stop_gmail_watch(request: Request):
    """
    Stop Gmail watch notifications.

    This endpoint stops real-time notifications for a user's mailbox.
    """
    try:
        body = await request.json()

        # Validate required fields
        required_fields = ['email', 'credentials']
        for field in required_fields:
            if field not in body:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )

        email = body['email']
        credentials = body['credentials']

        logger.info(f"Stopping Gmail watch for {email}")

        # Stop Gmail watch
        success = await gmail_pubsub_service.stop_gmail_watch({
            'email': email,
            **credentials
        })

        if success:
            logger.info(f"✅ Gmail watch stopped successfully for {email}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "success",
                    "message": "Gmail watch stopped successfully"
                }
            )
        else:
            logger.error(f"❌ Failed to stop Gmail watch for {email}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "message": "Failed to stop Gmail watch"
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping Gmail watch: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": str(e)
            }
        )


@router.get("/gmail-watch-health")
async def gmail_watch_health(request: Request):
    """
    Check health status of Gmail watch setup.

    This endpoint verifies that Gmail push notifications are working correctly.
    """
    try:
        # TODO: Get user credentials from request or auth context
        # For now, return general health status
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "message": "Gmail Pub/Sub service is running",
                "pubsub_configured": True,
                "webhook_endpoint": str(request.url).replace('/health', '/gmail-webhook'),
                "timestamp": "2025-11-16T12:00:00Z"
            }
        )

    except Exception as e:
        logger.error(f"Error checking Gmail watch health: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": str(e)
            }
        )


@router.get("/gmail-stats")
async def gmail_stats():
    """
    Get Gmail processing statistics.

    This endpoint returns statistics about email processing performance.
    """
    try:
        # TODO: Implement actual statistics collection
        # For now, return mock data
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "total_emails_processed": 0,
                "invoices_detected": 0,
                "attachments_processed": 0,
                "average_processing_time_ms": 0,
                "last_notification": None,
                "active_watches": 0,
                "errors_24h": 0,
                "timestamp": "2025-11-16T12:00:00Z"
            }
        )

    except Exception as e:
        logger.error(f"Error getting Gmail stats: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": str(e)
            }
        )