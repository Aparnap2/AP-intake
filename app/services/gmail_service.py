"""
Gmail API service for email monitoring and PDF attachment extraction.
"""

import base64
import hashlib
import logging
import mimetypes
import os
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import EmailIngestionException

logger = logging.getLogger(__name__)


class EmailMessage(BaseModel):
    """Email message model."""
    id: str
    thread_id: str
    subject: str
    from_email: str
    to_emails: List[str]
    date: datetime
    body: str
    attachments: List[Dict[str, Any]]
    labels: List[str]
    snippet: str


class GmailCredentials(BaseModel):
    """Gmail OAuth 2.0 credentials model."""
    token: str
    refresh_token: Optional[str] = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: str
    client_secret: str
    scopes: List[str]
    expiry: Optional[datetime] = None


class GmailService:
    """Service for interacting with Gmail API."""

    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify'
    ]

    def __init__(self):
        """Initialize Gmail service."""
        self.client_id = settings.GMAIL_CLIENT_ID
        self.client_secret = settings.GMAIL_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            logger.warning("Gmail credentials not configured")

        self.service = None
        self.credentials = None

    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> Tuple[str, str]:
        """Get OAuth 2.0 authorization URL."""
        if not self.client_id or not self.client_secret:
            raise EmailIngestionException("Gmail credentials not configured")

        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=self.SCOPES
            )

            flow.redirect_uri = redirect_uri

            if state:
                flow.state = state

            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )

            logger.info(f"Generated authorization URL with state: {state}")
            return authorization_url, state

        except Exception as e:
            logger.error(f"Failed to generate authorization URL: {e}")
            raise EmailIngestionException(f"Failed to generate authorization URL: {str(e)}")

    async def exchange_code_for_credentials(self, authorization_code: str, redirect_uri: str) -> GmailCredentials:
        """Exchange authorization code for OAuth 2.0 credentials."""
        if not self.client_id or not self.client_secret:
            raise EmailIngestionException("Gmail credentials not configured")

        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=self.SCOPES
            )

            flow.redirect_uri = redirect_uri

            # Exchange code for credentials
            flow.fetch_token(code=authorization_code)

            credentials = flow.credentials

            credentials_model = GmailCredentials(
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=self.SCOPES,
                expiry=credentials.expiry
            )

            logger.info("Successfully exchanged authorization code for credentials")
            return credentials_model

        except Exception as e:
            logger.error(f"Failed to exchange authorization code: {e}")
            raise EmailIngestionException(f"Failed to exchange authorization code: {str(e)}")

    async def build_service(self, credentials: GmailCredentials) -> None:
        """Build Gmail API service with credentials."""
        try:
            # Convert Pydantic model to Google Credentials object
            google_creds = Credentials(
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                expiry=credentials.expiry
            )

            # Refresh token if needed
            if google_creds.expired and google_creds.refresh_token:
                google_creds.refresh(Request())

            self.service = build('gmail', 'v1', credentials=google_creds)
            self.credentials = google_creds

            logger.info("Successfully built Gmail service")

        except Exception as e:
            logger.error(f"Failed to build Gmail service: {e}")
            raise EmailIngestionException(f"Failed to build Gmail service: {str(e)}")

    async def get_user_info(self) -> Dict[str, Any]:
        """Get authenticated user information."""
        if not self.service:
            raise EmailIngestionException("Gmail service not initialized")

        try:
            user_info = self.service.users().getProfile(userId='me').execute()
            return {
                "email_address": user_info.get("emailAddress"),
                "history_id": user_info.get("historyId"),
                "messages_total": user_info.get("messagesTotal"),
                "threads_total": user_info.get("threadsTotal")
            }
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise EmailIngestionException(f"Failed to get user info: {str(e)}")

    async def search_messages(
        self,
        query: str,
        max_results: int = 10,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for messages matching query."""
        if not self.service:
            raise EmailIngestionException("Gmail service not initialized")

        try:
            logger.info(f"Searching messages with query: {query}")

            try:
                result = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=max_results,
                    pageToken=page_token
                ).execute()
            except HttpError as e:
                if e.resp.status == 429:
                    # Rate limit exceeded
                    retry_after = int(e.resp.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit exceeded, retrying after {retry_after} seconds")
                    time.sleep(retry_after)
                    return await self.search_messages(query, max_results, page_token)
                else:
                    raise

            messages = result.get('messages', [])
            next_page_token = result.get('nextPageToken')

            logger.info(f"Found {len(messages)} messages")

            return {
                'messages': messages,
                'next_page_token': next_page_token,
                'result_size_estimate': result.get('resultSizeEstimate', 0)
            }

        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            raise EmailIngestionException(f"Gmail API error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to search messages: {e}")
            raise EmailIngestionException(f"Failed to search messages: {str(e)}")

    async def get_message(self, message_id: str) -> EmailMessage:
        """Get full message details including attachments."""
        if not self.service:
            raise EmailIngestionException("Gmail service not initialized")

        try:
            logger.info(f"Getting message: {message_id}")

            # Get message with full payload
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Parse headers
            headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}

            # Extract basic info
            subject = headers.get('Subject', '')
            from_email = headers.get('From', '')
            to_emails = [email.strip() for email in headers.get('To', '').split(',')]
            date_str = headers.get('Date', '')

            # Parse date
            try:
                date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
            except:
                date = datetime.utcnow()

            # Extract body
            body = await self._extract_body(message['payload'])

            # Extract attachments
            attachments = await self._extract_attachments(message['payload'])

            # Get labels
            labels = message.get('labelIds', [])

            return EmailMessage(
                id=message['id'],
                thread_id=message['threadId'],
                subject=subject,
                from_email=from_email,
                to_emails=to_emails,
                date=date,
                body=body,
                attachments=attachments,
                labels=labels,
                snippet=message.get('snippet', '')
            )

        except HttpError as e:
            logger.error(f"Gmail API error getting message {message_id}: {e}")
            raise EmailIngestionException(f"Failed to get message: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            raise EmailIngestionException(f"Failed to get message: {str(e)}")

    async def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from payload."""
        body = ""

        if 'parts' in payload:
            # Multipart message
            for part in payload['parts']:
                if part['mimeType'].startswith('text/plain'):
                    data = part['body'].get('data', '')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif part['mimeType'].startswith('text/html'):
                    # Prefer plain text over HTML
                    if not body:
                        data = part['body'].get('data', '')
                        if data:
                            html_content = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                            # Basic HTML to text conversion
                            import re
                            body = re.sub('<[^<]+?>', '', html_content)
        else:
            # Single part message
            data = payload['body'].get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        return body

    async def _extract_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract PDF attachments from payload."""
        attachments = []

        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    attachment = await self._process_attachment(part)
                    if attachment:
                        attachments.append(attachment)
        else:
            if payload.get('filename'):
                attachment = await self._process_attachment(payload)
                if attachment:
                    attachments.append(attachment)

        return attachments

    async def _process_attachment(self, part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single attachment."""
        try:
            filename = part['filename']
            mime_type = part['mimeType']

            # Only process PDF files for invoice processing
            if not mime_type == 'application/pdf' and not filename.lower().endswith('.pdf'):
                return None

            attachment_id = part['body'].get('attachmentId')
            if not attachment_id:
                return None

            size = part['body'].get('size', 0)

            # Security check - don't process extremely large attachments
            max_size = 50 * 1024 * 1024  # 50MB
            if size > max_size:
                logger.warning(f"Attachment {filename} too large ({size} bytes), skipping")
                return None

            return {
                'filename': filename,
                'mime_type': mime_type,
                'size': size,
                'attachment_id': attachment_id,
                'is_pdf': True
            }

        except Exception as e:
            logger.error(f"Error processing attachment: {e}")
            return None

    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment content."""
        if not self.service:
            raise EmailIngestionException("Gmail service not initialized")

        try:
            logger.info(f"Downloading attachment {attachment_id} from message {message_id}")

            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()

            data = attachment.get('data', '')
            if data:
                content = base64.urlsafe_b64decode(data)
                logger.info(f"Downloaded attachment content ({len(content)} bytes)")
                return content
            else:
                raise EmailIngestionException("No attachment data found")

        except HttpError as e:
            logger.error(f"Failed to download attachment {attachment_id}: {e}")
            raise EmailIngestionException(f"Failed to download attachment: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to download attachment {attachment_id}: {e}")
            raise EmailIngestionException(f"Failed to download attachment: {str(e)}")

    async def mark_message_processed(self, message_id: str) -> None:
        """Mark message as processed by adding label."""
        if not self.service:
            raise EmailIngestionException("Gmail service not initialized")

        try:
            # Create 'PROCESSED' label if it doesn't exist
            await self._ensure_label_exists('PROCESSED')

            # Add label to message
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={
                    'addLabelIds': ['PROCESSED']
                }
            ).execute()

            logger.info(f"Marked message {message_id} as processed")

        except Exception as e:
            logger.error(f"Failed to mark message {message_id} as processed: {e}")
            # Don't raise exception - this is not critical

    async def _ensure_label_exists(self, label_name: str) -> None:
        """Ensure a label exists, create if necessary."""
        try:
            # Try to get the label
            self.service.users().labels().get(
                userId='me',
                id=label_name
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                # Label doesn't exist, create it
                self.service.users().labels().create(
                    userId='me',
                    body={
                        'name': label_name,
                        'labelListVisibility': 'labelShow',
                        'messageListVisibility': 'show'
                    }
                ).execute()
                logger.info(f"Created label: {label_name}")
            else:
                raise

    async def get_recent_invoices(
        self,
        days_back: int = 7,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent emails with PDF attachments that might be invoices."""
        if not self.service:
            raise EmailIngestionException("Gmail service not initialized")

        try:
            # Build search query for recent emails with PDF attachments
            date_query = f"newer:{(datetime.utcnow() - timedelta(days=days_back)).strftime('%Y/%m/%d')}"
            attachment_query = "has:attachment filename:pdf"
            invoice_keywords = "invoice OR bill OR receipt OR statement"

            query = f"{date_query} {attachment_query} ({invoice_keywords})"

            logger.info(f"Searching for recent invoices with query: {query}")

            # Search for messages
            result = await self.search_messages(query, max_results)

            invoice_messages = []
            for message_ref in result.get('messages', []):
                try:
                    message = await self.get_message(message_ref['id'])

                    # Filter messages that have PDF attachments
                    pdf_attachments = [att for att in message.attachments if att.get('is_pdf')]
                    if pdf_attachments:
                        invoice_messages.append({
                            'message_id': message.id,
                            'thread_id': message.thread_id,
                            'subject': message.subject,
                            'from_email': message.from_email,
                            'date': message.date,
                            'attachments': pdf_attachments,
                            'body_preview': message.snippet
                        })

                except Exception as e:
                    logger.error(f"Error processing message {message_ref['id']}: {e}")
                    continue

            logger.info(f"Found {len(invoice_messages)} potential invoice messages")
            return invoice_messages

        except Exception as e:
            logger.error(f"Failed to get recent invoices: {e}")
            raise EmailIngestionException(f"Failed to get recent invoices: {str(e)}")

    def is_rate_limit_error(self, error: HttpError) -> bool:
        """Check if error is a rate limit error."""
        return error.resp.status == 429

    async def handle_rate_limit(self, error: HttpError) -> None:
        """Handle rate limiting with exponential backoff."""
        if self.is_rate_limit_error(error):
            retry_after = int(error.resp.headers.get('Retry-After', 60))
            logger.warning(f"Rate limit exceeded, waiting {retry_after} seconds")
            time.sleep(retry_after)
        else:
            raise error