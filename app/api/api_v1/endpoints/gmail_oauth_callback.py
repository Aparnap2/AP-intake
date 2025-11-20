"""
Gmail OAuth callback endpoint for seamless web-based OAuth flow.

Handles OAuth callback from Google and redirects back to dashboard.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1 import deps
from app.services.gmail_service import GmailService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/oauth/callback")
async def gmail_oauth_callback(
    request: Request,
    code: Optional[str] = Query(None, description="Authorization code from Google"),
    state: Optional[str] = Query(None, description="OAuth state parameter"),
    error: Optional[str] = Query(None, description="OAuth error"),
    error_description: Optional[str] = Query(None, description="Error description"),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Handle Gmail OAuth callback from Google.

    This endpoint receives the authorization code from Google,
    exchanges it for credentials, and redirects back to dashboard.
    """
    try:
        # Handle OAuth errors
        if error:
            logger.error(f"Gmail OAuth error: {error} - {error_description}")
            # Redirect to dashboard with error
            return RedirectResponse(
                url=f"http://localhost:3000/auth/gmail/error?error={error}&description={error_description}"
            )

        if not code:
            logger.error("No authorization code received from Google")
            return RedirectResponse(
                url="http://localhost:3000/auth/gmail/error?error=no_code&description=No+authorization+code"
            )

        logger.info(f"Received Gmail OAuth callback with state: {state}")

        try:
            # Exchange authorization code for credentials
            gmail_service = GmailService()
            credentials = await gmail_service.exchange_code_for_credentials(
                authorization_code=code,
                redirect_uri="http://localhost:8000/api/v1/gmail/oauth/callback"
            )

            # Build service to validate credentials and get user info
            await gmail_service.build_service(credentials)
            user_info = await gmail_service.get_user_info()

            # TODO: Store credentials in database
            # For now, we'll just redirect with success info

            email_address = user_info.get("email_address")

            logger.info(f"Successfully authenticated Gmail user: {email_address}")

            # Redirect to dashboard with success
            return RedirectResponse(
                url=f"http://localhost:3000/auth/gmail/success?"
                f"email={email_address}&"
                f"state={state}&"
                f"message=Gmail+successfully+connected"
            )

        except Exception as e:
            logger.error(f"Failed to exchange authorization code: {str(e)}")
            return RedirectResponse(
                url=f"http://localhost:3000/auth/gmail/error?error=exchange_failed&description={str(e)}"
            )

    except Exception as e:
        logger.error(f"Unexpected error in OAuth callback: {str(e)}")
        return RedirectResponse(
            url=f"http://localhost:3000/auth/gmail/error?error=unexpected&description={str(e)}"
        )


@router.get("/auth/quick")
async def quick_gmail_auth(
    request: Request,
    user_id: str = Query(..., description="User ID"),
    redirect_to: str = Query("http://localhost:3000/dashboard", description="Where to redirect after auth")
):
    """
    Quick Gmail OAuth authorization - one-click flow.

    This generates the authorization URL and immediately redirects the user.
    """
    try:
        gmail_service = GmailService()
        authorization_url, state = await gmail_service.get_authorization_url(
            redirect_uri="http://localhost:8000/api/v1/gmail/oauth/callback",
            state=f"user_id:{user_id}:redirect_to:{redirect_to}"
        )

        logger.info(f"Generated quick Gmail auth URL for user {user_id}")

        # Immediately redirect to Google OAuth
        return RedirectResponse(url=authorization_url)

    except Exception as e:
        logger.error(f"Failed to generate quick auth URL: {str(e)}")
        # Redirect back with error
        return RedirectResponse(
            url=f"{redirect_to}?error=auth_failed&description={str(e)}"
        )