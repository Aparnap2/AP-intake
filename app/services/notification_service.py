"""
Notification service for sending alerts and updates.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotificationException
from app.models.user import User
from app.models.invoice import Invoice
from app.models.approval_models import ApprovalRequest, ApprovalDecision
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending various types of notifications."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize the notification service."""
        self.db = db
        self.storage_service = StorageService()

    async def send_approval_notification(
        self,
        user: User,
        request: ApprovalRequest,
        step: Any,
        event_type: str
    ) -> bool:
        """Send approval workflow notification."""
        try:
            subject = f"Approval Required: {request.title}"

            if event_type == "step_initiated":
                message = self._generate_step_initiated_message(request, step, user)
            elif event_type == "step_completed":
                message = self._generate_step_completed_message(request, step, user)
            elif event_type == "workflow_completed":
                message = self._generate_workflow_completed_message(request, user)
            else:
                message = f"Approval update for {request.title}"

            # Send email notification
            if user.email:
                await self._send_email(
                    recipient=user.email,
                    subject=subject,
                    message=message,
                    template="approval_notification",
                    context={
                        "user": user,
                        "request": request,
                        "step": step,
                        "event_type": event_type
                    }
                )

            # Log notification
            await self._log_notification(
                user_id=str(user.id),
                notification_type="approval_workflow",
                subject=subject,
                message=message,
                context={
                    "request_id": str(request.id),
                    "event_type": event_type
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send approval notification: {e}")
            return False

    async def send_decision_notification(
        self,
        user: User,
        request: ApprovalRequest,
        decision: ApprovalDecision
    ) -> bool:
        """Send notification about approval decision."""
        try:
            subject = f"Decision Made: {request.title}"
            message = self._generate_decision_message(request, decision, user)

            if user.email:
                await self._send_email(
                    recipient=user.email,
                    subject=subject,
                    message=message,
                    template="approval_decision",
                    context={
                        "user": user,
                        "request": request,
                        "decision": decision
                    }
                )

            await self._log_notification(
                user_id=str(user.id),
                notification_type="approval_decision",
                subject=subject,
                message=message,
                context={
                    "request_id": str(request.id),
                    "decision_id": str(decision.id),
                    "action": decision.action.value
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send decision notification: {e}")
            return False

    async def send_step_decision_notification(
        self,
        user: User,
        request: ApprovalRequest,
        decision: ApprovalDecision
    ) -> bool:
        """Send notification about step decision to other approvers."""
        try:
            subject = f"Step Update: {request.title}"
            message = self._generate_step_decision_message(request, decision, user)

            if user.email:
                await self._send_email(
                    recipient=user.email,
                    subject=subject,
                    message=message,
                    template="step_decision",
                    context={
                        "user": user,
                        "request": request,
                        "decision": decision
                    }
                )

            await self._log_notification(
                user_id=str(user.id),
                notification_type="step_decision",
                subject=subject,
                message=message,
                context={
                    "request_id": str(request.id),
                    "decision_id": str(decision.id)
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send step decision notification: {e}")
            return False

    async def send_approval_completion_notification(
        self,
        user: User,
        request: ApprovalRequest
    ) -> bool:
        """Send notification when approval workflow is completed."""
        try:
            subject = f"Approval Completed: {request.title}"
            message = self._generate_completion_message(request, user)

            if user.email:
                await self._send_email(
                    recipient=user.email,
                    subject=subject,
                    message=message,
                    template="approval_completion",
                    context={
                        "user": user,
                        "request": request
                    }
                )

            await self._log_notification(
                user_id=str(user.id),
                notification_type="approval_completion",
                subject=subject,
                message=message,
                context={
                    "request_id": str(request.id),
                    "final_status": request.status.value
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send approval completion notification: {e}")
            return False

    async def send_export_completion_notification(
        self,
        user_id: str,
        staged_export_id: str,
        file_path: str
    ) -> bool:
        """Send notification when export is completed after approval."""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User not found for export completion notification: {user_id}")
                return False

            subject = "Export Completed Successfully"
            message = f"Your approved export has been generated and is ready for download."

            if user.email:
                download_url = f"{settings.BASE_URL}/exports/download/{staged_export_id}"
                await self._send_email(
                    recipient=user.email,
                    subject=subject,
                    message=message,
                    template="export_completion",
                    context={
                        "user": user,
                        "staged_export_id": staged_export_id,
                        "download_url": download_url,
                        "file_path": file_path
                    }
                )

            await self._log_notification(
                user_id=user_id,
                notification_type="export_completion",
                subject=subject,
                message=message,
                context={
                    "staged_export_id": staged_export_id,
                    "file_path": file_path
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send export completion notification: {e}")
            return False

    async def send_error_notification(
        self,
        task_id: str,
        error: str,
        traceback: Optional[str] = None
    ) -> bool:
        """Send error notification to administrators."""
        try:
            subject = f"System Error: Task {task_id}"
            message = f"An error occurred in task {task_id}: {error}"

            # Get admin users
            admin_users = self.db.query(User).filter(User.role == "admin").all()

            for admin in admin_users:
                if admin.email:
                    await self._send_email(
                        recipient=admin.email,
                        subject=subject,
                        message=message,
                        template="error_notification",
                        context={
                            "admin": admin,
                            "task_id": task_id,
                            "error": error,
                            "traceback": traceback
                        }
                    )

            await self._log_notification(
                user_id="system",
                notification_type="error",
                subject=subject,
                message=message,
                context={
                    "task_id": task_id,
                    "error": error,
                    "traceback": traceback
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            return False

    def _generate_step_initiated_message(self, request: ApprovalRequest, step: Any, user: User) -> str:
        """Generate message for step initiation."""
        return f"""
Hi {user.first_name or user.email},

Your approval is needed for "{request.title}".

Step: {step.step_name}
Required approvers: {step.required_approvers}
Description: {request.description}

Please review and take action at your earliest convenience.
        """.strip()

    def _generate_step_completed_message(self, request: ApprovalRequest, step: Any, user: User) -> str:
        """Generate message for step completion."""
        return f"""
Hi {user.first_name or user.email},

Step "{step.step_name}" has been completed for "{request.title}".

The approval process will continue to the next step if applicable.
        """.strip()

    def _generate_workflow_completed_message(self, request: ApprovalRequest, user: User) -> str:
        """Generate message for workflow completion."""
        status_text = "approved" if request.status.value == "approved" else "rejected"
        return f"""
Hi {user.first_name or user.email},

The approval workflow for "{request.title}" has been completed.

Final status: {status_text}
        """.strip()

    def _generate_decision_message(self, request: ApprovalRequest, decision: ApprovalDecision, user: User) -> str:
        """Generate message for approval decision."""
        action_text = decision.action.value.replace("_", " ")
        return f"""
Hi {user.first_name or user.email},

A decision has been made on "{request.title}".

Action: {action_text}
Decision by: {decision.approver_id}
Comments: {decision.comments or "No comments provided"}
        """.strip()

    def _generate_step_decision_message(self, request: ApprovalRequest, decision: ApprovalDecision, user: User) -> str:
        """Generate message for step decision notification."""
        action_text = decision.action.value.replace("_", " ")
        return f"""
Hi {user.first_name or user.email},

A decision has been made on the current step of "{request.title}".

Action: {action_text}
Decision by: {decision.approver_id}
Comments: {decision.comments or "No comments provided"}
        """.strip()

    def _generate_completion_message(self, request: ApprovalRequest, user: User) -> str:
        """Generate message for workflow completion."""
        status_text = "approved" if request.status.value == "approved" else "rejected"
        return f"""
Hi {user.first_name or user.email},

The approval workflow for "{request.title}" has been {status_text}.

Status: {status_text}
Completed at: {request.completed_at}
        """.strip()

    async def _send_email(
        self,
        recipient: str,
        subject: str,
        message: str,
        template: str,
        context: Dict[str, Any]
    ) -> bool:
        """Send email notification."""
        try:
            # This is a placeholder implementation
            # In a real implementation, you would use an email service like SendGrid, AWS SES, etc.

            logger.info(f"Sending email to {recipient}: {subject}")
            logger.info(f"Template: {template}")
            logger.info(f"Context: {context}")

            # For now, just log the email content
            email_content = f"""
To: {recipient}
Subject: {subject}
Template: {template}
Context: {json.dumps(context, indent=2)}

Message:
{message}
            """.strip()

            logger.info(f"Email content: {email_content}")

            # Store email in log for development
            if settings.DEBUG:
                await self.storage_service.upload_file(
                    f"emails/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{recipient.replace('@', '_at_')}.txt",
                    email_content.encode('utf-8')
                )

            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def _log_notification(
        self,
        user_id: str,
        notification_type: str,
        subject: str,
        message: str,
        context: Dict[str, Any]
    ) -> None:
        """Log notification for audit purposes."""
        try:
            log_entry = {
                "user_id": user_id,
                "notification_type": notification_type,
                "subject": subject,
                "message": message,
                "context": context,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Store notification log
            await self.storage_service.upload_file(
                f"notifications/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{notification_type}_{user_id}.json",
                json.dumps(log_entry, indent=2).encode('utf-8')
            )

        except Exception as e:
            logger.error(f"Failed to log notification: {e}")

    async def send_bulk_notification(
        self,
        user_ids: List[str],
        notification_type: str,
        subject: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """Send bulk notification to multiple users."""
        results = {}

        for user_id in user_ids:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and user.email:
                success = await self._send_email(
                    recipient=user.email,
                    subject=subject,
                    message=message,
                    template=notification_type,
                    context={**(context or {}), "user": user}
                )
                results[user_id] = success
            else:
                results[user_id] = False

        return results

    async def send_system_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send system-wide alert."""
        try:
            # Get all active users
            active_users = self.db.query(User).filter(User.is_active == True).all()

            subject = f"[{severity.upper()}] {title}"

            for user in active_users:
                if user.email:
                    await self._send_email(
                        recipient=user.email,
                        subject=subject,
                        message=message,
                        template="system_alert",
                        context={
                            "user": user,
                            "alert_type": alert_type,
                            "severity": severity,
                            "title": title,
                            "message": message,
                            **(context or {})
                        }
                    )

            await self._log_notification(
                user_id="system",
                notification_type="system_alert",
                subject=subject,
                message=message,
                context={
                    "alert_type": alert_type,
                    "severity": severity,
                    "title": title,
                    **(context or {})
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send system alert: {e}")
            return False


# Create a global instance for use across the application
notification_service = NotificationService()