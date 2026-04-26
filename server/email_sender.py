"""
Email Sender Module
Sends screenshot alerts via email using SendGrid API.
"""

import base64
import logging
from datetime import datetime

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Attachment,
    Disposition,
    FileContent,
    FileName,
    FileType,
    Mail,
)

from config import (
    EMAIL_ENABLED,
    EMAIL_RECIPIENT,
    EMAIL_SENDER,
    EMAIL_SUBJECT,
    SENDGRID_API_KEY,
)

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends screenshot images via email using SendGrid API."""

    def __init__(self):
        self.enabled = EMAIL_ENABLED
        self.recipient = EMAIL_RECIPIENT
        self.sender = EMAIL_SENDER
        self.subject = EMAIL_SUBJECT

        self.client = None
        if not self.sender or not SENDGRID_API_KEY:
            logger.warning("SendGrid credentials not configured - email sending disabled")
            self.enabled = False
        else:
            self.client = SendGridAPIClient(SENDGRID_API_KEY)


    def send_screenshot(
        self,
        image_bytes: bytes,
        monitor_number: int = 1,
        timestamp: str | None = None,
        user_id: str = "unknown",
    ) -> bool:
        """
        Send a screenshot via email.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.warning("Email sending is disabled - skipping")
            return False

        if not timestamp:
            timestamp = datetime.now().isoformat()

        try:
            body = (
                f"Work Monitor Alert\n\n"
                f"User: {user_id}\n"
                f"Timestamp: {timestamp}\n"
                f"Monitor: {monitor_number}\n\n"
                f"The captured screen was detected as NOT related to programming or software development work.\n"
                f"Please review the attached screenshot.\n"
            )

            message = Mail(
                from_email=self.sender,
                to_emails=self.recipient,
                subject=f"{self.subject} - {user_id} - {timestamp}",
                plain_text_content=body,
            )

            encoded_image = base64.b64encode(image_bytes).decode()
            attachment = Attachment(
                FileContent(encoded_image),
                FileName(f"screenshot_{user_id}_monitor_{monitor_number}_{timestamp.replace(':', '-')}.jpg"),
                FileType("image/jpeg"),
                Disposition("attachment"),
            )
            message.attachment = attachment

            logger.debug("Sending email via SendGrid...")
            response = self.client.send(message)

            if response.status_code in (200, 201, 202):
                logger.info(f"Email sent to {self.recipient} (status: {response.status_code})")
                return True
            else:
                logger.error(f"SendGrid returned status {response.status_code}: {response.body}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email: {type(e).__name__}: {e}")
            return False
