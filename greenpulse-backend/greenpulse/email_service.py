"""
GreenPulse - Email Service

Provides both:
1. IMAP reader: Ingests gardening/weather emails from Gmail for AI context (EmailService).
2. SMTP sender: Outgoing email notifications, test emails, and scheduled daily summaries (SmtpSender).
"""
import email
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
import html
import imaplib
import logging
import re
import smtplib
import time
from typing import Dict, Any, Optional

from greenpulse.config import Config

logger = logging.getLogger("greenpulse.email")

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class EmailServiceError(Exception):
    """Raised when Gmail access fails."""


class SmtpError(EmailServiceError):
    """Raised when SMTP delivery fails."""


class EmailService:
    """Read relevant GreenPulse messages from Gmail using IMAP SSL."""

    IMAP_HOST = "imap.gmail.com"
    IMAP_PORT = 993

    KEYWORDS = (
        "weather",
        "rain",
        "storm",
        "watering",
        "water",
        "garden",
        "gardening",
        "plant",
        "greenhouse",
        "temperature",
        "humidity",
    )

    def _validate_config(self):
        if not Config.GMAIL_ADDRESS:
            raise EmailServiceError(
                "GMAIL_ADDRESS is missing from .env."
            )

        if not Config.GMAIL_APP_PASSWORD:
            raise EmailServiceError(
                "GMAIL_APP_PASSWORD is missing from .env."
            )

    @staticmethod
    def _decode_header_value(value):
        if not value:
            return ""

        parts = decode_header(value)
        result = []

        for content, charset in parts:
            if isinstance(content, bytes):
                try:
                    result.append(
                        content.decode(charset or "utf-8", errors="replace")
                    )
                except LookupError:
                    result.append(
                        content.decode("utf-8", errors="replace")
                    )
            else:
                result.append(content)

        return "".join(result)

    @staticmethod
    def _extract_text(message):
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                disposition = str(
                    part.get("Content-Disposition", "")
                ).lower()

                if (
                    content_type == "text/plain"
                    and "attachment" not in disposition
                ):
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = (
                            part.get_content_charset()
                            or "utf-8"
                        )
                        return payload.decode(
                            charset,
                            errors="replace"
                        )

        elif message.get_content_type() == "text/plain":
            payload = message.get_payload(decode=True)
            if payload:
                charset = (
                    message.get_content_charset()
                    or "utf-8"
                )
                return payload.decode(
                    charset,
                    errors="replace"
                )

        return ""

    def get_relevant_recent_emails(
        self,
        max_messages=10
    ):
        """
        Read recent Inbox messages and return only
        gardening/weather-related messages.

        The service does not modify, delete or mark
        messages as read.
        """
        self._validate_config()
        connection = None

        try:
            connection = imaplib.IMAP4_SSL(
                self.IMAP_HOST,
                self.IMAP_PORT
            )

            connection.login(
                Config.GMAIL_ADDRESS,
                Config.GMAIL_APP_PASSWORD
            )

            status, _ = connection.select(
                "INBOX",
                readonly=True
            )

            if status != "OK":
                raise EmailServiceError(
                    "Could not open Gmail Inbox."
                )

            status, data = connection.search(
                None,
                "ALL"
            )

            if status != "OK":
                raise EmailServiceError(
                    "Could not search Gmail Inbox."
                )

            message_ids = data[0].split()
            recent_ids = message_ids[-50:]
            recent_ids.reverse()

            relevant = []

            for message_id in recent_ids:
                status, message_data = connection.fetch(
                    message_id,
                    "(BODY.PEEK[])"
                )

                if status != "OK":
                    continue

                raw_email = None
                for item in message_data:
                    if (
                        isinstance(item, tuple)
                        and isinstance(item[1], bytes)
                    ):
                        raw_email = item[1]
                        break

                if raw_email is None:
                    continue

                message = email.message_from_bytes(
                    raw_email
                )

                subject = self._decode_header_value(
                    message.get("Subject")
                )
                sender = self._decode_header_value(
                    message.get("From")
                )
                date = self._decode_header_value(
                    message.get("Date")
                )
                body = self._extract_text(message)

                searchable_text = (
                    subject + " " + body
                ).lower()

                if not any(
                    keyword in searchable_text
                    for keyword in self.KEYWORDS
                ):
                    continue

                clean_body = " ".join(
                    body.split()
                )

                relevant.append({
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "snippet": clean_body[:500],
                })

                if len(relevant) >= max_messages:
                    break

            return relevant

        except imaplib.IMAP4.error as error:
            raise EmailServiceError(
                "Gmail authentication or IMAP access failed."
            ) from error
        except OSError as error:
            raise EmailServiceError(
                f"Could not connect to Gmail: {error}"
            ) from error
        finally:
            if connection is not None:
                try:
                    connection.logout()
                except Exception:
                    pass


