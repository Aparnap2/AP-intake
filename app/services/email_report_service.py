"""
Email delivery service for weekly reports.
Handles email template rendering, delivery, and tracking.
"""

import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Any, Dict, List, Optional
import base64

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, update
from jinja2 import Environment, FileSystemLoader, Template

from app.models.reports import (
    WeeklyReport, ReportDelivery, DeliveryStatus,
    ReportSubscription, ReportType
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailReportService:
    """Service for delivering weekly reports via email."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.template_dir = Path(__file__).parent.parent.parent / "templates" / "reports"

    async def send_weekly_report(
        self,
        report_id: str,
        recipient_groups: Optional[List[str]] = None,
        additional_recipients: Optional[List[str]] = None,
        include_pdf: bool = True
    ) -> List[ReportDelivery]:
        """Send weekly report to recipients."""
        try:
            logger.info(f"Sending weekly report {report_id} via email")

            # Get the report
            report_query = select(WeeklyReport).where(WeeklyReport.id == report_id)
            report_result = await self.session.execute(report_query)
            report = report_result.scalar_one_or_none()

            if not report:
                raise ValueError(f"Report {report_id} not found")

            # Get recipients
            recipients = await self._get_recipients(
                recipient_groups or ["executive", "operations", "finance"],
                additional_recipients or []
            )

            if not recipients:
                logger.warning(f"No recipients found for report {report_id}")
                return []

            # Generate email content
            email_content = await self._generate_email_content(report)

            # Generate PDF attachment if requested
            pdf_content = None
            if include_pdf:
                pdf_content = await self._generate_pdf_attachment(report)

            # Send emails
            deliveries = []
            for recipient in recipients:
                delivery = await self._send_email_to_recipient(
                    report, recipient, email_content, pdf_content
                )
                deliveries.append(delivery)

            logger.info(f"Successfully sent weekly report to {len(deliveries)} recipients")
            return deliveries

        except Exception as e:
            logger.error(f"Failed to send weekly report {report_id}: {e}")
            raise

    async def send_custom_report(
        self,
        report_id: str,
        recipient_email: str,
        subject: Optional[str] = None,
        custom_message: Optional[str] = None,
        include_pdf: bool = True
    ) -> ReportDelivery:
        """Send report to a specific recipient with custom message."""
        try:
            logger.info(f"Sending custom report {report_id} to {recipient_email}")

            # Get the report
            report_query = select(WeeklyReport).where(WeeklyReport.id == report_id)
            report_result = await self.session.execute(report_query)
            report = report_result.scalar_one_or_none()

            if not report:
                raise ValueError(f"Report {report_id} not found")

            # Generate email content with custom message
            email_content = await self._generate_custom_email_content(
                report, subject, custom_message
            )

            # Generate PDF attachment if requested
            pdf_content = None
            if include_pdf:
                pdf_content = await self._generate_pdf_attachment(report)

            # Send email
            delivery = await self._send_email_to_recipient(
                report, {"email": recipient_email, "name": "", "group": "custom"},
                email_content, pdf_content
            )

            logger.info(f"Successfully sent custom report to {recipient_email}")
            return delivery

        except Exception as e:
            logger.error(f"Failed to send custom report {report_id} to {recipient_email}: {e}")
            raise

    async def send_scheduled_reports(self) -> List[ReportDelivery]:
        """Send scheduled weekly reports based on subscriptions."""
        try:
            logger.info("Processing scheduled weekly report deliveries")

            # Get current week's report
            current_report = await self._get_current_week_report()
            if not current_report:
                logger.warning("No current week report found for scheduled delivery")
                return []

            # Get active subscriptions
            subscriptions_query = select(ReportSubscription).where(
                and_(
                    ReportSubscription.report_type == ReportType.WEEKLY,
                    ReportSubscription.is_active == True
                )
            )
            subscriptions_result = await self.session.execute(subscriptions_query)
            subscriptions = subscriptions_result.scalars().all()

            if not subscriptions:
                logger.info("No active subscriptions found")
                return []

            deliveries = []
            for subscription in subscriptions:
                try:
                    # Check if report was already sent to this user
                    existing_delivery_query = select(ReportDelivery).where(
                        and_(
                            ReportDelivery.report_id == current_report.id,
                            ReportDelivery.recipient_email == subscription.user_email
                        )
                    )
                    existing_result = await self.session.execute(existing_delivery_query)
                    existing_delivery = existing_result.scalar_one_or_none()

                    if existing_delivery:
                        logger.debug(f"Report already sent to {subscription.user_email}")
                        continue

                    # Send report based on subscription preferences
                    subscription_deliveries = await self._send_report_to_subscriber(
                        current_report, subscription
                    )
                    deliveries.extend(subscription_deliveries)

                except Exception as e:
                    logger.error(f"Failed to send scheduled report to {subscription.user_email}: {e}")
                    continue

            logger.info(f"Completed scheduled deliveries: {len(deliveries)} emails sent")
            return deliveries

        except Exception as e:
            logger.error(f"Failed to process scheduled reports: {e}")
            raise

    async def _get_recipients(
        self,
        recipient_groups: List[str],
        additional_recipients: List[str]
    ) -> List[Dict[str, str]]:
        """Get recipient emails for different groups."""
        recipients = []

        # Define recipient groups (in production, this would come from database)
        group_recipients = {
            "executive": [
                {"email": "ceo@company.com", "name": "CEO", "group": "executive"},
                {"email": "cfo@company.com", "name": "CFO", "group": "executive"},
                {"email": "coo@company.com", "name": "COO", "group": "executive"}
            ],
            "operations": [
                {"email": "operations@company.com", "name": "Operations Team", "group": "operations"},
                {"email": "ap-manager@company.com", "name": "AP Manager", "group": "operations"}
            ],
            "finance": [
                {"email": "finance@company.com", "name": "Finance Team", "group": "finance"},
                {"email": "controller@company.com", "name": "Controller", "group": "finance"}
            ]
        }

        # Add group recipients
        for group in recipient_groups:
            if group in group_recipients:
                recipients.extend(group_recipients[group])

        # Add additional recipients
        for email in additional_recipients:
            recipients.append({
                "email": email,
                "name": email.split("@")[0].title(),
                "group": "additional"
            })

        # Remove duplicates
        seen_emails = set()
        unique_recipients = []
        for recipient in recipients:
            if recipient["email"] not in seen_emails:
                seen_emails.add(recipient["email"])
                unique_recipients.append(recipient)

        return unique_recipients

    async def _generate_email_content(self, report: WeeklyReport) -> Dict[str, str]:
        """Generate email content using templates."""
        try:
            # Setup Jinja2 environment
            env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=True
            )

            # Load templates
            template = env.get_template("weekly_report.html")
            plain_template = env.get_template("weekly_report.txt")

            # Prepare template context
            context = {
                "report": report,
                "report_data": report.content_json or {},
                "insights": report.insights or {},
                "generated_at": datetime.now(timezone.utc),
                "company_name": "Company Name",  # Would come from settings
                "logo_url": "https://company.com/logo.png",  # Would come from settings
            }

            # Render HTML content
            html_content = template.render(**context)

            # Render plain text content
            text_content = plain_template.render(**context)

            return {
                "html": html_content,
                "text": text_content,
                "subject": f"Weekly AP Intake Report - {report.week_start.strftime('%B %d, %Y')}"
            }

        except Exception as e:
            logger.error(f"Failed to generate email content: {e}")
            # Fallback to basic content
            return {
                "html": f"<p>Weekly report is available. Report ID: {report.id}</p>",
                "text": f"Weekly report is available. Report ID: {report.id}",
                "subject": f"Weekly AP Intake Report - {report.week_start.strftime('%B %d, %Y')}"
            }

    async def _generate_custom_email_content(
        self,
        report: WeeklyReport,
        subject: Optional[str],
        custom_message: Optional[str]
    ) -> Dict[str, str]:
        """Generate custom email content."""
        base_content = await self._generate_email_content(report)

        if subject:
            base_content["subject"] = subject

        if custom_message:
            # Prepend custom message to HTML content
            custom_html = f"""
            <div style="background-color: #f0f8ff; padding: 15px; margin-bottom: 20px; border-left: 4px solid #007bff;">
                <p><strong>Custom Message:</strong></p>
                <p>{custom_message}</p>
            </div>
            """
            base_content["html"] = custom_html + base_content["html"]

            # Prepend custom message to text content
            custom_text = f"""
            CUSTOM MESSAGE:
            {custom_message}

            ---

            """
            base_content["text"] = custom_text + base_content["text"]

        return base_content

    async def _generate_pdf_attachment(self, report: WeeklyReport) -> bytes:
        """Generate PDF attachment for the report."""
        try:
            # This would use a PDF generation library like reportlab or weasyprint
            # For now, return a placeholder PDF
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            import io

            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            # Add content to PDF
            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, height - 50, f"Weekly AP Intake Report")

            p.setFont("Helvetica", 12)
            p.drawString(50, height - 100, f"Period: {report.week_start.strftime('%B %d, %Y')} - {report.week_end.strftime('%B %d, %Y')}")
            p.drawString(50, height - 120, f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")

            # Add summary
            p.drawString(50, height - 160, "Executive Summary:")
            p.drawString(50, height - 180, report.summary[:80] + "..." if len(report.summary) > 80 else report.summary)

            p.save()
            buffer.seek(0)

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Failed to generate PDF attachment: {e}")
            # Return empty PDF as fallback
            return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Report Generation Failed) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000054 00000 n\n0000000115 00000 n\n0000000180 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n294\n%%EOF"

    async def _send_email_to_recipient(
        self,
        report: WeeklyReport,
        recipient: Dict[str, str],
        email_content: Dict[str, str],
        pdf_attachment: Optional[bytes] = None
    ) -> ReportDelivery:
        """Send email to a specific recipient."""
        try:
            # Create delivery record
            delivery = ReportDelivery(
                report_id=report.id,
                recipient_email=recipient["email"],
                recipient_group=recipient["group"],
                delivery_method="email",
                status=DeliveryStatus.PENDING
            )
            self.session.add(delivery)
            await self.session.flush()

            # Send email
            success = await self._send_email(
                recipient["email"],
                email_content["subject"],
                email_content["html"],
                email_content["text"],
                pdf_attachment,
                f"Weekly_Report_{report.week_start.strftime('%Y%m%d')}.pdf"
            )

            if success:
                delivery.status = DeliveryStatus.SENT
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.delivery_attempts = 1
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.error_message = "SMTP send failed"
                delivery.delivery_attempts = 1

            await self.session.commit()
            return delivery

        except Exception as e:
            logger.error(f"Failed to send email to {recipient['email']}: {e}")
            # Update delivery record
            if delivery:
                delivery.status = DeliveryStatus.FAILED
                delivery.error_message = str(e)
                delivery.delivery_attempts = 1
                await self.session.commit()
            raise

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        pdf_attachment: Optional[bytes] = None,
        pdf_filename: str = "report.pdf"
    ) -> bool:
        """Send email using SMTP."""
        try:
            # Email configuration (in production, this would come from environment variables)
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            smtp_username = "reports@company.com"  # From environment
            smtp_password = "app_password"  # From environment

            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"AP Intake Reports <{smtp_username}>"
            message["To"] = to_email

            # Add text and HTML parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")
            message.attach(text_part)
            message.attach(html_part)

            # Add PDF attachment if provided
            if pdf_attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(pdf_attachment)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {pdf_filename}",
                )
                message.attach(part)

            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(smtp_username, smtp_password)
                server.send_message(message)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    async def _get_current_week_report(self) -> Optional[WeeklyReport]:
        """Get the current week's report."""
        today = datetime.now(timezone.utc).date()
        days_since_monday = today.weekday()
        week_start = datetime.combine(
            today - timedelta(days=days_since_monday),
            datetime.min.time(),
            tzinfo=timezone.utc
        )

        query = select(WeeklyReport).where(
            and_(
                WeeklyReport.week_start == week_start,
                WeeklyReport.status == "completed"
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _send_report_to_subscriber(
        self,
        report: WeeklyReport,
        subscription: ReportSubscription
    ) -> List[ReportDelivery]:
        """Send report to a subscriber based on their preferences."""
        deliveries = []

        try:
            # Generate email content
            email_content = await self._generate_email_content(report)

            # Generate PDF if requested
            pdf_content = None
            if subscription.include_pdf_attachment:
                pdf_content = await self._generate_pdf_attachment(report)

            # Send to each recipient group
            for group in subscription.recipient_groups:
                group_recipients = await self._get_group_recipients(group)
                for recipient in group_recipients:
                    delivery = await self._send_email_to_recipient(
                        report, recipient, email_content, pdf_content
                    )
                    deliveries.append(delivery)

            # Update subscription
            subscription.last_delivered_at = datetime.now(timezone.utc)
            subscription.delivery_count += 1

        except Exception as e:
            subscription.failed_delivery_count += 1
            logger.error(f"Failed to send report to subscriber {subscription.user_email}: {e}")

        return deliveries

    async def _get_group_recipients(self, group: str) -> List[Dict[str, str]]:
        """Get recipients for a specific group."""
        # In production, this would query the database for group members
        if group == "executive":
            return [
                {"email": "ceo@company.com", "name": "CEO", "group": "executive"},
                {"email": "cfo@company.com", "name": "CFO", "group": "executive"}
            ]
        elif group == "operations":
            return [
                {"email": "operations@company.com", "name": "Operations Team", "group": "operations"}
            ]
        elif group == "finance":
            return [
                {"email": "finance@company.com", "name": "Finance Team", "group": "finance"}
            ]
        else:
            return []

    async def get_delivery_status(self, delivery_id: str) -> Optional[ReportDelivery]:
        """Get delivery status for a specific delivery."""
        query = select(ReportDelivery).where(ReportDelivery.id == delivery_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_report_deliveries(self, report_id: str) -> List[ReportDelivery]:
        """Get all deliveries for a report."""
        query = select(ReportDelivery).where(
            ReportDelivery.report_id == report_id
        ).order_by(desc(ReportDelivery.created_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def retry_failed_deliveries(self, report_id: str) -> List[ReportDelivery]:
        """Retry failed deliveries for a report."""
        # Get failed deliveries
        failed_query = select(ReportDelivery).where(
            and_(
                ReportDelivery.report_id == report_id,
                ReportDelivery.status == DeliveryStatus.FAILED,
                ReportDelivery.delivery_attempts < 3  # Max 3 attempts
            )
        )
        failed_result = await self.session.execute(failed_query)
        failed_deliveries = failed_result.scalars().all()

        retried_deliveries = []
        for delivery in failed_deliveries:
            try:
                # Get report
                report_query = select(WeeklyReport).where(WeeklyReport.id == report_id)
                report_result = await self.session.execute(report_query)
                report = report_result.scalar_one_or_none()

                if report:
                    # Retry sending
                    await self._retry_delivery(delivery, report)
                    retried_deliveries.append(delivery)

            except Exception as e:
                logger.error(f"Failed to retry delivery {delivery.id}: {e}")

        return retried_deliveries

    async def _retry_delivery(self, delivery: ReportDelivery, report: WeeklyReport):
        """Retry a failed delivery."""
        delivery.delivery_attempts += 1
        delivery.last_attempt_at = datetime.now(timezone.utc)

        try:
            # Generate email content
            email_content = await self._generate_email_content(report)

            # Generate PDF attachment
            pdf_content = await self._generate_pdf_attachment(report)

            # Create recipient info
            recipient = {
                "email": delivery.recipient_email,
                "name": delivery.recipient_email.split("@")[0].title(),
                "group": delivery.recipient_group
            }

            # Send email
            success = await self._send_email(
                recipient["email"],
                email_content["subject"],
                email_content["html"],
                email_content["text"],
                pdf_content,
                f"Weekly_Report_{report.week_start.strftime('%Y%m%d')}.pdf"
            )

            if success:
                delivery.status = DeliveryStatus.SENT
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.error_message = None
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.error_message = "Retry failed"

        except Exception as e:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)

        await self.session.commit()

    async def create_subscription(
        self,
        user_id: str,
        user_email: str,
        delivery_methods: List[str],
        recipient_groups: List[str],
        preferred_day_of_week: int = 1,
        preferred_time: str = "09:00",
        timezone: str = "UTC"
    ) -> ReportSubscription:
        """Create a new report subscription."""
        subscription = ReportSubscription(
            user_id=user_id,
            user_email=user_email,
            report_type=ReportType.WEEKLY,
            delivery_methods=delivery_methods,
            recipient_groups=recipient_groups,
            preferred_day_of_week=preferred_day_of_week,
            preferred_time=preferred_time,
            timezone=timezone
        )
        self.session.add(subscription)
        await self.session.commit()
        return subscription

    async def update_subscription_preferences(
        self,
        subscription_id: str,
        preferences: Dict[str, Any]
    ) -> Optional[ReportSubscription]:
        """Update subscription preferences."""
        query = select(ReportSubscription).where(ReportSubscription.id == subscription_id)
        result = await self.session.execute(query)
        subscription = result.scalar_one_or_none()

        if subscription:
            for key, value in preferences.items():
                if hasattr(subscription, key):
                    setattr(subscription, key, value)
            await self.session.commit()

        return subscription

    async def unsubscribe_user(self, user_id: str, reason: Optional[str] = None) -> bool:
        """Unsubscribe a user from all reports."""
        query = select(ReportSubscription).where(ReportSubscription.user_id == user_id)
        result = await self.session.execute(query)
        subscriptions = result.scalars().all()

        for subscription in subscriptions:
            subscription.is_active = False
            subscription.unsubscribed_at = datetime.now(timezone.utc)
            subscription.unsubscribe_reason = reason

        await self.session.commit()
        return len(subscriptions) > 0