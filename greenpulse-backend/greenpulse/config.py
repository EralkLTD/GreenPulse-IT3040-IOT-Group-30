import os

from dotenv import load_dotenv


# =====================================================
# LOAD ENVIRONMENT VARIABLES
# =====================================================

# Load environment variables from the local .env file.
load_dotenv()


# =====================================================
# APPLICATION CONFIGURATION
# =====================================================

class Config:
    """Application configuration loaded from environment variables."""

    # =================================================
    # MQTT / HIVEMQ CONFIGURATION
    # =================================================

    MQTT_HOST = os.getenv(
        "HIVEMQ_HOST"
    )

    MQTT_PORT = int(
        os.getenv(
            "HIVEMQ_PORT",
            "8883"
        )
    )

    MQTT_USERNAME = os.getenv(
        "HIVEMQ_USERNAME"
    )

    MQTT_PASSWORD = os.getenv(
        "HIVEMQ_PASSWORD"
    )

    # =================================================
    # GEMINI AI CONFIGURATION
    # =================================================

    GEMINI_API_KEY = os.getenv(
        "GEMINI_API_KEY"
    )

    # =================================================
    # GMAIL CONFIGURATION
    # =================================================

    GMAIL_ADDRESS = os.getenv(
        "GMAIL_ADDRESS"
    )

    GMAIL_APP_PASSWORD = os.getenv(
        "GMAIL_APP_PASSWORD"
    )

    # =================================================
    # SMTP DISPLAY NAME
    #
    # Optional. Shown as the sender name in outgoing
    # GreenPulse notification emails.
    # Defaults to "GreenPulse Greenhouse" if not set.
    # =================================================

    SMTP_FROM_NAME = os.getenv(
        "SMTP_FROM_NAME",
        "GreenPulse Greenhouse",
    )

    # =================================================
    # NOTIFICATION DAILY SUMMARY
    #
    # Optional. Default time for daily summary emails
    # when no per-recipient time is configured.
    # Format: "HH:MM" in 24-hour time.
    # =================================================

    NOTIFICATION_DAILY_SUMMARY_TIME = os.getenv(
        "NOTIFICATION_DAILY_SUMMARY_TIME",
        "08:00",
    )

    # =================================================
    # CORE CONFIGURATION VALIDATION
    # =================================================

    @classmethod
    def validate(cls):
        """
        Validate environment variables required for the
        core GreenPulse backend.

        Gmail is intentionally not checked here because
        an email configuration problem should not prevent
        MQTT, telemetry, plant profiles, or Gemini from
        starting.
        """

        required_settings = {

            # HiveMQ
            "HIVEMQ_HOST":
                cls.MQTT_HOST,

            "HIVEMQ_USERNAME":
                cls.MQTT_USERNAME,

            "HIVEMQ_PASSWORD":
                cls.MQTT_PASSWORD,

            # Gemini
            "GEMINI_API_KEY":
                cls.GEMINI_API_KEY,
        }

        missing = [
            name
            for name, value
            in required_settings.items()
            if not value
        ]

        if missing:
            raise ValueError(
                "Missing required environment variables: "
                + ", ".join(missing)
            )

    # =================================================
    # GMAIL CONFIGURATION VALIDATION
    # =================================================

    @classmethod
    def validate_gmail(cls):
        """
        Validate Gmail-specific configuration.

        This is separate from validate() so GreenPulse can
        continue operating even when Gmail is unavailable
        or has not yet been configured.
        """

        required_settings = {
            "GMAIL_ADDRESS":
                cls.GMAIL_ADDRESS,

            "GMAIL_APP_PASSWORD":
                cls.GMAIL_APP_PASSWORD,
        }

        missing = [
            name
            for name, value
            in required_settings.items()
            if not value
        ]

        if missing:
            raise ValueError(
                "Missing Gmail environment variables: "
                + ", ".join(missing)
            )

    # =================================================
    # SMTP CONFIGURATION VALIDATION
    #
    # SMTP reuses GMAIL_ADDRESS and GMAIL_APP_PASSWORD.
    # This method validates them explicitly when the
    # notification email sender is about to be used.
    # =================================================

    @classmethod
    def validate_smtp(cls):
        """
        Validate SMTP sending configuration.

        GreenPulse uses Gmail SMTP with an app password.
        This is the same credential pair used for IMAP.
        """

        required_settings = {
            "GMAIL_ADDRESS":
                cls.GMAIL_ADDRESS,

            "GMAIL_APP_PASSWORD":
                cls.GMAIL_APP_PASSWORD,
        }

        missing = [
            name
            for name, value
            in required_settings.items()
            if not value
        ]

        if missing:
            raise ValueError(
                "Missing SMTP environment variables: "
                + ", ".join(missing)
            )