class SmtpSender:
    """
    Delivers outbound notification and status emails via Gmail SMTP with TLS.
    Includes rate-limiting, retry logic, structured HTML/text rendering,
    and recipient validation.
    """

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587
    DEFAULT_TIMEOUT = 15

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.smtp_host = smtp_host or self.SMTP_HOST
        self.smtp_port = smtp_port or self.SMTP_PORT
        self.timeout = timeout

    @staticmethod
    def is_valid_email(addr: str) -> bool:
        """Validate recipient email address format."""
        if not addr or not isinstance(addr, str):
            return False
        clean = addr.strip()
        if len(clean) > 254:
            return False
        return bool(EMAIL_REGEX.match(clean))

    def _get_credentials(self):
        username = Config.GMAIL_ADDRESS
        password = Config.GMAIL_APP_PASSWORD

        if not username or not password:
            raise SmtpError(
                "SMTP credentials missing. Please set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env."
            )
        return username, password

    def send_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Send an email via SMTP with STARTTLS and retry logic.

        Returns status dict:
        {
            "success": bool,
            "status": "ACCEPTED_BY_SMTP" | "REJECTED_INVALID_EMAIL" | "SMTP_ERROR" | "AUTH_FAILED",
            "error": Optional[str],
            "message_id": Optional[str]
        }
        """
        if not self.is_valid_email(to_email):
            logger.warning("Rejected email send to invalid address: %s", to_email)
            return {
                "success": False,
                "status": "REJECTED_INVALID_EMAIL",
                "error": f"Invalid recipient email address format: {to_email}",
                "message_id": None,
            }

        try:
            username, password = self._get_credentials()
        except SmtpError as err:
            logger.warning("SMTP configuration error: %s", err)
            return {
                "success": False,
                "status": "AUTH_FAILED",
                "error": str(err),
                "message_id": None,
            }

        sender_name = Config.SMTP_FROM_NAME or "GreenPulse Greenhouse"
        from_header = formataddr((sender_name, username))
        to_header = formataddr(("", to_email.strip()))
        generated_msg_id = make_msgid(domain="greenpulse.local")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = to_header
        msg["Message-ID"] = generated_msg_id
        msg["Date"] = email.utils.formatdate(localtime=True)

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        last_error = None

        for attempt in range(max_retries + 1):
            server = None
            try:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(username, password)
                server.sendmail(username, [to_email.strip()], msg.as_string())

                logger.info(
                    "Email successfully accepted by SMTP server for recipient=%s Subject='%s'",
                    to_email,
                    subject,
                )
                return {
                    "success": True,
                    "status": "ACCEPTED_BY_SMTP",
                    "error": None,
                    "message_id": generated_msg_id,
                }

            except smtplib.SMTPAuthenticationError as err:
                logger.error("SMTP authentication failed for user %s: %s", username, err)
                return {
                    "success": False,
                    "status": "AUTH_FAILED",
                    "error": "SMTP authentication failed (check Gmail App Password)",
                    "message_id": generated_msg_id,
                }
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as err:
                last_error = err
                logger.warning(
                    "SMTP connection error on attempt %d/%d to %s: %s",
                    attempt + 1,
                    max_retries + 1,
                    to_email,
                    err,
                )
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
            except smtplib.SMTPException as err:
                logger.error("SMTP error sending to %s: %s", to_email, err)
                return {
                    "success": False,
                    "status": "SMTP_ERROR",
                    "error": f"SMTP delivery error: {err}",
                    "message_id": generated_msg_id,
                }
            finally:
                if server is not None:
                    try:
                        server.quit()
                    except Exception:
                        pass

        logger.error(
            "Exhausted %d SMTP retries sending to %s: %s",
            max_retries + 1,
            to_email,
            last_error,
        )
        return {
            "success": False,
            "status": "SMTP_ERROR",
            "error": f"Network or connection error after retries: {last_error}",
            "message_id": generated_msg_id,
        }

    # =========================================================================
    # HIGH-LEVEL TEMPLATED SENDERS
    # =========================================================================

    def send_notification_email(
        self,
        to_email: str,
        notification: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send formatted greenhouse condition notification email."""
        notif_type = notification.get("type", "SYSTEM")
        priority = notification.get("priority", "MEDIUM")
        title = notification.get("title") or f"GreenPulse {notif_type.title()} Alert"
        summary = notification.get("summary", "")
        care_tip = notification.get("care_tip", "")
        plant = notification.get("plant", "Greenhouse Crop")
        location = notification.get("location", "Smart Greenhouse")
        timestamp = notification.get("generated_at", "")

        priority_colors = {
            "CRITICAL": "#e53e3e",
            "HIGH": "#dd6b20",
            "MEDIUM": "#d69e2e",
            "LOW": "#3182ce",
            "INFO": "#38a169",
        }
        color = priority_colors.get(priority.upper(), "#38a169")

        subject = f"[GreenPulse {priority.upper()}] {title} - {plant}"

        text_body = (
            f"GREENPULSE SMART GREENHOUSE ALERT\n"
            f"----------------------------------------\n"
            f"Type: {notif_type} | Priority: {priority}\n"
            f"Plant: {plant}\n"
            f"Location: {location}\n"
            f"Time: {timestamp}\n\n"
            f"SUMMARY:\n{summary}\n\n"
            f"RECOMMENDATION:\n{care_tip}\n\n"
            f"----------------------------------------\n"
            f"GreenPulse AI-Powered Greenhouse System\n"
        )

        safe_title = html.escape(title)
        safe_summary = html.escape(summary)
        safe_tip = html.escape(care_tip)
        safe_plant = html.escape(plant)
        safe_location = html.escape(location)
        safe_type = html.escape(notif_type)
        safe_priority = html.escape(priority)

        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
    .card {{ max-width: 580px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; overflow: hidden; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    .header {{ background: linear-gradient(135deg, #065f46 0%, #047857 100%); padding: 20px 24px; display: flex; align-items: center; justify-content: space-between; }}
    .brand {{ font-size: 18px; font-weight: 700; color: #ffffff; letter-spacing: 0.5px; }}
    .pill {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; background-color: {color}; color: #ffffff; }}
    .content {{ padding: 24px; }}
    .title {{ font-size: 20px; font-weight: 600; color: #ffffff; margin: 0 0 12px 0; }}
    .meta-row {{ display: flex; gap: 16px; margin-bottom: 20px; font-size: 13px; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 12px; }}
    .meta-item {{ margin-right: 16px; }}
    .meta-label {{ color: #64748b; font-size: 11px; text-transform: uppercase; display: block; }}
    .section-title {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #10b981; font-weight: 700; margin: 16px 0 6px 0; }}
    .summary-box {{ background-color: #0f172a; padding: 14px; border-radius: 8px; border-left: 4px solid {color}; font-size: 14px; line-height: 1.5; color: #e2e8f0; }}
    .tip-box {{ background-color: rgba(16, 185, 129, 0.1); padding: 14px; border-radius: 8px; border-left: 4px solid #10b981; font-size: 14px; line-height: 1.5; color: #d1fae5; margin-top: 12px; }}
    .footer {{ padding: 16px 24px; font-size: 12px; color: #64748b; text-align: center; border-top: 1px solid #334155; background-color: #0f172a; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <span class="brand">🌱 GreenPulse</span>
      <span class="pill">{safe_priority} · {safe_type}</span>
    </div>
    <div class="content">
      <h2 class="title">{safe_title}</h2>
      <div class="meta-row">
        <div class="meta-item"><span class="meta-label">Active Plant</span><strong>{safe_plant}</strong></div>
        <div class="meta-item"><span class="meta-label">Location</span><strong>{safe_location}</strong></div>
      </div>
      <div class="section-title">Current Condition</div>
      <div class="summary-box">{safe_summary}</div>
      <div class="section-title">AI Care Recommendation</div>
      <div class="tip-box">{safe_tip}</div>
    </div>
    <div class="footer">
      GreenPulse AI-Powered Smart Greenhouse System · Automated Notification
    </div>
  </div>
</body>
</html>"""

        return self.send_email(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    def send_test_email(self, to_email: str) -> Dict[str, Any]:
        """Send verification test email to validate recipient connectivity."""
        subject = "[GreenPulse] Test Notification - Email Delivery Verified"
        text_body = (
            "GREENPULSE NOTIFICATION TEST\n"
            "----------------------------------------\n"
            "This is a test notification from your GreenPulse Smart Greenhouse.\n"
            "Your email address has been verified and is ready to receive\n"
            "automated plant care alerts and daily greenhouse summaries.\n"
            "----------------------------------------\n"
            "GreenPulse System\n"
        )
        safe_to = html.escape(to_email)
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; }}
    .card {{ max-width: 520px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; }}
    .header {{ background: #065f46; padding: 20px; text-align: center; color: #ffffff; font-size: 20px; font-weight: 700; }}
    .content {{ padding: 24px; font-size: 14px; line-height: 1.6; color: #cbd5e1; }}
    .badge {{ background-color: #10b981; color: #042f2e; padding: 4px 10px; border-radius: 4px; font-weight: 700; }}
    .footer {{ padding: 14px; text-align: center; font-size: 12px; color: #64748b; background-color: #0f172a; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">🌱 GreenPulse Test Notification</div>
    <div class="content">
      <p>Hello,</p>
      <p>This test confirms that your GreenPulse notification system is correctly configured.</p>
      <p>Recipient: <strong style="color:#ffffff;">{safe_to}</strong></p>
      <p>Status: <span class="badge">Connected</span></p>
      <p>You will now receive intelligent plant health alerts and scheduled updates according to your dashboard settings.</p>
    </div>
    <div class="footer">GreenPulse AI-Powered Greenhouse System</div>
  </div>
</body>
</html>"""
        return self.send_email(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    def send_daily_summary_email(
        self,
        to_email: str,
        summary_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send daily scheduled summary report email to recipient."""
        plant = summary_data.get("plant", "Greenhouse Crop")
        location = summary_data.get("location", "Smart Greenhouse")
        date_str = summary_data.get("date", "")
        telemetry = summary_data.get("telemetry", {})
        weather = summary_data.get("weather", {})
        ai_recommendation = summary_data.get("ai_recommendation", "All greenhouse systems operating normally.")

        air_temp = telemetry.get("air_temperature", "--")
        humidity = telemetry.get("humidity", "--")
        soil_moisture = telemetry.get("soil_moisture", "--")
        soil_temp = telemetry.get("soil_temperature", "--")

        subject = f"[GreenPulse Daily Summary] {plant} Status - {date_str}"

        text_body = (
            f"GREENPULSE DAILY GREENHOUSE SUMMARY\n"
            f"Date: {date_str}\n"
            f"Plant: {plant} | Location: {location}\n"
            f"----------------------------------------\n"
            f"LATEST SENSORS:\n"
            f"- Air Temperature: {air_temp}°C\n"
            f"- Humidity: {humidity}%\n"
            f"- Soil Moisture: {soil_moisture}%\n"
            f"- Soil Temperature: {soil_temp}°C\n\n"
            f"AI CARE INTELLIGENCE:\n"
            f"{ai_recommendation}\n"
            f"----------------------------------------\n"
            f"GreenPulse System\n"
        )

        safe_plant = html.escape(str(plant))
        safe_location = html.escape(str(location))
        safe_date = html.escape(str(date_str))
        safe_rec = html.escape(str(ai_recommendation))

        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; }}
    .card {{ max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #059669 0%, #0d9488 100%); padding: 20px 24px; color: #ffffff; }}
    .title {{ font-size: 20px; font-weight: 700; margin: 0; }}
    .subtitle {{ font-size: 13px; opacity: 0.9; margin-top: 4px; }}
    .content {{ padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }}
    .metric {{ background-color: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; }}
    .metric-label {{ font-size: 11px; text-transform: uppercase; color: #94a3b8; }}
    .metric-val {{ font-size: 20px; font-weight: 700; color: #10b981; margin-top: 4px; }}
    .rec-box {{ background-color: rgba(16, 185, 129, 0.1); border-left: 4px solid #10b981; padding: 16px; border-radius: 8px; font-size: 14px; line-height: 1.6; color: #d1fae5; }}
    .footer {{ padding: 16px; text-align: center; font-size: 12px; color: #64748b; background-color: #0f172a; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="title">🌱 Daily Greenhouse Summary</div>
      <div class="subtitle">{safe_plant} · {safe_location} · {safe_date}</div>
    </div>
    <div class="content">
      <div style="font-size:12px; text-transform:uppercase; color:#94a3b8; font-weight:600;">Current Sensors</div>
      <div class="grid">
        <div class="metric"><div class="metric-label">Air Temp</div><div class="metric-val">{air_temp}°C</div></div>
        <div class="metric"><div class="metric-label">Humidity</div><div class="metric-val">{humidity}%</div></div>
        <div class="metric"><div class="metric-label">Soil Moisture</div><div class="metric-val">{soil_moisture}%</div></div>
        <div class="metric"><div class="metric-label">Soil Temp</div><div class="metric-val">{soil_temp}°C</div></div>
      </div>
      <div style="font-size:12px; text-transform:uppercase; color:#94a3b8; font-weight:600; margin-top:16px; margin-bottom:8px;">AI Care Insights</div>
      <div class="rec-box">{safe_rec}</div>
    </div>
    <div class="footer">GreenPulse AI-Powered Smart Greenhouse System</div>
  </div>
</body>
</html>"""

        return self.send_email(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )